"""Portable Neo4j trust and TLS guarantees without external services."""
import os
import re
import ssl
from pathlib import Path
from unittest.mock import Mock

import certifi
import pytest
from neo4j.exceptions import ConfigurationError

from labor_rag.services.neo4j import create_neo4j_driver


@pytest.mark.parametrize("scheme", ["neo4j", "bolt"])
def test_verified_tls_trusts_system_and_bundled_cas_without_environment_changes(monkeypatch, scheme):
    monkeypatch.delenv("SSL_CERT_FILE", raising=False)
    before = dict(os.environ)
    system_roots = set(ssl.create_default_context().get_ca_certs(binary_form=True))
    pem_bundle = Path(certifi.where()).read_text(encoding="ascii")
    bundled_roots = {
        ssl.PEM_cert_to_DER_cert(pem)
        for pem in re.findall(r"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", pem_bundle, re.S)
    }
    assert bundled_roots
    factory = Mock()
    query = "?region=eu" if scheme == "neo4j" else ""
    result = create_neo4j_driver(
        f"{scheme}+s://graph.example:7687{query}", auth=("user", "secret"),
        driver_factory=factory, connection_timeout=5,
    )

    assert result is factory.return_value
    assert factory.call_args.args == (f"{scheme}://graph.example:7687{query}",)
    options = factory.call_args.kwargs
    assert options["auth"] == ("user", "secret")
    assert options["connection_timeout"] == 5
    assert options["encrypted"] is True
    context = options["ssl_context"]
    assert context.check_hostname is True
    assert context.verify_mode == ssl.CERT_REQUIRED
    assert context.minimum_version >= ssl.TLSVersion.TLSv1_2
    trusted_roots = set(context.get_ca_certs(binary_form=True))
    assert system_roots <= trusted_roots
    assert bundled_roots <= trusted_roots
    assert dict(os.environ) == before


@pytest.mark.parametrize("uri", [
    "bolt://localhost:7687", "neo4j://localhost:7687",
    "bolt+ssc://graph.example", "neo4j+ssc://graph.example",
])
def test_other_connection_modes_keep_driver_behavior(uri):
    factory = Mock()
    create_neo4j_driver(uri, auth=("user", "secret"), driver_factory=factory)
    factory.assert_called_once_with(uri, auth=("user", "secret"))


def test_bad_ca_bundle_fails_before_creating_a_driver(tmp_path, monkeypatch):
    invalid_bundle = tmp_path / "invalid.pem"
    invalid_bundle.write_text("invalid CA bundle", encoding="ascii")
    monkeypatch.setattr(certifi, "where", lambda: str(invalid_bundle))
    factory = Mock()
    with pytest.raises(ssl.SSLError):
        create_neo4j_driver("neo4j+s://graph.example", auth=("user", "secret"), driver_factory=factory)
    factory.assert_not_called()


def test_conflicting_security_options_still_raise_driver_configuration_error():
    with pytest.raises(ConfigurationError):
        create_neo4j_driver("neo4j+s://graph.example", auth=("user", "secret"), encrypted=False)


def test_each_driver_has_its_own_tls_context():
    factory = Mock()
    for _ in range(2):
        create_neo4j_driver("neo4j+s://graph.example", auth=("user", "secret"), driver_factory=factory)
    contexts = [call.kwargs["ssl_context"] for call in factory.call_args_list]
    assert contexts[0] is not contexts[1]
