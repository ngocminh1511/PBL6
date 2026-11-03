'use strict';
const $=id=>document.getElementById(id);
const labels={reference:'Tra cứu',form:'Biểu mẫu',mixed:'Hỗn hợp',unknown:'Chưa phân loại',auto_accepted:'Đã nhận diện',reviewed:'Đã rà soát',needs_review:'Cần rà soát',downloaded:'Đã tải',partial:'Tải chưa đủ',missing:'Chưa tải',extracted:'Đã trích xuất'};
let activeId=null,sessionId=null,searchTimer=null,requestNumber=0;
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
async function health(probe=false){$('health-probe').disabled=true;try{const h=await api('/api/health'+(probe?'?probe=true':''));$('storage-label').textContent=h.storage.backend==='r2'?'R2 ? C? b?n l?u tr?n m?y':h.storage.backend==='mixed'?'R2 + file tr?n m?y':'File l?u tr?n m?y';$('health').replaceChildren(element('span',`${h.data.appendices} phần phụ lục · ${h.data.chunks} chunk tra cứu`,'health-item'),element('span',`${h.data.needs_review} cần rà soát`,'health-item warn'));
  for(const key of ['qdrant','neo4j']){const s=h[key];const state=s.connection||s.status;const good=['connected','loaded','indexed'].includes(state);$('health').append(element('span',`${key==='qdrant'?'Qdrant':'Neo4j'}: ${good?'sẵn sàng':state==='failed'||state==='unavailable'?'chưa kết nối':'chưa kiểm tra'}`,'health-item'+(good?'':' warn')));}
}catch(e){error(e.message);}finally{$('health-probe').disabled=false;}}
function message(role,text){const box=element('div',undefined,'message '+role);box.append(element('strong',role==='user'?'BẠN':'TRỢ LÝ'),element('div',text,'answer'));$('messages').append(box);return box;}
function citationButton(e){const b=element('button',e.citation,'citation-button');if(e.view_url){b.onclick=()=>{preview(e.appendix_id,e.view_url);document.querySelector('.viewer').scrollIntoView({behavior:'smooth',block:'start'});};}else{b.onclick=()=>{const detail=element('details');detail.append(element('summary',e.citation),element('p',e.text));b.parentNode.append(detail);b.disabled=true;};}return b;}
function renderAnswer(parent,text,evidence){parent.replaceChildren();let cursor=0;for(const match of text.matchAll(/\[([^\]]+)\]/g)){parent.append(document.createTextNode(text.slice(cursor,match.index)));const source=evidence.find(e=>e.citation===match[1].trim());if(source){const button=citationButton(source);button.textContent=match[0];parent.append(button);}else parent.append(document.createTextNode(match[0]));cursor=match.index+match[0].length;}parent.append(document.createTextNode(text.slice(cursor)));}
$('chat-form').addEventListener('submit',async event=>{event.preventDefault();const question=$('question').value.trim();if(!question)return;message('user',question);$('question').value='';$('send').disabled=true;const reply=message('assistant','Đang tìm nguồn và tạo câu trả lời…');try{const result=await api('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question,session_id:sessionId})});sessionId=result.session_id;renderAnswer(reply.querySelector('.answer'),result.answer,result.evidence);const refs=element('div',undefined,'citations');for(const e of result.evidence)refs.append(citationButton(e));reply.append(refs);for(const a of result.attachments||[]){const links=element('div',undefined,'downloads');links.append(element('small',a.title));fileLinks(links,a);reply.append(links);}reply.append(element('p',result.citation_check.all_verified?'Các trích dẫn nhận diện đều khớp bằng chứng đã truy hồi.':'Trích dẫn chưa xác minh: '+result.citation_check.unverified.join('; '),'verification'+(result.citation_check.all_verified?'':' warn')));for(const warning of result.warnings||[])reply.append(element('p',warning,'verification warn'));}catch(e){reply.querySelector('.answer').textContent=e.message;}finally{$('send').disabled=false;$('messages').scrollTop=$('messages').scrollHeight;}});
for(const id of ['document','kind','status'])$(id).addEventListener('change',loadList);
$('search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(loadList,250);});$('health-probe').onclick=()=>health(true);
loadList();health();
