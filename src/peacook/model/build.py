"""Assemblage des modèles `architecture` et `implementation` (JSON) à partir des topologies par test."""
from __future__ import annotations

import re
from collections import OrderedDict

from .. import __version__
from ..resolve.values import glob_match
from ..elaborate.topology import Topology
from ..extract import textutil as tu
from ..extract.facts import Facts
from ..resolve import uvm_kb as kb
from ..resolve.types import TypeModel, base_name

SCHEMA_VERSION = "1.0"


def iid(path: str) -> str:
    return f"inst:{path}"


def cid(name: str) -> str:
    return f"class:{name}"


# ---------------------------------------------------------------- classes
def class_entries(tm: TypeModel, f: Facts) -> list[dict]:
    out = []
    for name, c in f.classes.items():
        chain = tm.chain(name)
        children = []
        for mname in ("build_phase", "new"):
            for _, m in tm.method_chain(name, mname)[:1]:
                for o in tu.iter_ops(m["ops"]):
                    if o["op"] == "create" and o.get("parent"):
                        typ = o["type"] or (tm.all_members(name).get(o["var"].split("[")[0]) or {}).get("type")
                        if typ and not tm.is_port_type(typ):
                            children.append({"member": o["var"], "type": typ, "name": o["name"], "loc": o["loc"]})
        ports = tm.ports(name)
        role = tm.role(name)
        entry = {
            "id": cid(name), "name": name, "package": c.package, "base": c.base, "base_chain": chain[1:],
            "role": role, "params": c.params, "loc": c.loc,
            "ports": [{"name": k, **v} for k, v in ports.items()],
            "children": children,
            "config_members": [{"name": k, "type": m["type"]} for k, m in c.members.items()
                               if tm.role(m["type"]) == "config" or k in ("cfg", "m_cfg", "config")],
            "handles": [{"name": k, "type": m["type"]} for k, m in c.members.items()
                        if tm.role(m["type"]) in ("sequencer", "virtual_sequencer") and tm.is_component(m["type"])],
            "vifs": [{"name": k, "type": m["type"]} for k, m in c.members.items() if m["type"].startswith("virtual")],
            "impl_ref": f"impl:{name}",
        }
        if role in ("sequence", "virtual_sequence"):
            entry["item"] = tm.txn_of_seq(name)
            entry["p_sequencer"] = next((f.classes[x].p_sequencer for x in chain
                                         if x in f.classes and f.classes[x].p_sequencer), None)
        if role in ("sequencer", "virtual_sequencer"):
            entry["item"] = tm.item_of_sequencer(name)
        out.append(entry)
    return out


