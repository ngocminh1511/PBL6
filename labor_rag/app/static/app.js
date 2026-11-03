'use strict';
const $=id=>document.getElementById(id);
const labels={reference:'Tra cứu',form:'Biểu mẫu',mixed:'Hỗn hợp',unknown:'Chưa phân loại',auto_accepted:'Đã nhận diện',reviewed:'Đã rà soát',needs_review:'Cần rà soát',downloaded:'Đã tải',partial:'Tải chưa đủ',missing:'Chưa tải',extracted:'Đã trích xuất'};
let activeId=null,searchTimer=null,requestNumber=0;
function element(tag,text,className){const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(className)e.className=className;return e;}
function error(message){$('error').textContent=message;$('error').hidden=!message;}
async function api(url,options){const response=await fetch(url,options);if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(typeof body.detail==='string'?body.detail:`Lỗi HTTP ${response.status}`);}return response.json();}
function fileLinks(parent,item){
  const split=element('a','Tải phụ lục HTML');split.href=item.view_url+'?download=true';parent.append(split);
  for(const f of item.files||[]){const link=element('a',`Tải ${f.format.toUpperCase()} nguồn${f.available===false?' · thiếu file':''}`);link.href=f.download_url;link.title=f.file_name;parent.append(link);}
  parent.append(element('small','File nguồn có thể chứa toàn văn và nhiều phụ lục; HTML là phần nội dung đã tách.'));
}
async function preview(id,url){
  try{const item=await api('/api/appendices/'+encodeURIComponent(id));activeId=id;
    $('preview-empty').hidden=true;$('preview').hidden=false;$('preview-doc').textContent=item.document_number+' · Phụ lục '+item.number;
    $('preview-title').textContent=item.title;$('preview-status').textContent=[labels[item.kind],labels[item.review_status]||item.review_status,item.effect_status].filter(Boolean).join(' · ');
    $('open-source').hidden=!item.source_url;if(item.source_url)$('open-source').href=item.source_url;
    $('related').replaceChildren(...(item.article_ids||[]).map(r=>element('span',`Điều ${r.article_number} · ${r.document_id}`)));
    $('downloads').replaceChildren();fileLinks($('downloads'),item);$('frame').src=url||item.view_url;
    document.querySelectorAll('#rows tr').forEach(row=>row.classList.toggle('selected',row.dataset.id===id));
  }catch(e){error(e.message);}
}
async function loadList(){const request=++requestNumber;const params=new URLSearchParams({limit:'1000'});for(const key of ['document','kind','status'])if($(key).value)params.set(key,$(key).value);if($('search').value.trim())params.set('q',$('search').value.trim());
  try{const result=await api('/api/appendices?'+params);if(request!==requestNumber)return;
    if($('document').options.length===1){for(const d of result.documents){const o=element('option',d.document);o.value=d.document_id;$('document').append(o);}}
    $('count').textContent=result.total;$('rows').replaceChildren();$('empty').hidden=result.total>0;
    for(const item of result.items){const row=element('tr');row.dataset.id=item.appendix_id;row.classList.toggle('selected',item.appendix_id===activeId);const name=element('td');const button=element('button',`Phụ lục ${item.number} · ${item.title}`,'row-button');button.onclick=()=>preview(item.appendix_id);name.append(button,element('small',item.document_number));const type=element('td');type.append(element('span',labels[item.kind],'tag '+item.kind));if(item.review_status==='needs_review')type.append(element('span','Cần rà soát','review'));row.append(name,type);$('rows').append(row);}
    const pending=result.documents.filter(d=>d.extraction_status!=='extracted');$('coverage-label').textContent=`Độ phủ: ${result.documents.length} nguồn văn bản · ${pending.length} nguồn chưa trích xuất được phụ lục`;
    const ul=element('ul');for(const d of result.documents){const li=element('li',`${d.document}: ${labels[d.download_status]||d.download_status} · ${d.appendices} phần nhận diện${d.extraction_status!=='extracted'?' · cần nguồn bổ sung hoặc chuyển đổi/OCR':''}`);ul.append(li);}$('coverage-details').replaceChildren(ul);
    if(!activeId&&result.items.length)preview(result.items.find(a=>a.appendix_id==='09-2020-tt-bldtbxh:pl2')?.appendix_id||result.items[0].appendix_id);
  }catch(e){error(e.message);}
}
async function health(probe=false){$('health-probe').disabled=true;try{const h=await api('/api/health'+(probe?'?probe=true':''));$('storage-label').textContent=h.storage.backend==='r2'?'R2 · Có bản lưu trên máy':h.storage.backend==='mixed'?'R2 + file trên máy':'File lưu trên máy';$('health').replaceChildren(element('span',`${h.data.appendices} phần phụ lục · ${h.data.chunks} chunk tra cứu`,'health-item'),element('span',`${h.data.needs_review} cần rà soát`,'health-item warn'));
  for(const key of ['qdrant','neo4j']){const s=h[key];const state=s.connection||s.status;const good=['connected','loaded','indexed'].includes(state);$('health').append(element('span',`${key==='qdrant'?'Qdrant':'Neo4j'}: ${good?'sẵn sàng':state==='failed'||state==='unavailable'?'chưa kết nối':'chưa kiểm tra'}`,'health-item'+(good?'':' warn')));}
}catch(e){error(e.message);}finally{$('health-probe').disabled=false;}}
function message(role,text){const box=element('div',undefined,'message '+role);box.append(element('strong',role==='user'?'BẠN':'KẾT QUẢ TRUY HỒI'),element('div',text,'answer'));$('messages').append(box);return box;}
function citationButton(e){const b=element('button',e.citation,'citation-button');if(e.view_url){b.onclick=()=>{preview(e.appendix_id,e.view_url);document.querySelector('.viewer').scrollIntoView({behavior:'smooth',block:'start'});};}else{b.onclick=()=>{const detail=element('details');detail.append(element('summary',e.citation),element('p',e.text));b.parentNode.append(detail);b.disabled=true;};}return b;}
function chunkCard(hit,open=false){
  const card=element('details',undefined,'retrieval-chunk');card.open=open;
  const score=hit.score==null?'':` · điểm vector ${hit.score.toFixed(4)}`;
  card.append(element('summary',`${hit.rank?'#'+hit.rank+' · ':''}${hit.citation}${score}`),element('code',hit.chunk_id));
  if(hit.ten)card.append(element('p',hit.ten,'chunk-title'));
  card.append(element('pre',hit.text||'Không có nội dung chunk.','chunk-text'));
  if(hit.view_url)card.append(citationButton(hit));
  return card;
}
function graphNode(node){
  if(node.appendix_id)return `Phụ lục ${node.appendix_number||''} · ${node.document_id}`;
  if(node.article_number)return `Điều ${node.article_number} · ${node.document_id}`;
  return node.file_name||node.document_number||node.document_id||node.id;
}
function graphPath(path){
  const box=element('div',undefined,'graph-path');
  for(let i=0;i<path.nodes.length;i++){
    if(i){const edge=path.edges[i-1];box.append(element('span',edge.source===path.nodes[i-1].id?`— ${edge.type} →`:`← ${edge.type} —`,'graph-edge'));}
    const node=element('span',graphNode(path.nodes[i]),'graph-node');node.title=path.nodes[i].id;box.append(node);
  }
  return box;
}
function retrievalSection(parent,title,description){const section=element('section',undefined,'retrieval-stage');section.append(element('h3',title),element('p',description,'verification'));parent.append(section);return section;}
function renderRetrieval(parent,result){
  parent.replaceChildren();parent.classList.add('retrieval-result');
  const seconds=ms=>(ms/1000).toFixed(2)+' s';
  parent.append(element('p',`${result.vector_hits.length} chunk vector · ${result.graph.paths.length} đường liên kết ontology · ${result.appendices.length} phụ lục · ${seconds(result.timings_ms.total)}`,'retrieval-summary'));
  const timingNames={initialization:'Khởi tạo',embedding:'Embedding',vector_search:'Tìm vector',ontology:'Ontology',appendix_fetch:'Lấy chunk phụ lục'};
  const timings=element('div',undefined,'retrieval-timings');for(const [key,label] of Object.entries(timingNames))timings.append(element('span',`${label}: ${seconds(result.timings_ms[key]||0)}`,'health-item'));parent.append(timings);
  parent.append(element('p',`${result.embedding.model} · ${result.embedding.backend} · vector ${result.embedding.dimensions} chiều · collection ${result.collection}. Không gọi LLM để viết lại câu hỏi, xếp hạng hay tạo câu trả lời.`,'verification'));
  for(const warning of result.warnings)parent.append(element('p',warning,'verification warn'));
  const vectors=retrievalSection(parent,'1. Qdrant tìm các đoạn gần nghĩa','Các chunk theo thứ tự điểm tương đồng vector. Điểm này không phải xác suất đúng; nhiều chunk có thể thuộc cùng một phụ lục.');
  for(const hit of result.vector_hits)vectors.append(chunkCard(hit));
  if(!result.vector_hits.length)vectors.append(element('p','Không tìm thấy chunk phù hợp với bộ lọc hiệu lực.'));
  const graph=retrievalSection(parent,'2. Ontology liên kết điều luật với phụ lục',`Nguồn: truy vấn trực tiếp Neo4j · ${result.graph.status==='connected'?'đã kết nối':result.graph.status==='skipped'?'không có điểm bắt đầu':'chưa truy vấn được'}. Mũi tên giữ đúng chiều quan hệ đã lưu; Di chuột lên nút để xem ID.`);
  for(const path of result.graph.paths){const entry=element('div',undefined,'graph-entry');entry.append(element('small',path.seed_chunk_id?`Từ chunk ${path.seed_chunk_id}`:'Đối chiếu liên kết của phụ lục tìm trực tiếp bằng vector'),graphPath(path));graph.append(entry);}
  if(!result.graph.paths.length)graph.append(element('p','Không có đường liên kết điều–phụ lục được trả về từ Neo4j.'));
  if(result.graph.provenance.length){const provenance=element('details');provenance.append(element('summary','Văn bản ban hành và file nguồn trong ontology'));for(const path of result.graph.provenance)provenance.append(graphPath(path));graph.append(provenance);}
  const cypher=element('details');cypher.append(element('summary','Xem Cypher và tham số truy vấn'),element('pre',result.graph.cypher+'\n\n'+JSON.stringify(result.graph.parameters,null,2),'chunk-text'));graph.append(cypher);
  const appendices=retrievalSection(parent,'3. Qdrant trả nội dung phụ lục','Lấy các chunk còn hiệu lực theo appendix_id. Tên, trạng thái và liên kết tải file lấy từ catalog; nội dung chunk bên dưới lấy từ Qdrant.');
  for(const item of result.appendices){
    const card=element('article',undefined,'retrieved-appendix');card.append(element('h4',`Phụ lục ${item.number||''} · ${item.document_number||item.appendix_id}`),element('p',item.title||item.appendix_id));
    card.append(element('p','Tìm được qua: '+item.retrieved_via.map(source=>source==='vector'?'vector Qdrant':'liên kết ontology').join(' + '),'verification'));
    if(item.view_url){const actions=element('div',undefined,'downloads');const view=element('button','Xem phụ lục','citation-button');view.onclick=()=>{preview(item.appendix_id);document.querySelector('.viewer').scrollIntoView({behavior:'smooth',block:'start'});};actions.append(view);fileLinks(actions,item);card.append(actions);}
    if(!item.eligible_for_retrieval)card.append(element('p','Phụ lục chưa đủ điều kiện về rà soát hoặc hiệu lực; chỉ hiển thị metadata.','verification warn'));
    else if(item.kind==='form')card.append(element('p','Biểu mẫu được tra cứu bằng metadata và file nguồn; nội dung mẫu không được embedding.','verification'));
    else if(!item.chunks.length)card.append(element('p',result.appendix_fetch_status==='unavailable'?'Truy vấn lấy chunk từ Qdrant chưa hoàn tất.':'Qdrant không trả chunk còn hiệu lực cho phụ lục này.','verification warn'));
    for(const [index,chunk] of item.chunks.entries())card.append(chunkCard(chunk,index===0));appendices.append(card);
  }
  if(!result.appendices.length)appendices.append(element('p','Chưa tìm được phụ lục từ các kết quả vector và liên kết ontology.'));
  const raw=element('details');raw.append(element('summary','Xem toàn bộ dữ liệu trả về (JSON)'),element('pre',JSON.stringify(result,null,2),'chunk-text'));parent.append(raw);
}
$('retrieval-form').addEventListener('submit',async event=>{
  event.preventDefault();const question=$('question').value.trim();if(!question)return;
  message('user',question);$('send').disabled=true;
  const reply=message('assistant','Đang tạo embedding, tìm vector và truy vấn liên kết ontology… Lượt đầu có thể cần chờ Modal khởi động.');
  try{const result=await api('/api/retrieve',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});renderRetrieval(reply.querySelector('.answer'),result);}
  catch(e){reply.querySelector('.answer').textContent=e.message;}
  finally{$('send').disabled=false;reply.scrollIntoView({behavior:'smooth',block:'start'});}
});
for(const id of ['document','kind','status'])$(id).addEventListener('change',loadList);
$('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(loadList,250);});$('health-probe').onclick=()=>health(true);
loadList();health();
