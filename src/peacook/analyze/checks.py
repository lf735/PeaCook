"""Vérifications d'architecture (lint) sur le modèle fusionné."""
from __future__ import annotations

from ..extract import textutil as tu
from ..extract.facts import Facts
from ..resolve.types import TypeModel, base_name


def run_checks(arch: dict, f: Facts, tm: TypeModel, parse_diags: list[dict]) -> list[dict]:
    d: list[dict] = []
    env = arch["environment"]

    def add(sev, code, msg, loc=None, ref=None):
        d.append({"severity": sev, "code": code, "message": msg, "loc": loc, "ref": ref})

    # connexions utilisées
    used: set[tuple] = set()
    for c in env["connections"]:
        if any(c["states"].values()):
            used.add((c["src"]["inst"], (c["src"]["port"] or "").split(".")[0]))
            used.add((c["dst"]["inst"], (c["dst"]["port"] or "").split(".")[0]))
    for i in env["instances"]:
        if i["always_inactive"]:
            continue
        for p in i["ports"]:
            if (i["id"], p["name"]) in used:
                continue
            if p["protocol"] == "analysis" and p["kind"] == "port":
                add("info", "ANALYSIS_PORT_UNCONNECTED", f"{i['path']}.{p['name']} (analysis_port) sans abonné", i["loc"], i["id"])
            elif p["kind"] == "imp" and i["role"] != "subscriber":
                add("warning", "IMP_UNCONNECTED", f"{i['path']}.{p['name']} ne reçoit aucune connexion", i["loc"], i["id"])
            elif p["protocol"] == "seq_item" and i["role"] != "virtual_sequencer":
                add("warning", "SEQ_ITEM_UNCONNECTED", f"{i['path']}.{p['name']} non connecté", i["loc"], i["id"])
        if i["role"] == "subscriber" and not any((i["id"], p["name"]) in used for p in i["ports"]):
            add("warning", "SUBSCRIBER_NOT_FED", f"{i['path']} n'est abonné à aucun analysis_port", i["loc"], i["id"])
    for s in env["config_db"]["sets"]:
        if s["status"] == "orphan_set":
            add("warning", "CONFIG_DB_ORPHAN_SET", f"set '{s['field']}' ({s['type']}) vers '{s['pattern']}' jamais lu",
                s["loc"], s["id"])
    for g in env["config_db"]["gets"]:
        if g["status"] == "unmatched_get":
            add("error", "CONFIG_DB_UNMATCHED_GET", f"get '{g['field']}' ({g['type']}) dans {g['getter']} sans set correspondant",
                g["loc"], g["id"])
    for i in env["instances"]:
        cls = i["class"]
        if cls and cls not in f.classes and cls not in tm.f.classes and not cls.startswith("uvm_"):
            add("warning", "UNRESOLVED_TYPE", f"type {cls} de {i['path']} introuvable dans les sources", i["loc"], i["id"])
        if any(s["unresolved"] for s in i["states"].values()):
            add("info", "UNRESOLVED_CONDITION", f"{i['path']} : condition non déterminable statiquement ({'; '.join(i['guards'])})",
                i["loc"], i["id"])
    for t, ovs in env["factory_overrides"].items():
        for o in ovs:
            if o["over"] not in f.classes:
                add("warning", "OVERRIDE_UNKNOWN_CLASS", f"override vers classe inconnue {o['over']} ({t})", o["loc"])
    # membres composants jamais créés (niveau classe)
    for name, c in f.classes.items():
        if tm.role(name) in ("object", "config", "seq_item", "sequence", "virtual_sequence", "callback"):
            continue
        created = set()
        for mname in ("build_phase", "new", "connect_phase"):
            for _, m in tm.method_chain(name, mname):
                for o in tu.iter_ops(m["ops"]):
                    if o["op"] == "create":
                        created.add(o["var"].split("[")[0].replace("this.", ""))
                    elif o["op"] in ("assign",):
                        created.add(o["lhs"].split("[")[0].replace("this.", ""))
        for mn, m in c.members.items():
            if tm.role(name) == "virtual_sequencer" and tm.role(m["type"]) in ("sequencer", "virtual_sequencer"):
                continue  # handles renseignés de l'extérieur (env)
            if tm.is_component(m["type"]) and not tm.is_port_type(m["type"]) and mn not in created:
                add("info", "MEMBER_NEVER_CREATED", f"{name}.{mn} ({m['type']}) déclaré mais jamais créé", m["loc"], f"class:{name}")
    n_parse = len(parse_diags)
    if n_parse:
        add("info", "PARSE_DIAGNOSTICS", f"{n_parse} diagnostic(s) de parsing (macros UVM remplacées par des stubs)")
    order = {"error": 0, "warning": 1, "info": 2}
    d.sort(key=lambda x: (order[x["severity"]], x["code"], x["message"]))
    return d
