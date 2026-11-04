"""Viewer HTML autonome (hors ligne, sans dépendance externe) : blocs imbriqués repliables, grisage par test."""
from __future__ import annotations

import json

from ..resolve.uvm_kb import ROLE_COLORS
from .common import INACTIVE, COND_STROKE, PROTO_COLOR, ROLE_ORDER


def build(arch: dict, impl: dict | None) -> str:
    env = arch["environment"]
    data = {
        "tests": env["tests"], "root": env["root"],
        "instances": [{k: i[k] for k in ("id", "path", "name", "parent", "declared_type", "role", "class", "guards",
                                          "conditional", "states", "ports", "loc", "array", "overridden_in")}
                      for i in env["instances"]],
        "flat": env["flat_connections"], "raw": env["connections"], "links": env["handle_links"],
        "colors": ROLE_COLORS, "roleOrder": ROLE_ORDER, "inactive": INACTIVE, "cond": COND_STROKE, "proto": PROTO_COLOR,
        "impl": {c["name"]: {"loc": c["loc"], "lines": c["lines"], "methods": c["methods"],
                             "constraints": [{"name": x["name"], "loc": x["loc"]} for x in c["constraints"]],
                             "covergroups": [{"name": g["name"], "coverpoints": [n for n, _ in g["coverpoints"]],
                                              "crosses": [n for n, _ in g["crosses"]]} for g in c["covergroups"]],
                             "fields": c["fields_macro"]} for c in impl["classes"]} if impl else {},
        "diagnostics": arch["diagnostics"],
    }
    js = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return TEMPLATE.replace("__DATA__", js)


