import json
from pathlib import Path

import pytest

from peacook.pipeline import analyze
from peacook.render import drawio, graphviz, html, jsonviews, markdown, mermaid
from peacook.render.common import View
from peacook.render.output import write_all

FIX = Path(__file__).parent / "fixtures" / "bridge_tb" / "files.f"


@pytest.fixture(scope="session")
def res():
    return analyze(filelist=str(FIX))


@pytest.fixture(scope="session")
def env(res):
    return res.arch["environment"]


def inst(env, suffix):
    return next(i for i in env["instances"] if i["path"] == f"uvm_test_top.{suffix}")


def test_tests_discovered(env):
    assert set(env["tests"]) == {"bridge_base_test", "bridge_smoke_test", "bridge_err_test",
                                 "bridge_multi_out_test", "bridge_passive_test"}


def test_roles(res):
    roles = {c["name"]: c["role"] for c in res.arch["classes"]}
    assert roles["bridge_env"] == "env" and roles["bridge_vseqr"] == "virtual_sequencer"
    assert roles["bridge_smoke_vseq"] == "virtual_sequence" and roles["apb_cfg"] == "config"
    assert roles["bridge_ref_model"] == "ref_model" and roles["stream_agent"] == "agent"


def test_condition_resolved_from_environment(env):
    drv = inst(env, "env.apb_agt.drv")
    assert drv["states"]["bridge_smoke_test"]["active"] is True
    assert drv["states"]["bridge_passive_test"]["active"] is False       # cfg modifiée par le test
    assert drv["conditional"] and drv["guards"] == ["cfg.is_active == UVM_ACTIVE"]
    # get_is_active() déduit des config_db::set de l'env (out_agt_* passifs)
    assert inst(env, "env.out_agt_0.drv")["always_inactive"] is True
    assert inst(env, "env.in_agt.drv")["states"]["bridge_smoke_test"]["active"] is True


def test_conditions_on_env_cfg(env):
    ref = inst(env, "env.ref_model")
    assert ref["states"]["bridge_smoke_test"]["active"] and not ref["states"]["bridge_passive_test"]["active"]
    cov = inst(env, "env.cov")
    assert not cov["states"]["bridge_passive_test"]["active"]


def test_array_expansion_depends_on_test(env):
    a3 = inst(env, "env.out_agt_3")
    assert a3["states"]["bridge_multi_out_test"]["active"]
    assert not a3["states"]["bridge_smoke_test"]["present"]
    assert inst(env, "env.out_agt_1")["states"]["bridge_smoke_test"]["present"]


def test_factory_override_only_in_err_test(env):
    drv = inst(env, "env.in_agt.drv")
    assert drv["states"]["bridge_err_test"]["effective_type"] == "stream_err_driver"
    assert drv["states"]["bridge_smoke_test"]["effective_type"] == "stream_driver"
    assert drv["overridden_in"] == ["bridge_err_test"]


def test_flat_connections(env):
    pairs = {(c["from"]["inst"][5:], c["to"]["inst"][5:]) for c in env["flat_connections"]}
    assert ("uvm_test_top.env.in_agt.mon", "uvm_test_top.env.ref_model.in_fifo") in pairs
    assert ("uvm_test_top.env.apb_agt.mon", "uvm_test_top.env.cov") in pairs      # via le port promu de l'agent
    assert ("uvm_test_top.env.out_agt_0.mon", "uvm_test_top.env.sb") in pairs
    assert ("uvm_test_top.env.apb_agt.drv", "uvm_test_top.env.apb_agt.sqr") in pairs
    txn = {c["txn"] for c in env["flat_connections"] if c["protocol"] == "analysis"}
    assert txn == {"apb_item", "stream_item"}


def test_connection_grayed_with_inactive_endpoint(env):
    c = next(c for c in env["flat_connections"] if c["to"]["inst"].endswith("env.cov"))
    assert c["states"]["bridge_smoke_test"] and not c["states"]["bridge_passive_test"]


def test_sequences_and_handles(env):
    runs = {(r["seq_name"], r["on"]) for r in env["sequences"]}
    assert ("bridge_smoke_vseq", "inst:uvm_test_top.env.vseqr") in runs
    assert ("apb_cfg_seq", "inst:uvm_test_top.env.apb_agt.sqr") in runs
    assert ("stream_seq", "inst:uvm_test_top.env.in_agt.sqr") in runs
    links = {(l["handle"], l["target"][5:]) for l in env["handle_links"]}
    assert ("apb_sqr", "uvm_test_top.env.apb_agt.sqr") in links


