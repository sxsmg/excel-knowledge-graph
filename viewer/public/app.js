/* global vis, NeoVis */
let viz, cfg;

// ––––– INIT –––––
(async function init () {
  cfg = await fetch("/config").then(r => r.json());
  const config = {
    containerId : "viz",
    neo4j       : { serverUrl:cfg.uri, serverUser:cfg.user, serverPassword:cfg.password },
    initialCypher : "MATCH (n)-[r:DEPENDS_ON]->(m) RETURN n,r,m",
    labels : { entity:{caption:"name"} },
    relationships : { DEPENDS_ON:{} }
  };
  viz = new NeoVis.default(config);
  viz.render();
})();

// ––––– HELPERS –––––
const $ = sel => document.querySelector(sel);
const ask  = () => nlCall("/ask"   , $("#q").value.trim());
const exec = () => nlCall("/update", $("#q").value.trim());

async function nlCall (endpoint, prompt){
  if(!prompt) return;
  $("#answer").textContent = "⏳ thinking…";
  const res   = await fetch(endpoint,{method:"POST",headers:{'Content-Type':'application/json'},body:JSON.stringify({question:prompt})}).then(r=>r.json());
  $("#answer").textContent = res.answer || res.detail || "✅ done";
  // if it was an update → pull fresh sub-graph
  if(endpoint==="/update") viz.updateWithCypher("MATCH (n)-[r:DEPENDS_ON]->(m) RETURN n,r,m");
}

// ––––– EVENTS –––––
$("#ask").addEventListener("click",  ask);
$("#update").addEventListener("click",exec);
$("#q").addEventListener("keydown",e=>{ if(e.key==="Enter") ask(); });
