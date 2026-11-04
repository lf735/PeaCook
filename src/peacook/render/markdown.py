"""Rapports Markdown : architecture (avec diagrammes Mermaid) et fiches d'implémentation liées."""
from __future__ import annotations

from . import mermaid
from .common import View


def tree_text(arch: dict) -> str:
    env = arch["environment"]
    by = {i["id"]: i for i in env["instances"]}
    kids: dict = {}
    for i in env["instances"]:
        if i["parent"]:
            kids.setdefault(i["parent"], []).append(i["id"])
    lines: list[str] = []

    def emit(i, prefix, last, is_root=False):
        n = by[i]
        inactive = [t for t, s in n["states"].items() if not s["active"]]
        mark = ""
        if n["guards"]:
            mark += f"  ⟨si {'; '.join(n['guards'])}⟩"
        if inactive and len(inactive) != len(env["tests"]):
            mark += f"  ✗ inactif dans : {', '.join(inactive)}"
        elif inactive:
            mark += "  ✗ inactif dans tous les tests"
        if n["overridden_in"]:
            mark += f"  ⇄ override dans : {', '.join(n['overridden_in'])}"
        lab = f"{n['name']} : {n['declared_type']} [{n['role']}]{mark}"
        if is_root:
            lines.append(lab)
        else:
            lines.append(prefix + ("└── " if last else "├── ") + lab)
        ks = kids.get(i, [])
        for k, c in enumerate(ks):
            emit(c, prefix + ("" if is_root else ("    " if last else "│   ")), k == len(ks) - 1)

    emit(env["root"], "", True, True)
    return "\n".join(lines)


def architecture_report(arch: dict, impl_dir_rel: str | None = "../implementation/classes") -> str:
    env = arch["environment"]
    L = ["# Architecture de l'environnement UVM", ""]
    n_act = sum(1 for i in env["instances"] if any(s["active"] for s in i["states"].values()))
    L += [f"- Tests analysés : **{len(env['tests'])}** ({', '.join(env['tests'])})",
          f"- Classes : **{len(arch['classes'])}**, instances (surensemble) : **{len(env['instances'])}** dont "
          f"**{sum(1 for i in env['instances'] if i['conditional'])}** conditionnelles",
          f"- Connexions TLM de bout en bout : **{len(env['flat_connections'])}**",
          f"- Diagnostics : {sum(1 for d in arch['diagnostics'] if d['severity'] == 'error')} erreur(s), "
          f"{sum(1 for d in arch['diagnostics'] if d['severity'] == 'warning')} avertissement(s)", ""]
    if not env["instances"]:
        L += ["> Aucun test (`uvm_test`) trouvé dans les sources : pas de topologie d'instances à afficher. "
              "Les classes et leurs relations sont décrites plus bas.", ""]
    else:
        L += ["## Schéma de référence (tous tests)", "",
              "Les blocs en pointillé orange sont activés par une condition ; par test, ils sont grisés quand désactivés.", "",
              "```mermaid", mermaid.block(View(arch, None)).rstrip(), "```", ""]
        L += ["## Hiérarchie", "", "```text", tree_text(arch), "```", ""]
    L += ["## Tests", "", "| Test | Hérite de | Overrides factory | Instances inactives |", "|---|---|---|---|"]
    for t in arch["tests"]:
        ovs = env["factory_overrides"].get(t["name"], [])
        inactive = sorted(i["path"].replace("uvm_test_top.", "") for i in env["instances"]
                          if i["states"][t["name"]]["present"] and not i["states"][t["name"]]["active"])
        ovtxt = '<br>'.join('`{}`: {} → {}'.format(o['path'], o['orig'], o['over']) for o in ovs) or '—'
        L.append(f"| `{t['name']}` | {', '.join(t['base_chain'][:1])} | {ovtxt} | {len(inactive)} |")
    L.append("")
    L += ["## Connexions TLM (de bout en bout)", "", "| Source | Destination | Protocole | Transaction | Actif dans |", "|---|---|---|---|---|"]
    for c in env["flat_connections"]:
        act = [t for t, a in c["states"].items() if a]
        L.append(f"| `{c['from']['inst'][5:]}.{c['from']['port']}` | `{c['to']['inst'][5:]}.{c['to']['port']}` | "
                 f"{c['protocol']} | {c['txn'] or ''} | {'tous' if len(act) == len(env['tests']) else ', '.join(act) or '—'} |")
    L.append("")
    L += ["## config_db", "", "| Champ | Type | Émetteur | Cible | Lu par | État |", "|---|---|---|---|---|---|"]
    for s in env["config_db"]["sets"]:
        L.append(f"| `{s['field']}` | `{s['type']}` | {s['setter'][5:] if s['setter'] else '(tb_top)'} | `{s['pattern']}` | "
                 f"{', '.join(c[5:] for c in s['consumers']) or '—'} | {'✅' if s['status'] == 'ok' else '⚠️ orphelin'} |")
    L.append("")
    L += ["## Séquences → séquenceurs", "", "| Séquence | Item | Lancée par | Sur | Tests |", "|---|---|---|---|---|"]
    for r in env["sequences"]:
        L.append(f"| `{r['seq_name']}` | {r['item'] or ''} | {r['started_by'].split(':', 1)[1]} | "
                 f"{r['on'][5:] if r['on'] else '?'} | {', '.join(r['tests'])} |")
    if env["handle_links"]:
        L += ["", "Handles de séquenceurs (séquenceur virtuel) :", ""]
        for l in env["handle_links"]:
            L.append(f"- `{l['owner'][5:]}.{l['handle']}` → `{l['target'][5:]}`")
    L.append("")
    L += ["## Harnais top / DUT", "", "```mermaid", mermaid.harness(arch).rstrip(), "```", ""]
    L += ["## Classes", "", "| Classe | Rôle | Base | Implémentation |", "|---|---|---|---|"]
    for c in arch["classes"]:
        link = f"[fiche]({impl_dir_rel}/{c['name']}.md)" if impl_dir_rel else ""
        L.append(f"| `{c['name']}` | {c['role']} | {c['base'] or ''} | {link} |")
    L.append("")
    L += ["## Diagnostics", ""]
    if not arch["diagnostics"]:
        L.append("Aucun.")
    for d in arch["diagnostics"]:
        L.append(f"- **{d['severity']}** `{d['code']}` — {d['message']}" + (f" _({d['loc']})_" if d.get("loc") else ""))
    return "\n".join(L) + "\n"