TEMPLATE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>PeaCook – architecture UVM</title>
<style>
*{box-sizing:border-box} body{margin:0;font:13px/1.35 Segoe UI,Helvetica,Arial,sans-serif;color:#222;display:flex;flex-direction:column;height:100vh}
#bar{display:flex;gap:10px;align-items:center;padding:6px 10px;background:#2c3e50;color:#fff;flex-wrap:wrap}
#bar select,#bar input[type=text],#bar button{font:inherit;padding:3px 6px;border-radius:4px;border:1px solid #999}
#bar label{display:flex;gap:4px;align-items:center;cursor:pointer}
#main{flex:1;display:flex;min-height:0}
#canvas{flex:1;position:relative;background:#fafafa;overflow:hidden}
svg{width:100%;height:100%;cursor:grab} svg:active{cursor:grabbing}
#panel{width:380px;border-left:1px solid #ccc;overflow:auto;padding:10px;background:#fff}
#panel h3{margin:.2em 0} .tag{display:inline-block;padding:1px 7px;border-radius:9px;font-size:11px;border:1px solid #888}
table{border-collapse:collapse;width:100%;font-size:12px} td,th{border-bottom:1px solid #eee;padding:2px 4px;text-align:left;vertical-align:top}
.tabs button{border:0;border-bottom:2px solid transparent;background:none;padding:4px 10px;cursor:pointer;font:inherit}
.tabs button.on{border-color:#2471a3;font-weight:600}
#legend{position:absolute;left:8px;bottom:8px;background:#fffd;border:1px solid #ccc;border-radius:6px;padding:6px 8px;font-size:11px;max-width:420px}
#legend span.sw{display:inline-block;width:11px;height:11px;border:1px solid #666;margin:0 3px 0 8px;vertical-align:-1px}
.ok{color:#1e8449}.ko{color:#999}.warn{color:#b9770e}
text{pointer-events:none}
.halo{paint-order:stroke;stroke:#fafafa;stroke-width:3px}
</style></head><body>
<div id="bar">
 <b>PeaCook</b>
 <label>Vue <select id="sel"></select></label>
 <label><input type="checkbox" id="hide"> masquer les éléments grisés</label>
 <label><input type="checkbox" id="raw"> connexions hiérarchiques</label>
 <input type="text" id="q" placeholder="rechercher…">
 <button id="collapse">Tout replier</button><button id="expand">Tout déplier</button><button id="fit">Ajuster</button>
 <button id="svgx">Exporter SVG</button>
 <span id="count" style="opacity:.8"></span>
</div>
<div id="main">
 <div id="canvas"><svg id="svg"><defs id="defs"></defs><g id="vp"></g></svg>
  <div id="legend"></div></div>
 <div id="panel"><i>Clique un bloc pour voir ses détails. Double-clic : replier / déplier.</i></div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const NS='http://www.w3.org/2000/svg';
const LW=176,LH=48,PAD=14,HEAD=26,GAP=16;
const S={test:null,hide:false,raw:false,collapsed:new Set(),sel:null,q:'',tab:'arch'};
const N={};D.instances.forEach(i=>N[i.id]={i,kids:[],id:i.id});
D.instances.forEach(i=>{if(i.parent&&N[i.parent])N[i.parent].kids.push(N[i.id])});
const el=(t,a,p)=>{const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e};
const st=(n)=>S.test?n.i.states[S.test]:null;
const isActive=n=>!S.test||st(n).active;
const visible=n=>!(S.hide&&S.test&&!isActive(n));
const ro=r=>{const k=D.roleOrder.indexOf(r);return k<0?99:k};
function layout(n,rep,top){
  n.vk=n.kids.filter(visible).sort((a,b)=>ro(a.i.role)-ro(b.i.role));
  if(!n.vk.length||S.collapsed.has(n.id)){n.w=LW;n.h=LH;n.leaf=true;n.hidden=n.kids.filter(visible).length>0;
    (function mark(m){m.kids.forEach(k=>{rep[k.id]=n.id;mark(k)})})(n);rep[n.id]=n.id;return}
  n.leaf=false;n.hidden=false;rep[n.id]=n.id;
  n.vk.forEach(k=>layout(k,rep));
  let area=0,mw=0;n.vk.forEach(k=>{area+=(k.w+GAP)*(k.h+GAP);mw=Math.max(mw,k.w)});
  const maxRow=Math.max(mw,Math.sqrt(area)*1.5);let x=0,y=0,rh=0,W=0;
  n.vk.forEach(k=>{if(x&&x+k.w>maxRow){x=0;y+=rh+GAP;rh=0}k.rx=x+PAD;k.ry=y+HEAD+PAD;x+=k.w+GAP;rh=Math.max(rh,k.h);W=Math.max(W,x-GAP)});
  n.w=W+2*PAD;n.h=y+rh+HEAD+2*PAD}
function place(n,ox,oy){n.x=ox;n.y=oy;if(!n.leaf)n.vk.forEach(k=>place(k,ox+k.rx,oy+k.ry))}
function label(n){const i=n.i;if(i.id===D.root)return 'uvm_test_top : '+(S.test||'(tous tests)');
  let t=i.declared_type,ov=false;if(S.test){const s=st(n);t=s.effective_type||t;ov=s.overridden}else if(i.overridden_in.length){ov=true}
  return {name:i.name+((i.array&&i.array.unresolved)?' ×N':''),type:t+(ov?(S.test?'  ⇄':' ⇄*'):'')}}
function style(n){if(S.test&&!isActive(n))return{f:D.inactive.fill,s:D.inactive.stroke,t:D.inactive.font,d:true};
  const cond=!S.test&&n.i.conditional;return{f:D.colors[n.i.role]||'#ececec',s:cond?D.cond:'#555',t:'#000',d:cond}}
function clip(n,tx,ty){const cx=n.x+n.w/2,cy=n.y+n.h/2,dx=tx-cx,dy=ty-cy;if(!dx&&!dy)return[cx,cy];
  const k=Math.min(dx?(n.w/2)/Math.abs(dx):1e9,dy?(n.h/2)/Math.abs(dy):1e9);return[cx+dx*k,cy+dy*k]}
function render(){
  const root=N[D.root],rep={};layout(root,rep);place(root,20,20);
  const vp=document.getElementById('vp');vp.textContent='';
  const defs=document.getElementById('defs');defs.textContent='';
  const cols=new Set(Object.values(D.proto).concat(['#bdbdbd','#555555']));
  cols.forEach(c=>{const m=el('marker',{id:'a'+c.slice(1),viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'},defs);el('path',{d:'M0 0L10 5L0 10z',fill:c},m)});
  const gN=el('g',{},vp),gE=el('g',{},vp);let shown=0;
  (function draw(n){const s=style(n),l=label(n);shown++;
    const g=el('g',{'data-id':n.id,style:'cursor:pointer'},gN);
    const r=el('rect',{x:n.x,y:n.y,width:n.w,height:n.h,rx:9,fill:s.f,stroke:S.sel===n.id?'#e74c3c':s.s,'stroke-width':S.sel===n.id?3:1.4,'stroke-dasharray':s.d?'6 4':'0'},g);
    if(S.q&&n.i.path.toLowerCase().includes(S.q)){r.setAttribute('stroke','#e74c3c');r.setAttribute('stroke-width',3)}
    const nm=typeof l==='string'?l:l.name,ty=typeof l==='string'?'':l.type;
    if(n.leaf){const mark=n.hidden?'▸ ':'';
      el('text',{x:n.x+n.w/2,y:n.y+19,'text-anchor':'middle','font-size':12,'font-weight':600,fill:s.t},g).textContent=mark+nm+(n.hidden?' (+'+countDesc(n)+')':'');
      if(ty)el('text',{x:n.x+n.w/2,y:n.y+35,'text-anchor':'middle','font-size':10.5,fill:s.t},g).textContent=ty.length>30?ty.slice(0,29)+'…':ty}
    else{el('text',{x:n.x+10,y:n.y+17,'font-size':12,'font-weight':700,fill:s.t},g).textContent='▾ '+nm+(ty?' : '+ty:'')}
    g.addEventListener('click',e=>{S.sel=n.id;S.tab='arch';render();panel()});
    g.addEventListener('dblclick',e=>{e.stopPropagation();if(!n.kids.length)return;S.collapsed.has(n.id)?S.collapsed.delete(n.id):S.collapsed.add(n.id);render()});
    if(!n.leaf)n.vk.forEach(draw)})(root);
  const seen=new Set(),list=S.raw?D.raw:D.flat,E=[];
  list.forEach(c=>{const a=S.raw?c.src.inst:c.from.inst,b=S.raw?c.dst.inst:c.to.inst;E.push({a,b,lab:c.txn||c.protocol,p:c.protocol,act:S.test?c.states[S.test]:true,cond:!S.test&&!Object.values(c.states).every(Boolean)})});
  D.links.forEach(c=>E.push({a:c.owner,b:c.target,lab:c.handle,p:'handle',act:S.test?c.states[S.test]:true,cond:!S.test&&!Object.values(c.states).every(Boolean),dash:true}));
  E.forEach(e=>{const a=rep[e.a],b=rep[e.b];if(!a||!b||a===b)return;const A=N[a],B=N[b];if(!visible(A)||!visible(B))return;
    if(S.hide&&S.test&&!e.act)return;const key=a+'>'+b+'>'+e.lab+e.p;if(seen.has(key))return;seen.add(key);
    const [x1,y1]=clip(A,B.x+B.w/2,B.y+B.h/2),[x2,y2]=clip(B,A.x+A.w/2,A.y+A.h/2);
    const col=(S.test&&!e.act)?'#bdbdbd':(D.proto[e.p]||'#555555');
    const dx=x2-x1,dy=y2-y1,cx=(x1+x2)/2-dy*0.12,cy=(y1+y2)/2+dx*0.12;
    el('path',{d:`M${x1} ${y1}Q${cx} ${cy} ${x2} ${y2}`,fill:'none',stroke:col,'stroke-width':1.6,'stroke-dasharray':(e.dash||e.cond||(S.test&&!e.act))?'5 4':'0','marker-end':`url(#a${col.slice(1)})`},gE);
    if(e.lab)el('text',{x:(x1+x2)/2*0.5+cx*0.5,y:(y1+y2)/2*0.5+cy*0.5,'text-anchor':'middle','font-size':10,fill:col,class:'halo'},gE).textContent=e.lab});
  document.getElementById('count').textContent=shown+' blocs';
  vp.setAttribute('data-w',root.w+40);vp.setAttribute('data-h',root.h+40);
}
function countDesc(n){let c=0;(function f(m){m.kids.forEach(k=>{if(visible(k)){c++;f(k)}})})(n);return c}
let vb={x:0,y:0,k:1};
function applyVB(){document.getElementById('vp').setAttribute('transform',`translate(${vb.x} ${vb.y}) scale(${vb.k})`)}
function fit(){const vp=document.getElementById('vp'),sv=document.getElementById('svg');const W=+vp.getAttribute('data-w'),H=+vp.getAttribute('data-h');
  const r=sv.getBoundingClientRect();vb.k=Math.min(r.width/W,r.height/H,1.4);vb.x=(r.width-W*vb.k)/2;vb.y=(r.height-H*vb.k)/2;applyVB()}
(function(){const sv=document.getElementById('svg');let drag=null;
  sv.addEventListener('mousedown',e=>{drag={x:e.clientX-vb.x,y:e.clientY-vb.y}});
  window.addEventListener('mouseup',()=>drag=null);
  window.addEventListener('mousemove',e=>{if(drag){vb.x=e.clientX-drag.x;vb.y=e.clientY-drag.y;applyVB()}});
  sv.addEventListener('wheel',e=>{e.preventDefault();const r=sv.getBoundingClientRect(),px=e.clientX-r.left,py=e.clientY-r.top;
    const f=e.deltaY<0?1.12:1/1.12,k=Math.max(.05,Math.min(4,vb.k*f));vb.x=px-(px-vb.x)*(k/vb.k);vb.y=py-(py-vb.y)*(k/vb.k);vb.k=k;applyVB()},{passive:false})})();
function panel(){const p=document.getElementById('panel');const n=N[S.sel];if(!n){return}
  const i=n.i,cls=D.impl[i.class];
  let h=`<h3>${i.name}</h3><div style="color:#666;word-break:break-all">${i.path}</div><p><span class="tag" style="background:${D.colors[i.role]||'#eee'}">${i.role}</span> <code>${i.declared_type}</code></p>`;
  h+=`<div class="tabs"><button class="${S.tab==='arch'?'on':''}" onclick="S.tab='arch';panel()">Architecture</button><button class="${S.tab==='impl'?'on':''}" onclick="S.tab='impl';panel()">Implémentation</button></div>`;
  if(S.tab==='arch'){
    if(i.guards.length)h+=`<p class="warn"><b>Conditions :</b><br>${i.guards.map(g=>'<code>'+g.replace(/</g,'&lt;')+'</code>').join('<br>')}</p>`;
    h+='<b>États par test</b><table><tr><th>Test</th><th>État</th><th>Type effectif</th></tr>';
    D.tests.forEach(t=>{const s=i.states[t];h+=`<tr><td>${t}</td><td class="${s.active?'ok':'ko'}">${!s.present?'absent':s.active?'✓ actif'+(s.unresolved?' (?)':''):'✗ inactif'}</td><td>${s.effective_type||''}${s.overridden?' ⇄':''}</td></tr>`});h+='</table>';
    if(i.ports.length){h+='<p><b>Ports</b></p><table><tr><th>Nom</th><th>Kind</th><th>Protocole</th><th>Transaction</th></tr>'+i.ports.map(q=>`<tr><td>${q.name}</td><td>${q.kind}</td><td>${q.protocol}</td><td>${q.txn||''}</td></tr>`).join('')+'</table>'}
    const rel=D.flat.filter(c=>c.from.inst===i.id||c.to.inst===i.id);
    if(rel.length){h+='<p><b>Connexions</b></p><table>'+rel.map(c=>`<tr><td>${c.from.inst.slice(5).split('.').slice(-2).join('.')}.${c.from.port}</td><td>→</td><td>${c.to.inst.slice(5).split('.').slice(-2).join('.')}.${c.to.port}</td><td>${c.txn||''}</td></tr>`).join('')+'</table>'}
    h+=`<p style="color:#666">Défini : ${i.loc||''}</p>`
  }else{
    if(!cls){h+='<p><i>Pas de détail d\'implémentation (classe UVM standard ou analyse sans implémentation).</i></p>'}
    else{h+=`<p>Classe <code>${i.class}</code> — ${cls.loc} (${cls.lines} lignes)</p>`;
      h+='<b>Méthodes</b><table><tr><th>Nom</th><th>Lignes</th><th>Branches</th></tr>'+cls.methods.map(m=>`<tr><td>${m.name}${m.is_phase?' ⏱':''}</td><td>${m.lines}</td><td>${m.branches}</td></tr>`).join('')+'</table>';
      if(cls.constraints.length)h+='<p><b>Contraintes</b></p><ul>'+cls.constraints.map(c=>`<li>${c.name}</li>`).join('')+'</ul>';
      if(cls.covergroups.length)h+='<p><b>Covergroups</b></p><ul>'+cls.covergroups.map(c=>`<li>${c.name} — cp: ${c.coverpoints.join(', ')||'—'}; cross: ${c.crosses.join(', ')||'—'}</li>`).join('')+'</ul>';
      if(cls.fields.length)h+=`<p><b>uvm_field_*</b> : ${cls.fields.join(', ')}</p>`}}
  p.innerHTML=h}
function init(){
  const sel=document.getElementById('sel');sel.innerHTML='<option value="">Référence (tous tests)</option>'+D.tests.map(t=>`<option>${t}</option>`).join('');
  sel.onchange=()=>{S.test=sel.value||null;render();panel()};
  document.getElementById('hide').onchange=e=>{S.hide=e.target.checked;render();fit()};
  document.getElementById('raw').onchange=e=>{S.raw=e.target.checked;render()};
  document.getElementById('q').oninput=e=>{S.q=e.target.value.toLowerCase();render()};
  document.getElementById('collapse').onclick=()=>{D.instances.forEach(i=>{if(N[i.id].kids.length&&i.id!==D.root)S.collapsed.add(i.id)});render();fit()};
  document.getElementById('expand').onclick=()=>{S.collapsed.clear();render();fit()};
  document.getElementById('fit').onclick=fit;
  document.getElementById('svgx').onclick=()=>{const s=document.getElementById('svg').cloneNode(true);s.setAttribute('xmlns',NS);
    const vp=document.getElementById('vp');s.setAttribute('viewBox',`0 0 ${vp.getAttribute('data-w')} ${vp.getAttribute('data-h')}`);s.querySelector('#vp').removeAttribute('transform');
    const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(s)],{type:'image/svg+xml'}));a.download='uvm_'+(S.test||'all')+'.svg';a.click()};
  const lg=document.getElementById('legend');const used=[...new Set(D.instances.map(i=>i.role))];
  lg.innerHTML=used.map(r=>`<span class="sw" style="background:${D.colors[r]||'#ececec'}"></span>${r}`).join('')+
   `<br><span class="sw" style="background:#fff;border:2px dashed ${D.cond}"></span>conditionnel (vue référence)<span class="sw" style="background:${D.inactive.fill};border-color:${D.inactive.stroke}"></span>désactivé (grisé)`+
   `<br>flèches : <span style="color:${D.proto.analysis}">analysis</span> · <span style="color:${D.proto.seq_item}">seq_item</span> · <span style="color:${D.proto.handle}">handle séquenceur</span>`;
  const hp=new URLSearchParams(location.hash.slice(1));
  if(hp.get('test')&&D.tests.includes(hp.get('test'))){S.test=hp.get('test');sel.value=S.test}
  if(hp.get('hide')==='1'){S.hide=true;document.getElementById('hide').checked=true}
  if(hp.get('select')&&N[hp.get('select')]){S.sel=hp.get('select')}
  render();fit();if(S.sel)panel()}
init();
</script></body></html>
"""