def test_config_db_matching(env):
    sets = {s["field"]: s for s in env["config_db"]["sets"]}
    assert sets["debug_level"]["status"] == "orphan_set"
    assert sets["cfg"]["status"] == "ok"
    assert all(g["status"] == "ok" for g in env["config_db"]["gets"])


def test_lint_codes(res):
    codes = {d["code"] for d in res.arch["diagnostics"]}
    assert "CONFIG_DB_ORPHAN_SET" in codes
    assert "CONFIG_DB_UNMATCHED_GET" not in codes


def test_harness(res):
    top = res.arch["harness"]["tops"][0]
    assert top["name"] == "tb_top" and top["duts"][0]["type"] == "bridge_dut"
    assert {i["type"] for i in top["interfaces"]} == {"apb_if", "stream_if"}
    vif = next(v for v in top["vif_sets"] if v["interface_instance"] == "apb_vif")
    assert any(c.endswith("apb_agt.mon") for c in vif["consumers"])


def test_implementation_layer_is_separate_but_linked(res):
    impl = {c["name"]: c for c in res.impl["classes"]}
    assert impl["apb_item"]["constraints"][0]["name"] == "c_align"
    assert impl["apb_monitor"]["covergroups"][0]["crosses"]
    assert impl["apb_item"]["arch_ref"] == "class:apb_item"
    assert any(c["impl_ref"] == "impl:apb_item" for c in res.arch["classes"])
    assert "constraints" not in res.arch["classes"][0]       # rien d'implémentation côté architecture


def test_same_geometry_for_all_tests(res):
    """Le schéma de référence et les schémas par test contiennent exactement les mêmes blocs."""
    ref = mermaid.block(View(res.arch, None))
    for t in res.arch["environment"]["tests"]:
        txt = mermaid.block(View(res.arch, t))
        nodes = lambda s: sorted(l.split("[")[0].strip() for l in s.splitlines() if '["' in l)
        assert nodes(txt) == nodes(ref)
    assert "fill:#f0f0f0" in mermaid.block(View(res.arch, "bridge_passive_test"))


def test_hide_inactive_removes_gray(res):
    full = mermaid.block(View(res.arch, "bridge_passive_test"))
    hid = mermaid.block(View(res.arch, "bridge_passive_test", hide_inactive=True))
    assert len(hid) < len(full) and "fill:#f0f0f0" not in hid and "ref_model" not in hid


def test_renderers_outputs(res, tmp_path):
    files = write_all(res, str(tmp_path))
    names = {f.name for f in files}
    assert {"index.html", "architecture.json", "implementation.json", "block.drawio", "report.md"} <= names
    page = (tmp_path / "index.html").read_text(encoding="utf-8")
    assert "http://" not in page.replace("http://www.w3.org/2000/svg", "") and "https://" not in page
    data = json.loads(page.split('type="application/json">')[1].split("</script>")[0].replace("<\\/", "</"))
    assert len(data["instances"]) == len(res.arch["environment"]["instances"])
    import xml.dom.minidom as md
    doc = md.parseString((tmp_path / "architecture/views/block.drawio").read_text(encoding="utf-8"))
    assert len(doc.getElementsByTagName("diagram")) == 1 + 5
    assert (tmp_path / "implementation/classes/apb_item.md").exists()
    dot = graphviz.block(View(res.arch, None))
    assert dot.count("subgraph cluster_") >= 5 and dot.rstrip().endswith("}")
    assert "[" in (tmp_path / "architecture/views/hierarchy.json").read_text(encoding="utf-8")


def test_compact_json_views(res):
    h = jsonviews.hierarchy(res.arch)
    assert h["root"]["name"] == "uvm_test_top" and "children" in h["root"]
    conns = jsonviews.connections(res.arch)["connections"]
    assert all({"from", "to", "protocol"} <= set(c) for c in conns)
    assert "producers" in jsonviews.dataflow(res.arch)["transactions"][0]


# ----------------------------------------------------------------- relations (étape 1)
def rels(env, kind):
    return [r for r in env["relations"] if r["kind"] == kind]


def short(x):
    if not x["inst"].startswith("inst:"):
        return x["inst"]
    p = x["inst"].split(":", 1)[1]
    if p == "uvm_test_top":
        return "TEST"
    return p.replace("uvm_test_top.", "")


def test_relation_kinds_present(env):
    kinds = {r["kind"] for r in env["relations"]}
    assert {"tlm", "hier", "seq", "vif", "cfg", "handle"} <= kinds
    assert all(set(r["states"]) == set(env["tests"]) for r in env["relations"])


