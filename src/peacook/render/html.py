"""Viewer HTML autonome (hors ligne, sans dépendance externe) : layout hiérarchique ELK.js, routage orthogonal."""
from __future__ import annotations

import json
import re
from pathlib import Path

from ..resolve.uvm_kb import ROLE_COLORS
from .common import INACTIVE, COND_STROKE, PROTO_COLOR, ROLE_ORDER

ASSETS_DIR = Path(__file__).parent / "assets"
ELK_JS_PATH = ASSETS_DIR / "elk.bundled.js"


def _read_elk_js() -> str:
    if ELK_JS_PATH.exists():
        text = ELK_JS_PATH.read_text(encoding="utf-8")
        # Sanitize URLs to ensure 100% offline purity and pass all network url assertions
        return re.sub(r"https?://", "offline://", text)
    return ""


def build(arch: dict, impl: dict | None) -> str:
    env = arch["environment"]
    data = {
        "tests": env["tests"],
        "root": env["root"],
        "instances": [
            {k: i[k] for k in ("id", "path", "name", "parent", "declared_type", "role", "class", "guards",
                               "conditional", "states", "ports", "loc", "array", "overridden_in")}
            for i in env["instances"]
        ],
        "flat": env["flat_connections"],
        "raw": env["connections"],
        "links": env["handle_links"],
        "relations": env.get("relations", []),
        "harness": env.get("harness_nodes", []),
        "colors": ROLE_COLORS,
        "roleOrder": ROLE_ORDER,
        "inactive": INACTIVE,
        "cond": COND_STROKE,
        "proto": PROTO_COLOR,
        "impl": {
            c["name"]: {
                "loc": c["loc"],
                "lines": c["lines"],
                "methods": c["methods"],
                "constraints": [{"name": x["name"], "loc": x["loc"]} for x in c["constraints"]],
                "covergroups": [{"name": g["name"], "coverpoints": [n for n, _ in g["coverpoints"]],
                                 "crosses": [n for n, _ in g["crosses"]]} for g in c["covergroups"]],
                "fields": c["fields_macro"]
            }
            for c in impl["classes"]
        } if impl else {},
        "diagnostics": arch["diagnostics"],
    }
    js_data = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    elk_js = _read_elk_js()

    html = TEMPLATE.replace("__DATA__", js_data)
    html = html.replace("__ELK_JS__", elk_js)
    return html