# ------------------------------------------------------------ fusion env
def merge_env(topos: "OrderedDict[str, Topology]", tm: TypeModel, f: Facts) -> dict:
    tests = list(topos)
    insts: "OrderedDict[str, dict]" = OrderedDict()
    for t, top in topos.items():
        for p, i in top.insts.items():
            rec = insts.get(p)
            if rec is None:
                ports = tm.ports(i.effective)
                rec = insts[p] = {
                    "id": iid(p), "path": p, "name": i.name, "parent": iid(i.parent) if i.parent else None,
                    "declared_type": i.declared if p != "uvm_test_top" else "uvm_test", "role": i.role,
                    "class": i.cls, "loc": i.loc, "guards": [], "array": i.array,
                    "ports": [{"name": k, **v} for k, v in ports.items()], "states": {},
                    "impl_ref": f"impl:{i.cls}" if i.cls in f.classes else None,
                }
            for g in i.guards:
                if g not in rec["guards"]:
                    rec["guards"].append(g)
            rec["states"][t] = {"present": True, "active": bool(i.active), "unresolved": bool(i.unresolved),
                                "effective_type": base_name(i.effective) if "#" not in i.effective else
                                tu.squash(i.effective),
                                "overridden": bool(i.override)}
    for rec in insts.values():
        for t in tests:
            rec["states"].setdefault(t, {"present": False, "active": False, "unresolved": False,
                                         "effective_type": None, "overridden": False})
        sts = list(rec["states"].values())
        rec["conditional"] = bool(rec["guards"]) or len({(s["present"], s["active"]) for s in sts}) > 1 \
            or any(s["unresolved"] for s in sts)
        rec["always_inactive"] = not any(s["active"] for s in sts)
        rec["overridden_in"] = [t for t, s in rec["states"].items() if s["overridden"]]

    # connexions
    conns: "OrderedDict[tuple, dict]" = OrderedDict()
    for t, top in topos.items():
        for c in top.conns:
            key = (c["src"]["inst"], c["src"]["port"], c["dst"]["inst"], c["dst"]["port"])
            rec = conns.get(key)
            if rec is None:
                si = top.insts.get(c["src"]["inst"])
                pinfo = (tm.ports(si.effective).get((c["src"]["port"] or "").split(".")[0]) if si else None) or {}
                di = top.insts.get(c["dst"]["inst"])
                pinfo2 = (tm.ports(di.effective).get((c["dst"]["port"] or "").split(".")[0]) if di else None) or {}
                rec = conns[key] = {
                    "id": f"conn:{key[0]}.{key[1]}->{key[2]}.{key[3]}",
                    "src": {"inst": iid(key[0]), "port": key[1]}, "dst": {"inst": iid(key[2]), "port": key[3]},
                    "protocol": pinfo.get("protocol") or pinfo2.get("protocol") or "tlm",
                    "txn": pinfo.get("txn") or pinfo2.get("txn"), "loc": c["loc"], "states": {}}
            rec["states"][t] = bool(c["active"])
    for rec in conns.values():
        for t in tests:
            rec["states"].setdefault(t, False)

    # liens de handles de séquenceurs
    links: "OrderedDict[tuple, dict]" = OrderedDict()
    for t, top in topos.items():
        for l in top.links:
            key = (l["owner"], l["handle"], l["target"])
            rec = links.setdefault(key, {"owner": iid(l["owner"]), "handle": l["handle"], "target": iid(l["target"]),
                                         "states": {}})
            ti, oi = top.insts.get(l["target"]), top.insts.get(l["owner"])
            rec["states"][t] = bool(ti and oi and ti.active and oi.active)
    for rec in links.values():
        for t in tests:
            rec["states"].setdefault(t, False)

    flat = merge_flat(topos, tm)
    cfg = merge_cfg(topos, tm, f, insts)
    seqs = merge_sequences(topos, tm, f)
    return {
        "root": iid("uvm_test_top"), "tests": tests, "instances": list(insts.values()),
        "connections": list(conns.values()), "flat_connections": flat, "handle_links": list(links.values()),
        "config_db": cfg, "sequences": seqs,
        "factory_overrides": {t: top.applied_overrides for t, top in topos.items()},
    }


# ------------------------------------------------------ connexions aplaties
def flat_for(top: Topology, tm: TypeModel) -> list[dict]:
    adj: dict[tuple, list] = {}
    incoming = set()
    for c in top.conns:
        a, b = (c["src"]["inst"], c["src"]["port"]), (c["dst"]["inst"], c["dst"]["port"])
        adj.setdefault(a, []).append((b, c))
        incoming.add(b)
    res = []

    def walk(node, root, via, active, seen):
        nxt = adj.get(node, [])
        if not nxt:
            if via:
                res.append((root, node, list(via), active))
            return
        for b, c in nxt:
            if b in seen:
                continue
            walk(b, root, via + [node], active and c["active"], seen | {b})

    for a in list(adj):
        if a not in incoming:
            walk(a, a, [], True, {a})
    return [{"from": r, "to": t, "via": v, "active": act} for r, t, v, act in res]


def merge_flat(topos, tm: TypeModel) -> list[dict]:
    out: "OrderedDict[tuple, dict]" = OrderedDict()
    tests = list(topos)
    for t, top in topos.items():
        for fc in flat_for(top, tm):
            key = (fc["from"], fc["to"])
            rec = out.get(key)
            if rec is None:
                si = top.insts.get(fc["from"][0])
                pinfo = (tm.ports(si.effective).get((fc["from"][1] or "").split(".")[0]) if si else None) or {}
                rec = out[key] = {"from": {"inst": iid(key[0][0]), "port": key[0][1]},
                                  "to": {"inst": iid(key[1][0]), "port": key[1][1]},
                                  "via": [iid(v[0]) for v in fc["via"][1:]], "protocol": pinfo.get("protocol", "tlm"),
                                  "txn": pinfo.get("txn"), "states": {}}
            rec["states"][t] = bool(fc["active"])
    for rec in out.values():
        for t in tests:
            rec["states"].setdefault(t, False)
    return list(out.values())