def test_tlm_relations_hide_dead_end_promoted_port(env):
    pairs = {(short(r["src"]), short(r["dst"])) for r in rels(env, "tlm")}
    assert ("env.in_agt.mon", "env.in_agt") not in pairs               # port promu sans suite
    assert ("env.in_agt.mon", "env.ref_model.in_fifo") in pairs
    # ... mais il reste visible dans le calque des ports promus
    hier = {(short(r["src"]), short(r["dst"])) for r in rels(env, "hier")}
    assert ("env.in_agt.mon", "env.in_agt") in hier
    assert len(rels(env, "hier")) == len(env["connections"])


def test_fifo_consumption_relation(env):
    r = [r for r in rels(env, "tlm") if r["implicit"]]
    assert [(short(x["src"]), short(x["dst"])) for x in r] == [("env.ref_model.in_fifo", "env.ref_model")]


def test_sequence_relations(env):
    seq = {(short(r["src"]), short(r["dst"]), r["label"]): r for r in rels(env, "seq")}
    assert ("TEST", "env.vseqr", "bridge_smoke_vseq") in seq
    assert ("env.vseqr", "env.apb_agt.sqr", "apb_cfg_seq") in seq
    assert ("env.vseqr", "env.in_agt.sqr", "stream_seq") in seq
    apb = seq[("env.vseqr", "env.apb_agt.sqr", "apb_cfg_seq")]
    assert apb["states"]["bridge_smoke_test"] and not apb["states"]["bridge_passive_test"]   # sqr passif => grisé
    assert not apb["states"]["bridge_base_test"]                       # séquence lancée seulement par les tests dérivés


def test_vif_and_dut_relations(env):
    vif = {(r["src"]["inst"], short(r["dst"]), r["label"]) for r in rels(env, "vif")}
    assert ("if:apb_vif", "env.apb_agt.mon", "vif") in vif
    assert ("if:apb_vif", "env.apb_agt.drv", "vif") in vif
    assert ("if:in_vif", "env.in_agt.mon", "vif") in vif
    assert any(s == "if:apb_vif" and d == "dut:dut" for s, d, _ in vif)
    names = {n["id"]: n["kind"] for n in env["harness_nodes"]}
    assert names["if:apb_vif"] == "interface" and names["dut:dut"] == "dut"


def test_config_relations_exclude_vif_and_follow_state(env):
    cfg = {(short(r["src"]), short(r["dst"]), r["label"]): r for r in rels(env, "cfg")}
    assert ("TEST", "env", "cfg") in cfg
    assert ("TEST", "env.apb_agt", "cfg") in cfg
    assert not any(l == "vif" for _, _, l in cfg)
    assert cfg[("TEST", "env.apb_agt", "cfg")]["states"]["bridge_smoke_test"]


def test_handle_relations(env):
    h = {(short(r["src"]), short(r["dst"]), r["label"]) for r in rels(env, "handle")}
    assert ("env.vseqr", "env.apb_agt.sqr", "apb_sqr") in h


def test_default_sequence_relation_via_config_db(env):
    r = [x for x in rels(env, "seq") if x["label"] == "stream_seq (default)"]
    assert [(short(x["src"]), short(x["dst"])) for x in r] == [("TEST", "env.in_agt.sqr")]
    st = r[0]["states"]
    assert st["bridge_err_test"] and not st["bridge_smoke_test"]


def test_html_embedded_elk_and_offline(res):
    page = html.build(res.arch, res.impl)
    # Vérification stricte hors ligne (zéro dépendance CDN / HTTP distante)
    assert "http://" not in page.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in page
    # Présence d'ELK.js embarqué dans la page
    assert "new ELK()" in page
    assert "elk.bundled" in page or "ELK" in page
    data = json.loads(page.split('type="application/json">')[1].split("</script>")[0])
    assert "relations" in data and len(data["relations"]) >= 50
    assert "harness" in data and len(data["harness"]) >= 5


def test_html_elk_layout_execution_headless(res, tmp_path):
    import subprocess, shutil
    edge = shutil.which("msedge") or r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if not Path(edge).exists():
        pytest.skip("msedge introuvable pour test headless")
    page = html.build(res.arch, res.impl)
    p = tmp_path / "elk_view.html"
    p.write_text(page, encoding="utf-8")
    cmd = [edge, "--headless", "--disable-gpu", "--dump-dom", f"file:///{p.resolve().as_posix()}"]
    run = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace", timeout=25)
    assert run.returncode == 0
    assert 'id="layer-edges"' in run.stdout
    assert 'id="layer-leaves"' in run.stdout
    assert 'class="edge-path"' in run.stdout
    assert "JS ERROR" not in run.stdout

