"""Retrieval inspection uses vector/graph stores and never an LLM provider."""
import json
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from neo4j.exceptions import ServiceUnavailable
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from src.backend.app.main import create_app
from labor_rag.appendices.runtime import AppendixCatalog
from labor_rag.ingest.chunk_schema import point_id
from labor_rag.retrieval.inspect import APPENDIX_PATHS, RetrievalInspector


class Graph:
    def __init__(self, unavailable=False):
        self.unavailable = unavailable
        self.calls = []

    def session(self, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def run(self, cypher, **parameters):
        self.calls.append((cypher, parameters))
        if self.unavailable:
            raise ServiceUnavailable('https://secret.example/?key=must-not-leak')
        if cypher == APPENDIX_PATHS:
            if parameters['seeds'] or parameters['direct_ids']:
                return [{'seed_chunk_id': 'law:d147', 'appendix_id': appendix_id,
                         'nodes': [{'id': 'law:d147', 'article_number': '147'}, {'id': appendix_id, 'appendix_id': appendix_id}],
                         'edges': [{'source': 'law:d147', 'target': appendix_id, 'type': 'CITES_COMPONENT'}]}
                        for appendix_id in ['circular:pl3', 'circular:pl1']]
        return []


@pytest.fixture
def setup_inspector(tmp_path):
    catalog = AppendixCatalog(tmp_path)
    catalog.items = {
        'circular:pl3': {'appendix_id': 'circular:pl3', 'number': 'III', 'document_id': 'circular',
                         'title': 'Work list', 'kind': 'reference', 'review_status': 'reviewed',
                         'still_valid': True, 'artifact_ids': []},
        'circular:pl1': {'appendix_id': 'circular:pl1', 'number': 'I', 'document_id': 'circular',
                         'title': 'Form', 'kind': 'form', 'review_status': 'reviewed',
                         'still_valid': True, 'artifact_ids': []},
    }
    store = QdrantClient(':memory:')
    store.create_collection('legal_test', vectors_config=VectorParams(size=2, distance=Distance.COSINE))
    payloads = [
        {'chunk_id': 'law:d147', 'document_id': 'law', 'meta_dieu': '147', 'text': 'Article 147'},
        {'chunk_id': 'circular:pl3:p1', 'appendix_id': 'circular:pl3', 'document_id': 'circular',
         'chunk_type': 'appendix', 'text': 'FIRST PAGE FROM QDRANT', 'locator': {'start': 0}},
        {'chunk_id': 'circular:pl3:p2', 'appendix_id': 'circular:pl3', 'document_id': 'circular',
         'chunk_type': 'appendix', 'text': 'SECOND PAGE FROM QDRANT', 'locator': {'start': 50}},
        {'chunk_id': 'circular:pl3:p3', 'appendix_id': 'circular:pl3', 'document_id': 'circular',
         'chunk_type': 'appendix', 'text': 'EXPIRED', 'effective_to_date': '2000-01-01'},
        {'chunk_id': 'circular:pl4:p1', 'appendix_id': 'circular:pl4', 'document_id': 'circular',
         'chunk_type': 'appendix', 'text': 'UNRELATED APPENDIX'},
    ]
    points = []
    for index, payload in enumerate(payloads):
        payload.setdefault('still_valid', True)
        payload.setdefault('effective_from_date', None)
        payload.setdefault('effective_to_date', None)
        vector = [1.0, 0.0] if index in [0, 3] else [0.0, 1.0]
        points.append(PointStruct(id=point_id(payload['chunk_id']), vector=vector, payload=payload))
        catalog.chunks[payload['chunk_id']] = {**payload, 'text': 'LOCAL CONTENT MUST NOT BE USED'}
    store.upsert('legal_test', points=points)
    graph = Graph()
    closed = []
    retriever = SimpleNamespace(model=SimpleNamespace(encode=lambda *args, **kwargs: [1.0, 0.0]),
                                qdrant=store, neo4j=graph, collection='legal_test', close=lambda: closed.append(True))
    inspector = RetrievalInspector(catalog, retriever)
    yield inspector, store, graph, closed
    store.close()


def test_retrieves_graph_linked_chunks_with_validity_and_real_content(setup_inspector):
    inspector, _, graph, _ = setup_inspector
    result = inspector.inspect('work affecting development', top_k=1)
    assert result['llm_used'] is False
    assert result['vector_hits'][0]['chunk_id'] == 'law:d147'
    assert graph.calls[0][1]['seeds'] == [{'chunk_id': 'law:d147', 'document_id': 'law', 'article_number': '147'}]
    appendix = next(a for a in result['appendices'] if a['appendix_id'] == 'circular:pl3')
    assert appendix['retrieved_via'] == ['ontology'] and appendix['vector_score'] is None
    assert [c['text'] for c in appendix['chunks']] == ['FIRST PAGE FROM QDRANT', 'SECOND PAGE FROM QDRANT']
    assert all(c['score'] is None and 'chunk_id=' in c['view_url'] for c in appendix['chunks'])
    form = next(a for a in result['appendices'] if a['kind'] == 'form')
    assert form['chunks'] == []
    assert 'circular:pl4' not in {a['appendix_id'] for a in result['appendices']}


def test_graph_failure_keeps_vector_results_without_inventing_links(setup_inspector):
    inspector, _, graph, _ = setup_inspector
    graph.unavailable = True
    result = inspector.inspect('query', top_k=1)
    assert result['vector_hits'] and result['graph']['status'] == 'unavailable'
    assert result['graph']['paths'] == [] and result['appendices'] == []
    assert result['warnings']
    assert 'must-not-leak' not in json.dumps(result)


def test_retrieve_endpoint_reuses_inspector_without_importing_llm(setup_inspector, monkeypatch):
    inspector, _, _, closed = setup_inspector
    for name in ['labor_rag.generation.llm_client', 'google.genai', 'openai', 'anthropic']:
        monkeypatch.setitem(sys.modules, name, None)
    calls = []
    def factory():
        calls.append(True)
        return inspector
    with TestClient(create_app(inspector.catalog, retrieval_factory=factory)) as client:
        for _ in range(2):
            response = client.post('/api/retrieve', json={'question': ' work ', 'top_k': 1})
            assert response.status_code == 200
            assert response.json()['question'] == 'work'
            assert response.json()['llm_used'] is False
            assert 'answer' not in response.json()
        assert client.post('/api/retrieve', json={'question': '  '}).status_code == 422
        assert client.post('/api/retrieve', json={'question': 'x', 'top_k': 21}).status_code == 422
    assert len(calls) == len(closed) == 1


def test_qdrant_failure_reports_stage_without_secrets(setup_inspector):
    inspector, _, _, _ = setup_inspector
    def fail(**kwargs):
        raise RuntimeError('private-api-key')
    inspector.retriever.qdrant.query_points = fail
    with TestClient(create_app(inspector.catalog, retrieval_factory=lambda: inspector)) as client:
        response = client.post('/api/retrieve', json={'question': 'work'})
    assert response.status_code == 503
    assert 'vector_search' in response.json()['detail']
    assert 'private-api-key' not in response.text
