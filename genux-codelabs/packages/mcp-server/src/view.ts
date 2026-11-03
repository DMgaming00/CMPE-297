/**
 * The MCP App "view": one self-contained HTML document served as the `ui://` resource.
 * It speaks the MCP Apps bridge (JSON-RPC 2.0 over postMessage) to its host:
 *   view → host  request  ui/initialize           (host replies with hostContext)
 *   view → host  notify   ui/notifications/initialized
 *   host → view  notify   ui/notifications/tool-result  (CallToolResult incl. structuredContent)
 *   view → host  request  tools/call              (host decides whether to allow it)
 * It renders with textContent / createElement only — no innerHTML anywhere.
 */
export const VIEW_URI = "ui://genux/items-view";

export const VIEW_HTML = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root{color-scheme:light dark;--line:#d5dbe8;--accent:#2457d6}
body{font:14px system-ui,sans-serif;margin:0;padding:12px;background:transparent;color:CanvasText}
h2{font-size:15px;margin:0 0 8px}.muted{opacity:.7}table{border-collapse:collapse;width:100%}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
.row{display:flex;gap:8px;flex-wrap:wrap}.card{border:1px solid var(--line);border-radius:10px;padding:10px;min-width:150px}
button{font:inherit;border:1px solid var(--accent);color:var(--accent);background:transparent;border-radius:8px;padding:4px 10px;cursor:pointer}
.win{color:#16794c;font-weight:600}.err{color:#b3261e}
</style></head>
<body><div id="root" class="muted">Waiting for the host…</div>
<script>
(function(){
  var root=document.getElementById('root'),nextId=1,pending={};
  function send(m){m.jsonrpc='2.0';parent.postMessage(m,'*');}
  function request(method,params){return new Promise(function(res,rej){var id=nextId++;pending[id]={res:res,rej:rej};send({id:id,method:method,params:params});});}
  function notify(method,params){send({method:method,params:params});}
  function el(tag,text,cls){var e=document.createElement(tag);if(text!==undefined)e.textContent=String(text);if(cls)e.className=cls;return e;}
  function clear(){while(root.firstChild)root.removeChild(root.firstChild);root.className='';}
  function table(cols,rows){var t=el('table'),h=el('tr');cols.forEach(function(c){h.appendChild(el('th',c));});t.appendChild(h);
    rows.forEach(function(r){var tr=el('tr');r.forEach(function(c){tr.appendChild(el('td',c));});t.appendChild(tr);});return t;}
  function drill(id){request('tools/call',{name:'get_item_details',arguments:{id:id}}).then(function(r){render(r.structuredContent);},function(e){showError(e);});}
  function showError(e){clear();root.appendChild(el('div',(e&&e.message)||'Request failed','err'));}
  function render(sc){
    clear();if(!sc){root.appendChild(el('div','No structured content.','muted'));return;}
    if(sc.kind==='items'){root.appendChild(el('h2','Search results ('+sc.items.length+')'));
      var row=el('div',undefined,'row');sc.items.forEach(function(i){var c=el('div',undefined,'card');c.appendChild(el('strong',i.name));
        c.appendChild(el('div','$'+i.price+' · '+i.rating+'★','muted'));var b=el('button','Details');b.onclick=function(){drill(i.id);};c.appendChild(b);row.appendChild(c);});root.appendChild(row);}
    else if(sc.kind==='comparison'){root.appendChild(el('h2','Comparison'));
      root.appendChild(table(['Name','Price','Rating','Battery','Weight'],sc.items.map(function(i){return [i.name,'$'+i.price,i.rating,i.batteryHours+' h',i.weightKg+' kg'];})));
      var w=sc.winners,names={};sc.items.forEach(function(i){names[i.id]=i.name;});
      root.appendChild(el('p','Cheapest: '+names[w.cheapest]+' · Best rated: '+names[w.bestRated]+' · Lightest: '+names[w.lightest],'win'));}
    else if(sc.kind==='details'){var i=sc.item;root.appendChild(el('h2',i.name));root.appendChild(el('p',i.summary,'muted'));
      root.appendChild(table(['Price','Rating','RAM','Battery','Weight'],[['$'+i.price,i.rating,i.ramGb+' GB',i.batteryHours+' h',i.weightKg+' kg']]));}
    else if(sc.kind==='summary'){root.appendChild(el('h2','Summary'));root.appendChild(el('p',sc.text));}
    else root.appendChild(el('div','Unknown result kind.','err'));
    notify('ui/notifications/size-changed',{height:document.documentElement.scrollHeight});
  }
  window.addEventListener('message',function(ev){
    if(ev.source!==parent)return;var m=ev.data;if(!m||m.jsonrpc!=='2.0')return;
    if(m.id!==undefined&&pending[m.id]&&(m.result!==undefined||m.error)){var p=pending[m.id];delete pending[m.id];m.error?p.rej(m.error):p.res(m.result);return;}
    if(m.method==='ui/notifications/tool-result'){render(m.params&&m.params.structuredContent);}
  });
  request('ui/initialize',{protocolVersion:'2026-01-26',appInfo:{name:'genux-items-view',version:'1.0.0'},appCapabilities:{}})
    .then(function(){notify('ui/notifications/initialized',{});},showError);
})();
</script></body></html>`;