# ----------------------------------------------------------------- config_db
def merge_cfg(topos, tm: TypeModel, f: Facts, insts: dict) -> dict:
    sets: "OrderedDict[tuple, dict]" = OrderedDict()
    gets: "OrderedDict[tuple, dict]" = OrderedDict()
    for t, top in topos.items():
        seq2key = {}
        for s in top.cfg_sets:
            key = (s["setter"], s["pattern"], s["field"], s["type"])
            seq2key[s["seq"]] = key
            rec = sets.setdefault(key, {
                "id": "cfgset:" + "|".join(str(k) for k in key), "setter": iid(s["setter"]) if s["setter"] else None,
                "setter_class": s["setter_class"] or None, "pattern": s["pattern"], "field": s["field"],
                "type": s["type"], "loc": s["loc"], "values": {}, "consumers": []})
            rec["values"][t] = s["value"]
        for g in top.cfg_gets:
            key = (g["getter"], g["field"], g["type"])
            rec = gets.setdefault(key, {"id": "cfgget:" + "|".join(key), "getter": iid(g["getter"]),
                                        "getter_class": g["getter_class"], "field": g["field"], "type": g["type"],
                                        "loc": g["loc"], "setters": []})
            if g["matched"] is not None:
                sk = seq2key[g["matched"]]
                sid = sets[sk]["id"]
                if sid not in rec["setters"]:
                    rec["setters"].append(sid)
                if rec["getter"] not in sets[sk]["consumers"]:
                    sets[sk]["consumers"].append(rec["getter"])
    # consommation implicite (is_active lu par get_is_active des agents, champs UVM natifs,
    # champs lus par get dans une classe non instanciée (séquence) ou par automatisation uvm_field_*)
    read_fields: set[str] = set()
    auto_fields: set[str] = set()
    for c in f.classes.values():
        auto_fields.update(c.fields_macro)
        for m in c.methods.values():
            for o in tu.iter_ops(m["ops"]):
                if o["op"] == "cfg" and o["kind"] == "get":
                    read_fields.add(tu.strip_quotes(o["field"]))
    for s in sets.values():
        if s["consumers"]:
            continue
        if s["field"] in ("default_sequence", "recording_detail", "count", "max_quit_count", "uvm_test_top"):
            s["implicit"] = "champ UVM natif"
        elif s["field"] in auto_fields:
            s["implicit"] = "lu par automatisation uvm_field_*"
        elif s["field"] == "is_active":
            for p, rec in insts.items():
                if rec["role"] == "agent" and glob_match(s["pattern"], p):
                    s["implicit"] = "lu par get_is_active()"
                    if rec["id"] not in s["consumers"]:
                        s["consumers"].append(rec["id"])
        elif s["field"] in read_fields:
            s["implicit"] = "lu par un get dans une classe non instanciée (séquence, objet)"
    for s in sets.values():
        s["status"] = "ok" if (s["consumers"] or s.get("implicit")) else "orphan_set"
    for g in gets.values():
        g["status"] = "ok" if g["setters"] else "unmatched_get"
    return {"sets": list(sets.values()), "gets": list(gets.values())}


# ----------------------------------------------------------------- séquences
def _body_info(tm: TypeModel, f: Facts, cname: str):
    types: dict[str, str] = {}
    starts = []
    for cn, m in tm.method_chain(cname, "body")[:1]:
        for o in tu.iter_ops(m["ops"]):
            if o["op"] == "localdecl" and o["type"]:
                types[o["var"]] = o["type"]
            elif o["op"] == "create" and o.get("type") and not o.get("parent"):
                types[o["var"]] = o["type"]
            elif o["op"] == "start":
                starts.append({"seq_var": o["seq"], "on": o["on"], "loc": o["loc"], "via": "start"})
    for cn in tm.chain(cname):
        c = f.classes.get(cn)
        if c:
            for rs in c.raw_starts:
                starts.append({"seq_var": rs["seq"], "on": rs["on"], "loc": c.loc, "via": "macro"})
    return types, starts


def _resolve_on(expr, on_path, top: Topology):
    e = (expr or "").strip()
    if e.startswith("p_sequencer") or e.startswith("m_sequencer"):
        rest = re.sub(r"^(p_sequencer|m_sequencer)\.?", "", e)
        if not rest:
            return on_path
        for l in top.links:
            if l["owner"] == on_path and l["handle"] == rest:
                return l["target"]
        p = f"{on_path}.{rest}"
        return p if p in top.insts else None
    return None


def sequence_runs(top: Topology, tm: TypeModel, f: Facts) -> list[dict]:
    runs: list[dict] = []

    def expand(seq_type, on_path, by, loc, depth, parent):
        rid = len(runs)
        runs.append({"seq": seq_type, "on": on_path, "started_by": by, "loc": loc, "depth": depth, "parent": parent})
        if depth >= 6 or seq_type not in f.classes:
            return
        types, starts = _body_info(tm, f, seq_type)
        for s in starts:
            st = types.get(s["seq_var"].split(".")[0])
            if not st:
                continue
            target = _resolve_on(s["on"], on_path, top)
            expand(tm.resolve(st)[0], target, seq_type, s["loc"], depth + 1, rid)

    for s in top.starts:
        expand(s["seq"], s["on"], s["by"], s["loc"], 0, None)
    return runs


