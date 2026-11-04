# PeaCook

Extraction d'**architecture** d'environnements UVM (SystemVerilog) → schémas et modèles JSON.

PeaCook analyse statiquement les sources (aucun simulateur requis, via [pyslang](https://pypi.org/project/pyslang/)),
interprète symboliquement `new` / `build_phase` / `connect_phase` pour chaque test, et produit :

- une **topologie unique** par environnement (schéma de référence) où les composants activés par une condition sont mis en évidence ;
- pour **chaque test**, le même schéma avec les composants désactivés **grisés** (option pour les masquer) et les overrides factory appliqués ;
- deux couches de sortie **séparées mais liées** par des identifiants stables : `architecture/` et `implementation/`.

## Installation

```powershell
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
```

Graphviz (`dot`) est optionnel : sans lui, les `.dot` sont générés mais pas les `.svg`.

## Utilisation

```powershell
# Tout en une commande : filelist .f (+incdir, +define, -f imbriqués) ou scan d'un répertoire
peacook all -f tests/fixtures/bridge_tb/files.f -o out/bridge
peacook all -d chemin/vers/env_uvm -o out/mon_env

peacook scan   -f tb.f -o out/model          # modèle JSON seulement
peacook render out/model/architecture/architecture.json -o out/vues --formats mermaid,html
peacook check  -f tb.f --fail-on warning     # lint d'architecture (code de sortie pour la CI)
```

Options utiles : `--test T` (limiter à un test), `--hide-inactive` (ne pas afficher les éléments grisés),
`--raw` (connexions hiérarchiques au lieu de bout en bout), `--views`, `--formats`, `--no-impl`,
`-I`, `-D`, `--exclude`, `--uvm-home` (vraies macros UVM à la place des stubs), `--max-array-expand`.

## Sorties

```text
out/
├─ index.html                      viewer autonome (hors ligne) : blocs repliables, sélecteur de test, grisage,
│                                  masquage des inactifs, recherche, panneau Architecture / Implémentation, export SVG
├─ architecture/
│  ├─ architecture.json            modèle complet de la couche architecture
│  ├─ report.md                    rapport (diagrammes Mermaid intégrés)
│  └─ views/
│     ├─ block.all.{mmd,dot,svg}   schéma de référence ; block.<test>.* : même schéma, inactifs grisés
│     ├─ block.drawio              une page par test + une page de référence (éditable dans draw.io)
│     ├─ hierarchy.{mmd,txt,json}  classes.{mmd,dot,json}   config_db.{dot,json}   sequences.{mmd,json}
│     └─ harness.{mmd,json}  connections.json  dataflow.json  tests.json  lint.json     (JSON compacts)
└─ implementation/
   ├─ implementation.json          méthodes, contraintes, covergroups, champs, étapes de séquences...
   ├─ report.md
   └─ classes/<classe>.md          une fiche par classe, liée à la vue d'architecture
```

## Comment les conditions sont résolues

Les valeurs sont déduites de l'environnement, **test par test** : affectations de champs d'objets de configuration
(`cfg.is_active = UVM_PASSIVE`), valeurs par défaut, `config_db::set/get` (glob, priorité hiérarchique),
`get_is_active()`, tailles de tableaux (`new[cfg.num_out]`), boucles `for`/`foreach`, paramètres. Une branche à faux est
exécutée en mode « fantôme » : ses composants existent mais sont marqués inactifs (grisés). Quand aucune valeur n'est
déductible, le composant est marqué `unresolved` (jamais deviné).

## Limites connues (analyse statique)

- Pas d'exécution réelle : valeurs aléatoires, `$urandom`, logique procédurale complexe → `unresolved`.
- Constructions non reconnues → ignorées silencieusement (ajouter un test unitaire dans `tests/`).
- Classes de la bibliothèque UVM non fournies : rôle et ports hérités issus d'une base de connaissances intégrée
  (`resolve/uvm_kb.py`) ; macros UVM remplacées par des stubs (`frontend/stubs/uvm_macros.svh`).
- RAL, diff d'architecture, carte des phases, import d'un dump de simulation : prévus (v2), non implémentés.

## Tests

```powershell
.venv\Scripts\python -m pytest
```