def impl_class_md(c: dict, arch_class: dict | None, arch_report_rel="../../architecture/report.md") -> str:
    L = [f"# {c['name']}", "",
         f"Rôle d'architecture : **{arch_class['role'] if arch_class else '?'}** — [vue d'architecture]({arch_report_rel}) "
         f"(`{c['arch_ref']}`)", "", f"Défini dans `{c['loc']}` ({c['lines']} lignes)", ""]
    if c["members"]:
        L += ["## Membres", "", "| Nom | Type | Init | rand |", "|---|---|---|---|"]
        L += [f"| `{m['name']}{m['dims']}` | `{m['type']}` | {m['init'] or ''} | {'oui' if m['rand'] else ''} |" for m in c["members"]]
        L.append("")
    if c["methods"]:
        L += ["## Méthodes", "", "| Méthode | Type | Lignes | Branches | Appels notables | Loc |", "|---|---|---|---|---|---|"]
        L += [f"| `{m['name']}` | {m['kind']}{' (phase)' if m['is_phase'] else ''} | {m['lines']} | {m['branches']} | "
              f"{', '.join(f'`{x}`' for x in m['calls'][:8])} | {m['loc']} |" for m in c["methods"]]
        L.append("")
    if c["constraints"]:
        L += ["## Contraintes", ""] + [f"- `{x['name']}` ({x['loc']}) : `{x['text']}`" for x in c["constraints"]] + [""]
    if c["covergroups"]:
        L += ["## Covergroups", ""]
        for g in c["covergroups"]:
            cps = ", ".join(f"`{n}`" for n, _ in g["coverpoints"]) or "—"
            xs = ", ".join(f"`{n}`" for n, _ in g["crosses"]) or "—"
            L.append(f"- `{g['name']}` ({g['loc']}) — coverpoints : {cps} — crosses : {xs}")
        L.append("")
    if c["fields_macro"]:
        L += ["## Champs `uvm_field_*`", "", ", ".join(f"`{x}`" for x in c["fields_macro"]), ""]
    if c["sequence_steps"]:
        L += ["## Étapes de la séquence (`body`)", "", "| Séquence/Item | Type | Sur | Via |", "|---|---|---|---|"]
        L += [f"| `{s['var']}` | {s['type'] or ''} | `{s['on'] or ''}` | {s['via']} |" for s in c["sequence_steps"]]
    return "\n".join(L) + "\n"


def impl_report(impl: dict, arch: dict) -> str:
    by = {c["name"]: c for c in arch["classes"]}
    L = ["# Implémentation (détails par classe)", "",
         "Les fiches détaillent ce qui n'apparaît pas dans les schémas d'architecture. "
         "[Retour à l'architecture](../architecture/report.md).", "",
         "| Classe | Rôle | Méthodes | Contraintes | Covergroups | Lignes |", "|---|---|---|---|---|---|"]
    for c in impl["classes"]:
        L.append(f"| [{c['name']}](classes/{c['name']}.md) | {by[c['name']]['role']} | {len(c['methods'])} | "
                 f"{len(c['constraints'])} | {len(c['covergroups'])} | {c['lines']} |")
    return "\n".join(L) + "\n"
