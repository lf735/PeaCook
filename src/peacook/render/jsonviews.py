"""Vues JSON compactes : uniquement l'essentiel de chaque vue, sans superflu (identifiants pour rejoindre le modèle)."""
from __future__ import annotations

from collections import defaultdict


def _active_in(states: dict) -> list[str]:
    return [t for t, a in states.items() if (a["active"] if isinstance(a, dict) else a)]


def hierarchy(arch: dict) -> dict:
    env = arch["environment"]
    tests = env["tests"]
    by = {i["id"]: i for i in env["instances"]}
    kids = defaultdict(list)
    for i in env["instances"]:
        if i["parent"]:
            kids[i["parent"]].append(i["id"])

    def node(i):
        n = by[i]
        effs = {t: s["effective_type"] for t, s in n["states"].items() if s["effective_type"]}
        out = {"id": n["id"], "name": n["name"], "type": n["declared_type"], "role": n["role"]}
        if len(set(effs.values())) > 1 or (effs and next(iter(effs.values())) != n["declared_type"] and n["id"] != env["root"]):
            out["effective_type"] = effs
        act = _active_in(n["states"])
        if len(act) != len(tests):
            out["active_in"] = act
        if n["guards"]:
            out["conditions"] = n["guards"]
        if kids[i]:
            out["children"] = [node(k) for k in kids[i]]
        return out

    return {"tests": tests, "root": node(env["root"])}


def connections(arch: dict) -> dict:
    env = arch["environment"]
    tests = env["tests"]
    out = []
    for c in env["flat_connections"]:
        e = {"from": f"{c['from']['inst'][5:]}.{c['from']['port']}", "to": f"{c['to']['inst'][5:]}.{c['to']['port']}",
             "protocol": c["protocol"], "txn": c["txn"]}
        a = _active_in(c["states"])
        if len(a) != len(tests):
            e["active_in"] = a
        out.append(e)
    for l in env["handle_links"]:
        e = {"from": f"{l['owner'][5:]}.{l['handle']}", "to": l["target"][5:], "protocol": "handle", "txn": None}
        a = _active_in(l["states"])
        if len(a) != len(tests):
            e["active_in"] = a
        out.append(e)
    return {"connections": out}


def config_db(arch: dict) -> dict:
    db = arch["environment"]["config_db"]
    sets = []
    for s in db["sets"]:
        vals = s["values"]
        e = {"field": s["field"], "type": s["type"], "set_by": s["setter"][5:] if s["setter"] else "(tb_top)",
             "target": s["pattern"], "read_by": [c[5:] for c in s["consumers"]], "status": s["status"]}
        e["value"] = next(iter(vals.values())) if len(set(vals.values())) == 1 else vals
        sets.append(e)
    gets = [{"field": g["field"], "type": g["type"], "getter": g["getter"][5:], "status": g["status"]}
            for g in db["gets"]]
    return {"sets": sets, "gets": gets}


def sequences(arch: dict) -> dict:
    env = arch["environment"]
    return {"runs": [{"sequence": r["seq_name"], "item": r["item"], "on": r["on"][5:] if r["on"] else None,
                      "started_by": r["started_by"].split(":", 1)[1], "tests": r["tests"]} for r in env["sequences"]],
            "sequencer_handles": [{"owner": l["owner"][5:], "handle": l["handle"], "target": l["target"][5:]}
                                  for l in env["handle_links"]]}


def harness(arch: dict) -> dict:
    return {"tops": [{"name": t["name"], "run_test": t["run_test"],
                      "interfaces": [{"name": i["name"], "type": i["type"]} for i in t["interfaces"]],
                      "duts": [{"name": d["name"], "type": d["type"], "interfaces": d["interfaces"]} for d in t["duts"]],
                      "vif": [{"field": v["field"], "interface": v["interface_instance"], "target": v["pattern"],
                               "consumers": [c[5:] for c in v["consumers"]]} for v in t["vif_sets"]]}
                     for t in arch["harness"]["tops"]]}


def classes(arch: dict) -> dict:
    return {"classes": [{"class": c["name"], "base": c["base"], "role": c["role"], "package": c["package"],
                         **({"params": [p["name"] for p in c["params"]]} if c["params"] else {}),
                         **({"ports": [f"{p['name']}:{p['kind']}/{p['protocol']}({p['txn']})" for p in c["ports"]]} if c["ports"] else {}),
                         **({"children": [f"{x['member']}:{x['type']}" for x in c["children"]]} if c["children"] else {})}
                        for c in arch["classes"]]}


def tests(arch: dict) -> dict:
    env = arch["environment"]
    out = []
    for t in arch["tests"]:
        name = t["name"]
        out.append({"test": name, "extends": t["base_chain"][:1],
                    "overrides": [{"path": o["path"], "from": o["orig"], "to": o["over"]}
                                  for o in env["factory_overrides"].get(name, [])],
                    "sequences": [r["seq_name"] for r in env["sequences"] if name in r["tests"] and r["started_by"] == "inst:uvm_test_top"],
                    "inactive": sorted(i["path"] for i in env["instances"]
                                       if i["states"][name]["present"] and not i["states"][name]["active"]),
                    "instances": sum(1 for i in env["instances"] if i["states"][name]["active"])})
    return {"tests": out}


def lint(arch: dict) -> dict:
    return {"diagnostics": [{k: d[k] for k in ("severity", "code", "message", "loc") if d.get(k)} for d in arch["diagnostics"]]}


def dataflow(arch: dict) -> dict:
    env = arch["environment"]
    prod, cons = defaultdict(set), defaultdict(set)
    for c in env["flat_connections"]:
        if c["protocol"] != "analysis" or not c["txn"]:
            continue
        prod[c["txn"]].add(c["from"]["inst"][5:])
        cons[c["txn"]].add(c["to"]["inst"][5:])
    return {"transactions": [{"txn": t, "producers": sorted(prod[t]), "consumers": sorted(cons[t])} for t in sorted(prod)]}


ALL = {"hierarchy": hierarchy, "connections": connections, "config_db": config_db, "sequences": sequences,
       "harness": harness, "classes": classes, "tests": tests, "lint": lint, "dataflow": dataflow}
