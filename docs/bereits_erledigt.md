## Vorarbeit

* **Research/Hintergrundwissen**
* **Prototyp/Machbarkeitsstudie**
* **Feedback**
* **Exposee**

# Inhalt und Status
## Phase 1 Projektgrundlagen 

* **Repo & Packaging (pyproject + Hatchling, src-Layout, LICENSE, README):** ✅
* **Library & CLI-Gerüst:** `p2p_copy` (API-Stubs) und `p2p_copy_cli/main.py` (Enum für `compress`) — `p2p-copy --help` läuft. ✅
* **Server-Stub:** `server/relay.py` als Platzhalter. ✅
* **Protokoll-Skizze:** `protocol.py` (Hello/Manifest, Version) fixiert. ✅
* **Hilfs-Module (Platzhalter):** `chunker.py`, `io_utils.py`, `errors.py`. ✅
* **Tests (Smoke/env):** laufen im venv. ✅
* **Doku-Basis :** `mkdocs.yml`, `docs/index.md` und **Architekturskizze** eingebunden. ✅
* **IDE-Setup:** Projekt-Interpreter (venv), `src/` als Sources Root. ✅
* **Ignore-Regeln:** `.gitignore` inkl. `venv/`. ✅
* **Lokal paketieren:** wheel und tar ball erzeugt in `dist/` ✅