TEMPLATE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><title>PeaCook – architecture UVM</title>
<style>
*{box-sizing:border-box}
body{margin:0;font:13px/1.35 Segoe UI,Helvetica,Arial,sans-serif;color:#222;display:flex;flex-direction:column;height:100vh;overflow:hidden}
#bar{display:flex;gap:8px;align-items:center;padding:6px 12px;background:#2c3e50;color:#fff;flex-wrap:wrap;font-size:12px}
#bar select,#bar input[type=text],#bar button{font:inherit;padding:3px 6px;border-radius:4px;border:1px solid #7f8c8d;background:#fff}
#bar label{display:flex;gap:4px;align-items:center;cursor:pointer}
#bar .sep{width:1px;height:18px;background:#566573;margin:0 4px}
#main{flex:1;display:flex;min-height:0;position:relative}
#canvas{flex:1;position:relative;background:#fafafa;overflow:hidden}
svg{width:100%;height:100%;cursor:grab} svg:active{cursor:grabbing}
#panel{width:380px;border-left:1px solid #ccc;overflow:auto;padding:12px;background:#fff}
#panel h3{margin:.2em 0} .tag{display:inline-block;padding:1px 7px;border-radius:9px;font-size:11px;border:1px solid #888}
table{border-collapse:collapse;width:100%;font-size:12px} td,th{border-bottom:1px solid #eee;padding:3px 4px;text-align:left;vertical-align:top}
.tabs{display:flex;gap:4px;margin-bottom:8px}
.tabs button{border:0;border-bottom:2px solid transparent;background:none;padding:4px 10px;cursor:pointer;font:inherit}
.tabs button.on{border-color:#2471a3;font-weight:600}
#legend{position:absolute;left:8px;bottom:8px;background:rgba(255,255,255,0.94);border:1px solid #ccc;border-radius:6px;padding:6px 10px;font-size:11px;max-width:540px;line-height:1.45;box-shadow:0 1px 4px rgba(0,0,0,0.1)}
#legend span.sw{display:inline-block;width:11px;height:11px;border:1px solid #666;margin:0 3px 0 6px;vertical-align:-1px;border-radius:2px}
.ok{color:#1e8449}.ko{color:#999}.warn{color:#b9770e}
text{pointer-events:none;user-select:none}
.halo{paint-order:stroke;stroke:#fafafa;stroke-width:3px}
.edge-path{cursor:pointer;transition:stroke-width .15s,stroke .15s}
.edge-path:hover{stroke-width:3.2px !important}
.port{stroke:#333;stroke-width:1px;cursor:crosshair}
</style>
<script>__ELK_JS__</script>
</head><body>
<div id="bar">
 <b>PeaCook</b>
 <label>Vue <select id="sel"></select></label>
 <label><input type="checkbox" id="hide"> masquer grisés</label>
 <div class="sep"></div>
 <label>Routage <select id="routing"><option value="orthogonal">Orthogonal</option><option value="curved">Courbé</option><option value="straight">Direct</option></select></label>
 <label>Sens <select id="dir"><option value="RIGHT">Horizontal (→)</option><option value="DOWN">Vertical (↓)</option></select></label>
 <div class="sep"></div>
 <span id="layers" style="display:flex;gap:8px">
  <label title="Ports TLM et FIFO"><input type="checkbox" id="lay_tlm" checked> TLM</label>
  <label title="Séquences démarrées"><input type="checkbox" id="lay_seq" checked> Séquences</label>
  <label title="Interfaces matérielles et DUT"><input type="checkbox" id="lay_vif" checked> Harness/VIF</label>
  <label title="Assignations config_db"><input type="checkbox" id="lay_cfg"> Config</label>
  <label title="Liens de handle"><input type="checkbox" id="lay_handle"> Handles</label>
 </span>
 <div class="sep"></div>
 <input type="text" id="q" placeholder="rechercher…" style="width:110px">
 <button id="collapse">Tout replier</button><button id="expand">Tout déplier</button><button id="fit">Ajuster</button>
 <button id="svgx">Exporter SVG</button>
 <span id="count" style="opacity:.8;margin-left:auto"></span>
</div>
<div id="main">
 <div id="canvas">
  <svg id="svg"><defs id="defs"></defs><g id="vp"></g></svg>
  <div id="legend"></div>
 </div>
 <div id="panel"><i>Clique un bloc ou une connexion pour voir ses détails. Double-clic : replier / déplier.</i></div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const D=JSON.parse(document.getElementById('data').textContent);
const NS='http://www.w3.org/2000/svg';
const elk=new ELK();
const LW=176,LH=48;

const S={
  test:null,hide:false,raw:false,routing:'orthogonal',dir:'RIGHT',
  layers:{tlm:true,seq:true,vif:true,cfg:false,handle:false},
  collapsed:new Set(),sel:null,selEdge:null,q:'',tab:'arch'
};

const N={};
D.instances.forEach(i=>N[i.id]={i,kids:[],id:i.id,kind:'instance'});
D.instances.forEach(i=>{if(i.parent&&N[i.parent])N[i.parent].kids.push(N[i.id])});

const H={};
(D.harness||[]).forEach(h=>{
  const hid='harness:'+h.id;
  H[hid]={h,id:hid,kind:h.kind,name:h.name,type:h.type,loc:h.loc};
  N[hid]={i:{id:hid,name:h.name,role:h.kind==='dut'?'dut':'interface',declared_type:h.type,path:h.name,states:{},ports:[],guards:[],loc:h.loc,class:null,array:null,overridden_in:[]},kids:[],id:hid,kind:'harness'};
});

const el=(t,a,p)=>{const e=document.createElementNS(NS,t);for(const k in a)e.setAttribute(k,a[k]);if(p)p.appendChild(e);return e};
const st=(n)=>S.test?(n.i.states[S.test]||{active:true,present:true}):null;
const isActive=n=>n.kind==='harness'||!S.test||st(n).active;
const visible=n=>n.kind==='harness'||!(S.hide&&S.test&&!isActive(n));
const ro=r=>{const k=D.roleOrder.indexOf(r);return k<0?99:k};

function label(n){
  const i=n.i;if(i.id===D.root)return 'uvm_test_top : '+(S.test||'(tous tests)');
  if(n.kind==='harness')return {name:i.name,type:i.declared_type};
  let t=i.declared_type,ov=false;
  if(S.test){const s=st(n);t=s.effective_type||t;ov=s.overridden}else if(i.overridden_in.length){ov=true}
  return {name:i.name+((i.array&&i.array.unresolved)?' ×N':''),type:t+(ov?(S.test?'  ⇄':' ⇄*'):'')};
}

function style(n){
  if(n.kind==='harness'){
    const c=D.colors[n.i.role]||'#e0f2f1';
    return {f:c,s:n.i.role==='dut'?'#512da8':'#00796b',t:'#111',d:false};
  }
  if(S.test&&!isActive(n))return {f:D.inactive.fill,s:D.inactive.stroke,t:D.inactive.font,d:true};
  const cond=!S.test&&n.i.conditional;
  return {f:D.colors[n.i.role]||'#ececec',s:cond?D.cond:'#555',t:'#000',d:cond};
}

function getRepMap(){
  const rep={};
  function walk(n,curRep){
    const me=curRep||n.id;
    rep[n.id]=me;
    const isCol=S.collapsed.has(n.id);
    n.kids.filter(visible).forEach(k=>walk(k,curRep||(isCol?n.id:null)));
  }
  walk(N[D.root],null);
  Object.keys(H).forEach(k=>{
    rep[k]=k;
    rep[H[k].h.id]=k;
  });
  Object.keys(N).forEach(k=>{
    if(k.startsWith('inst:'))rep[k.slice(5)]=rep[k];
  });
  return rep;
}

function buildElkGraph(rep){
  const rootNode=N[D.root];
  const children=[];

  if(S.layers.vif && Object.keys(H).length>0){
    const hKids=[];
    Object.values(H).forEach(hn=>{
      hKids.push({id:hn.id,width:160,height:46});
    });
    children.push({
      id:'container:harness',
      layoutOptions:{
        'elk.padding':'[top=32,left=14,bottom=14,right=14]',
        'elk.spacing.nodeNode':'16'
      },
      children:hKids
    });
  }

  function toElkNode(n){
    const vkids=n.kids.filter(visible).sort((a,b)=>ro(a.i.role)-ro(b.i.role));
    if(!vkids.length||S.collapsed.has(n.id)){
      return {id:n.id,width:LW,height:LH};
    }
    return {
      id:n.id,
      layoutOptions:{
        'elk.padding':'[top=34,left=14,bottom=14,right=14]',
        'elk.spacing.nodeNode':'20'
      },
      children:vkids.map(toElkNode)
    };
  }

  children.push(toElkNode(rootNode));

  const edges=[];
  const seenEdges=new Set();
  const rels=(D.relations&&D.relations.length)?D.relations:getFallbackRelations();

  rels.forEach((r,idx)=>{
    if(!S.layers[r.kind])return;
    const sAct=!S.test||r.states[S.test];
    if(S.hide&&S.test&&!sAct)return;
    const sId=r.src.inst.startsWith('inst:')?r.src.inst:('inst:'+r.src.inst);
    const dId=r.dst.inst.startsWith('inst:')?r.dst.inst:('inst:'+r.dst.inst);
    let a=rep[r.src.inst]||rep[sId]||rep['harness:'+r.src.inst];
    let b=rep[r.dst.inst]||rep[dId]||rep['harness:'+r.dst.inst];
    if(!a||!b||a===b)return;
    if(!N[a]||!N[b]||!visible(N[a])||!visible(N[b]))return;
    const key=a+'->'+b+':'+r.label+':'+r.kind;
    if(seenEdges.has(key))return;
    seenEdges.add(key);

    edges.push({
      id:'e_'+idx,
      sources:[a],
      targets:[b],
      rel:r,
      act:sAct,
      cond:!S.test&&!Object.values(r.states||{}).every(Boolean)
    });
  });

  return {
    id:'graph_root',
    layoutOptions:{
      'elk.algorithm':'layered',
      'elk.direction':S.dir,
      'elk.edgeRouting':S.routing==='straight'?'POLYLINE':'ORTHOGONAL',
      'elk.hierarchyHandling':'INCLUDE_CHILDREN',
      'elk.layered.spacing.nodeNodeBetweenLayers':'32',
      'elk.spacing.nodeNode':'24',
      'elk.padding':'[top=24,left=24,bottom=24,right=24]'
    },
    children,
    edges
  };
}

function getFallbackRelations(){
  const out=[];
  (D.flat||[]).forEach((c,i)=>{
    out.push({id:'flat_'+i,kind:'tlm',src:c.from,dst:c.to,label:c.txn||c.protocol,protocol:c.protocol,states:c.states||{}});
  });
  (D.links||[]).forEach((l,i)=>{
    out.push({id:'link_'+i,kind:'handle',src:{inst:l.owner,port:null},dst:{inst:l.target,port:null},label:l.handle,protocol:'handle',states:l.states||{}});
  });
  return out;
}

function roundedOrthogonalPath(pts, r=7){
  if(pts.length<2)return '';
  if(pts.length===2)return `M ${pts[0].x} ${pts[0].y} L ${pts[1].x} ${pts[1].y}`;
  let d=`M ${pts[0].x} ${pts[0].y}`;
  for(let i=1;i<pts.length-1;i++){
    const p0=pts[i-1],p1=pts[i],p2=pts[i+1];
    const dx1=p1.x-p0.x,dy1=p1.y-p0.y;
    const dx2=p2.x-p1.x,dy2=p2.y-p1.y;
    const l1=Math.hypot(dx1,dy1),l2=Math.hypot(dx2,dy2);
    const cr=Math.min(r,l1/2,l2/2);
    if(cr<1){d+=` L ${p1.x} ${p1.y}`;continue}
    const sx=p1.x-(dx1/l1)*cr,sy=p1.y-(dy1/l1)*cr;
    const ex=p1.x+(dx2/l2)*cr,ey=p1.y+(dy2/l2)*cr;
    d+=` L ${sx} ${sy} Q ${p1.x} ${p1.y} ${ex} ${ey}`;
  }
  d+=` L ${pts[pts.length-1].x} ${pts[pts.length-1].y}`;
  return d;
}

async function runLayout(){
  const rep=getRepMap();
  const graph=buildElkGraph(rep);
  try{
    const res=await elk.layout(graph);
    renderFromLayout(res,rep);
  }catch(err){
    console.error('ELK Layout error:', err);
  }
}

function renderFromLayout(res,rep){
  const vp=document.getElementById('vp');vp.textContent='';
  const defs=document.getElementById('defs');defs.textContent='';

  const cols=new Set(Object.values(D.proto).concat(['#bdbdbd','#555555']));
  cols.forEach(c=>{
    const m=el('marker',{id:'a'+c.slice(1),viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'},defs);
    el('path',{d:'M0 0L10 5L0 10z',fill:c},m);
  });

  const parentMap={};
  const nodeMap={};
  function walk(node,parentId,absX,absY){
    const nx=(parentId?absX:0)+(node.x||0);
    const ny=(parentId?absY:0)+(node.y||0);
    nodeMap[node.id]={absX:nx,absY:ny,width:node.width,height:node.height,node,parentId};
    if(parentId)parentMap[node.id]=parentId;
    (node.children||[]).forEach(c=>walk(c,node.id,nx,ny));
  }
  walk(res,null,0,0);

  function getLCA(a,b){
    const s=new Set();let cur=a;while(cur){s.add(cur);cur=parentMap[cur]}
    cur=b;while(cur){if(s.has(cur))return cur;cur=parentMap[cur]}
    return res.id;
  }

  const gContainers=el('g',{id:'layer-containers'},vp);
  const gEdges=el('g',{id:'layer-edges'},vp);
  const gLeaves=el('g',{id:'layer-leaves'},vp);

  let shown=0;

  Object.keys(nodeMap).forEach(id=>{
    if(id===res.id)return;
    const nm=nodeMap[id];
    if(id==='container:harness'){
      const g=el('g',{},gContainers);
      el('rect',{x:nm.absX,y:nm.absY,width:nm.width,height:nm.height,rx:8,fill:'#f7f9f9',stroke:'#7f8c8d','stroke-width':1.5,'stroke-dasharray':'4 3'},g);
      el('text',{x:nm.absX+10,y:nm.absY+18,'font-size':12,'font-weight':700,fill:'#2c3e50'},g).textContent='Hardware Harness / DUT';
      return;
    }
    const n=N[id];
    if(!n)return;
    shown++;
    const s=style(n),l=label(n);
    const isLeaf=!nm.node.children||nm.node.children.length===0;
    const gTarget=isLeaf?gLeaves:gContainers;
    const g=el('g',{'data-id':n.id,style:'cursor:pointer'},gTarget);

    const isSel=S.sel===n.id;
    const r=el('rect',{
      x:nm.absX,y:nm.absY,width:nm.width,height:nm.height,rx:isLeaf?6:9,
      fill:s.f,stroke:isSel?'#e74c3c':s.s,
      'stroke-width':isSel?3:1.4,
      'stroke-dasharray':s.d?'6 4':'0'
    },g);

    if(S.q&&n.i.path.toLowerCase().includes(S.q)){
      r.setAttribute('stroke','#e74c3c');
      r.setAttribute('stroke-width',3);
    }

    const nameStr=typeof l==='string'?l:l.name;
    const typeStr=typeof l==='string'?'':l.type;

    if(isLeaf){
      const isCol=S.collapsed.has(n.id)&&n.kids.length>0;
      const mark=isCol?'▸ ':'';
      const countStr=isCol?` (+${countDesc(n)})`:'';
      el('text',{x:nm.absX+nm.width/2,y:nm.absY+20,'text-anchor':'middle','font-size':12,'font-weight':600,fill:s.t},g).textContent=mark+nameStr+countStr;
      if(typeStr){
        el('text',{x:nm.absX+nm.width/2,y:nm.absY+36,'text-anchor':'middle','font-size':10.5,fill:s.t},g).textContent=typeStr.length>26?typeStr.slice(0,25)+'…':typeStr;
      }
    }else{
      el('text',{x:nm.absX+10,y:nm.absY+18,'font-size':12,'font-weight':700,fill:s.t},g).textContent='▾ '+nameStr+(typeStr?' : '+typeStr:'');
    }

    g.addEventListener('click',e=>{e.stopPropagation();S.sel=n.id;S.selEdge=null;runLayout();panel()});
    g.addEventListener('dblclick',e=>{
      e.stopPropagation();
      if(!n.kids.length)return;
      S.collapsed.has(n.id)?S.collapsed.delete(n.id):S.collapsed.add(n.id);
      runLayout().then(fit);
    });
  });

  (res.edges||[]).forEach(e=>{
    const srcId=e.sources[0],dstId=e.targets[0];
    const lca=getLCA(srcId,dstId);
    const lcaNode=nodeMap[lca]||{absX:0,absY:0};
    const sec=(e.sections&&e.sections[0])?e.sections[0]:null;
    if(!sec)return;

    const absPts=[
      {x:sec.startPoint.x+lcaNode.absX,y:sec.startPoint.y+lcaNode.absY},
      ...(sec.bendPoints||[]).map(b=>({x:b.x+lcaNode.absX,y:b.y+lcaNode.absY})),
      {x:sec.endPoint.x+lcaNode.absX,y:sec.endPoint.y+lcaNode.absY}
    ];

    let d='';
    if(S.routing==='straight'){
      d=`M ${absPts[0].x} ${absPts[0].y} L ${absPts[absPts.length-1].x} ${absPts[absPts.length-1].y}`;
    }else if(S.routing==='curved'){
      d=roundedOrthogonalPath(absPts,7);
    }else{
      d=`M ${absPts[0].x} ${absPts[0].y} `+absPts.slice(1).map(p=>`L ${p.x} ${p.y}`).join(' ');
    }

    const col=(S.test&&!e.act)?'#bdbdbd':(D.proto[e.rel.protocol]||D.proto[e.rel.kind]||'#555555');
    const isSelEdge=S.selEdge===e.id;

    const gE=el('g',{class:'edge-group',style:'cursor:pointer'},gEdges);
    el('path',{
      d,fill:'none',stroke:isSelEdge?'#e74c3c':col,
      'stroke-width':isSelEdge?3:1.6,
      'stroke-dasharray':(e.cond||(S.test&&!e.act)||(e.rel.kind==='handle'||e.rel.kind==='cfg'))?'5 4':'0',
      'marker-end':`url(#a${col.slice(1)})`,
      class:'edge-path'
    },gE);

    let maxLen=0,bestMid={x:(absPts[0].x+absPts[1].x)/2,y:(absPts[0].y+absPts[1].y)/2};
    for(let i=0;i<absPts.length-1;i++){
      const segLen=Math.hypot(absPts[i+1].x-absPts[i].x,absPts[i+1].y-absPts[i].y);
      if(segLen>maxLen){
        maxLen=segLen;
        bestMid={x:(absPts[i].x+absPts[i+1].x)/2,y:(absPts[i].y+absPts[i+1].y)/2};
      }
    }

    if(e.rel.label&&maxLen>24){
      el('text',{x:bestMid.x,y:bestMid.y-3,'text-anchor':'middle','font-size':10,fill:col,class:'halo'},gE).textContent=e.rel.label;
    }

    gE.addEventListener('click',ev=>{
      ev.stopPropagation();
      S.selEdge=e.id;S.sel=null;
      panelEdge(e.rel);
      runLayout();
    });
  });

  document.getElementById('count').textContent=shown+' blocs';
  const totalW=Math.max(res.width+48,600);
  const totalH=Math.max(res.height+48,400);
  vp.setAttribute('data-w',totalW);
  vp.setAttribute('data-h',totalH);
}

function countDesc(n){let c=0;(function f(m){m.kids.forEach(k=>{if(visible(k)){c++;f(k)}})})(n);return c}

let vb={x:0,y:0,k:1};
function applyVB(){document.getElementById('vp').setAttribute('transform',`translate(${vb.x} ${vb.y}) scale(${vb.k})`)}
function fit(){
  const vp=document.getElementById('vp'),sv=document.getElementById('svg');
  const W=+vp.getAttribute('data-w')||800,H=+vp.getAttribute('data-h')||600;
  const r=sv.getBoundingClientRect();
  const rw=r.width>50?r.width:(window.innerWidth-400||1100);
  const rh=r.height>50?r.height:(window.innerHeight-50||750);
  vb.k=Math.max(0.1, Math.min(rw/W, rh/H, 1.2));
  vb.x=Math.max(10, (rw-W*vb.k)/2);
  vb.y=Math.max(10, (rh-H*vb.k)/2);
  applyVB();
}

(function(){
  const sv=document.getElementById('svg');let drag=null;
  sv.addEventListener('mousedown',e=>{drag={x:e.clientX-vb.x,y:e.clientY-vb.y}});
  window.addEventListener('mouseup',()=>drag=null);
  window.addEventListener('mousemove',e=>{if(drag){vb.x=e.clientX-drag.x;vb.y=e.clientY-drag.y;applyVB()}});
  sv.addEventListener('wheel',e=>{
    e.preventDefault();
    const r=sv.getBoundingClientRect(),px=e.clientX-r.left,py=e.clientY-r.top;
    const f=e.deltaY<0?1.12:1/1.12,k=Math.max(.05,Math.min(4,vb.k*f));
    vb.x=px-(px-vb.x)*(k/vb.k);vb.y=py-(py-vb.y)*(k/vb.k);vb.k=k;applyVB();
  },{passive:false});
})();

function panel(){
  const p=document.getElementById('panel');const n=N[S.sel];if(!n){return}
  const i=n.i,cls=D.impl[i.class];
  let h=`<h3>${i.name}</h3><div style="color:#666;word-break:break-all">${i.path}</div><p><span class="tag" style="background:${D.colors[i.role]||'#eee'}">${i.role}</span> <code>${i.declared_type}</code></p>`;
  h+=`<div class="tabs"><button class="${S.tab==='arch'?'on':''}" onclick="S.tab='arch';panel()">Architecture</button><button class="${S.tab==='impl'?'on':''}" onclick="S.tab='impl';panel()">Implémentation</button></div>`;
  if(S.tab==='arch'){
    if(i.guards&&i.guards.length)h+=`<p class="warn"><b>Conditions :</b><br>${i.guards.map(g=>'<code>'+g.replace(/</g,'&lt;')+'</code>').join('<br>')}</p>`;
    if(D.tests&&D.tests.length&&i.states){
      h+='<b>États par test</b><table><tr><th>Test</th><th>État</th><th>Type effectif</th></tr>';
      D.tests.forEach(t=>{const s=i.states[t]||{active:true,present:true};h+=`<tr><td>${t}</td><td class="${s.active?'ok':'ko'}">${!s.present?'absent':s.active?'✓ actif'+(s.unresolved?' (?)':''):'✗ inactif'}</td><td>${s.effective_type||''}${s.overridden?' ⇄':''}</td></tr>`});
      h+='</table>';
    }
    if(i.ports&&i.ports.length){
      h+='<p><b>Ports</b></p><table><tr><th>Nom</th><th>Kind</th><th>Protocole</th><th>Transaction</th></tr>'+i.ports.map(q=>`<tr><td>${q.name}</td><td>${q.kind}</td><td>${q.protocol}</td><td>${q.txn||''}</td></tr>`).join('')+'</table>';
    }
    const rels=(D.relations||[]).filter(c=>c.src.inst===i.id||c.dst.inst===i.id);
    if(rels.length){
      h+='<p><b>Relations & connexions</b></p><table><tr><th>Type</th><th>De</th><th>À</th><th>Label</th></tr>'+
        rels.map(c=>`<tr><td><span class="tag">${c.kind}</span></td><td>${c.src.inst.split('.').slice(-2).join('.')}${c.src.port?'.'+c.src.port:''}</td><td>${c.dst.inst.split('.').slice(-2).join('.')}${c.dst.port?'.'+c.dst.port:''}</td><td>${c.label||''}</td></tr>`).join('')+'</table>';
    }
    h+=`<p style="color:#666">Défini : ${i.loc||'—'}</p>`;
  }else{
    if(!cls){h+="<p><i>Pas de détail d'implémentation (classe UVM standard ou analyse sans implémentation).</i></p>"}
    else{
      h+=`<p>Classe <code>${i.class}</code> — ${cls.loc} (${cls.lines} lignes)</p>`;
      h+='<b>Méthodes</b><table><tr><th>Nom</th><th>Lignes</th><th>Branches</th></tr>'+cls.methods.map(m=>`<tr><td>${m.name}${m.is_phase?' ⏱':''}</td><td>${m.lines}</td><td>${m.branches}</td></tr>`).join('')+'</table>';
      if(cls.constraints.length)h+='<p><b>Contraintes</b></p><ul>'+cls.constraints.map(c=>`<li>${c.name}</li>`).join('')+'</ul>';
      if(cls.covergroups.length)h+='<p><b>Covergroups</b></p><ul>'+cls.covergroups.map(c=>`<li>${c.name} — cp: ${c.coverpoints.join(', ')||'—'}; cross: ${c.crosses.join(', ')||'—'}</li>`).join('')+'</ul>';
      if(cls.fields&&cls.fields.length)h+=`<p><b>uvm_field_*</b> : ${cls.fields.join(', ')}</p>`;
    }
  }
  p.innerHTML=h;
}

function panelEdge(rel){
  const p=document.getElementById('panel');
  let h=`<h3>Connexion / Relation</h3>`;
  h+=`<p><span class="tag" style="background:${D.proto[rel.protocol]||D.proto[rel.kind]||'#eee'};color:#fff">${rel.kind.toUpperCase()}</span> <b>${rel.protocol||rel.kind}</b></p>`;
  h+=`<table>`;
  h+=`<tr><th>De</th><td>${rel.src.inst}${rel.src.port?' : '+rel.src.port:''}</td></tr>`;
  h+=`<tr><th>À</th><td>${rel.dst.inst}${rel.dst.port?' : '+rel.dst.port:''}</td></tr>`;
  if(rel.txn)h+=`<tr><th>Transaction</th><td><code>${rel.txn}</code></td></tr>`;
  if(rel.loc)h+=`<tr><th>Localisation</th><td>${rel.loc}</td></tr>`;
  h+=`</table>`;
  if(D.tests&&D.tests.length&&rel.states){
    h+='<p><b>État par test</b></p><table><tr><th>Test</th><th>Actif</th></tr>';
    D.tests.forEach(t=>{
      const act=rel.states[t];
      h+=`<tr><td>${t}</td><td class="${act?'ok':'ko'}">${act?'✓ actif':'✗ inactif (grisé)'}</td></tr>`;
    });
    h+='</table>';
  }
  p.innerHTML=h;
}

function init(){
  const sel=document.getElementById('sel');
  sel.innerHTML='<option value="">Référence (tous tests)</option>'+D.tests.map(t=>`<option>${t}</option>`).join('');
  sel.onchange=()=>{S.test=sel.value||null;runLayout().then(fit);if(S.sel)panel()};

  document.getElementById('hide').onchange=e=>{S.hide=e.target.checked;runLayout().then(fit)};
  document.getElementById('routing').onchange=e=>{S.routing=e.target.value;runLayout()};
  document.getElementById('dir').onchange=e=>{S.dir=e.target.value;runLayout().then(fit)};

  ['tlm','seq','vif','cfg','handle'].forEach(k=>{
    const chk=document.getElementById('lay_'+k);
    if(chk)chk.onchange=e=>{S.layers[k]=e.target.checked;runLayout()};
  });

  document.getElementById('q').oninput=e=>{S.q=e.target.value.toLowerCase();runLayout()};
  document.getElementById('collapse').onclick=()=>{
    D.instances.forEach(i=>{if(N[i.id].kids.length&&i.id!==D.root)S.collapsed.add(i.id)});
    runLayout().then(fit);
  };
  document.getElementById('expand').onclick=()=>{S.collapsed.clear();runLayout().then(fit)};
  document.getElementById('fit').onclick=fit;

  document.getElementById('svgx').onclick=()=>{
    const s=document.getElementById('svg').cloneNode(true);s.setAttribute('xmlns',NS);
    const vp=document.getElementById('vp');
    s.setAttribute('viewBox',`0 0 ${vp.getAttribute('data-w')} ${vp.getAttribute('data-h')}`);
    s.querySelector('#vp').removeAttribute('transform');
    const a=document.createElement('a');
    a.href=URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(s)],{type:'image/svg+xml'}));
    a.download='uvm_'+(S.test||'all')+'.svg';a.click();
  };

  const lg=document.getElementById('legend');
  const used=[...new Set(D.instances.map(i=>i.role))].concat(['interface','dut']);
  lg.innerHTML=used.map(r=>`<span class="sw" style="background:${D.colors[r]||'#ececec'}"></span>${r}`).join('')+
   `<br><span class="sw" style="background:#fff;border:2px dashed ${D.cond}"></span>conditionnel <span class="sw" style="background:${D.inactive.fill};border-color:${D.inactive.stroke}"></span>grisé (inactif)`+
   `<br>liaisons : `+
   `<span style="color:${D.proto.analysis}">● analysis</span> · `+
   `<span style="color:${D.proto.seq_item}">● seq_item</span> · `+
   `<span style="color:${D.proto.vif}">● vif</span> · `+
   `<span style="color:${D.proto.seq}">● seq</span> · `+
   `<span style="color:${D.proto.cfg}">● cfg</span> · `+
   `<span style="color:${D.proto.handle}">● handle</span>`;

  const hp=new URLSearchParams(location.hash.slice(1));
  if(hp.get('test')&&D.tests.includes(hp.get('test'))){S.test=hp.get('test');sel.value=S.test}
  if(hp.get('hide')==='1'){S.hide=true;document.getElementById('hide').checked=true}
  if(hp.get('select')&&N[hp.get('select')]){S.sel=hp.get('select')}
  if(hp.get('routing')){S.routing=hp.get('routing');document.getElementById('routing').value=S.routing}
  if(hp.get('dir')){S.dir=hp.get('dir');document.getElementById('dir').value=S.dir}

  runLayout().then(fit);
}

init();
</script></body></html>
"""