def merge_sequences(topos, tm: TypeModel, f: Facts) -> list[dict]:
    out: "OrderedDict[tuple, dict]" = OrderedDict()
    for t, top in topos.items():
        for r in sequence_runs(top, tm, f):
            key = (r["seq"], r["on"], r["started_by"])
            rec = out.setdefault(key, {
                "seq": cid(r["seq"]), "seq_name": r["seq"], "item": tm.txn_of_seq(r["seq"]),
                "on": iid(r["on"]) if r["on"] else None, "started_by": iid(r["started_by"]) if r["started_by"] in top.insts
                else cid(r["started_by"]), "loc": r["loc"], "depth": r["depth"], "tests": []})
            if t not in rec["tests"]:
                rec["tests"].append(t)
    return list(out.values())


# ------------------------------------------------------------------ harnais
def harness(f: Facts, tm: TypeModel, env: dict) -> dict:
    mods = f.modules
    instantiated = {i["type"] for m in mods.values() for i in m.instances}
    tops = [m for m in mods.values() if m.kind == "module" and (m.run_test is not None or m.name not in instantiated)]
    tops.sort(key=lambda m: (m.run_test is None, m.name))
    result = {"tops": []}
    for top in tops[:3]:
        ifaces, duts = [], []
        by_name = {}
        for i in top.instances:
            mt = mods.get(i["type"])
            kind = mt.kind if mt else None
            by_name[i["name"]] = i
            if kind == "interface":
                ifaces.append({"name": i["name"], "type": i["type"], "modports": mt.modports, "signals": mt.signals,
                               "loc": i["loc"]})
            elif kind in ("module", None):
                duts.append({"name": i["name"], "type": i["type"], "ports": i["ports"] or
                             {str(n): v for n, v in enumerate(i["ordered"])}, "loc": i["loc"]})
        vif_sets = []
        for s in env["config_db"]["sets"]:
            if s["setter"] is None and s["type"].startswith("virtual"):
                val = next(iter(s["values"].values()), None)
                inst = by_name.get(val)
                vif_sets.append({"field": s["field"], "type": s["type"], "pattern": s["pattern"],
                                 "interface_instance": val, "interface_type": inst["type"] if inst else None,
                                 "consumers": s["consumers"], "set_id": s["id"], "loc": s["loc"]})
        for d in duts:
            d["interfaces"] = sorted({v for v in d["ports"].values() if v in by_name and
                                      any(x["name"] == v for x in ifaces)})
        result["tops"].append({"name": top.name, "run_test": top.run_test, "loc": top.loc, "interfaces": ifaces,
                               "duts": duts, "vif_sets": vif_sets})
    return result


# ------------------------------------------------------------- implémentation
def implementation(f: Facts, tm: TypeModel) -> dict:
    classes = []
    for name, c in f.classes.items():
        methods = []
        for mname, m in c.methods.items():
            ops = list(tu.iter_ops(m["ops"]))
            methods.append({"name": mname, "kind": m["kind"], "signature": m["signature"], "loc": m["loc"],
                            "lines": m["lines"], "branches": m["branches"], "is_phase": m["is_phase"],
                            "calls": m["calls"],
                            "creates": [o["var"] for o in ops if o["op"] == "create"],
                            "connects": sum(1 for o in ops if o["op"] == "connect"),
                            "config_ops": sum(1 for o in ops if o["op"] == "cfg")})
        body = _body_info(tm, f, name) if tm.role(name) in ("sequence", "virtual_sequence") else None
        classes.append({
            "id": f"impl:{name}", "arch_ref": cid(name), "name": name, "loc": c.loc,
            "lines": max(c.end_line - int(c.loc.rsplit(":", 1)[-1] or 0), 0) if c.loc != "?" else 0,
            "members": [{"name": k, "type": m["type"], "dims": m["dims"], "init": m["init"], "rand": m["rand"],
                         "loc": m["loc"]} for k, m in c.members.items()],
            "methods": methods,
            "constraints": c.constraints, "covergroups": c.covergroups, "fields_macro": c.fields_macro,
            "registered_as": c.registered,
            "sequence_steps": [{"var": s["seq_var"], "type": body[0].get(s["seq_var"].split(".")[0]),
                                "on": s["on"], "via": s["via"], "loc": s["loc"]} for s in body[1]] if body else [],
        })
    return {"schema_version": SCHEMA_VERSION, "tool": {"name": "peacook", "version": __version__}, "classes": classes}
