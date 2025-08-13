## Vorarbeit

* **Research/Hintergrundwissen**
* **Prototyp/Machbarkeitsstudie**
* **Feedback zu Anforderungen/Spezifikation**
* **Exposee**

# Inhalt und Status
## Phase 1 Projektgrundlagen 

* **Repo & Packaging (pyproject + Hatchling, src-Layout, LICENSE, README)** 
* **Library & CLI-Gerüst:** `p2p_copy` (API-Stubs) und `p2p_copy_cli/main.py` (Enum für `compress`),  `p2p-copy --help` läuft. 
* **Server-Stub:** `server/relay.py` als Platzhalter. 
* **Protokoll-Skizze:** `protocol.py` (Hello/Manifest, Version) fixiert. 
* **Hilfs-Module (Platzhalter):** `chunker.py`, `io_utils.py`, `errors.py`. 
* **Tests (Smoke/env):** laufen im venv. 
* **Doku-Basis :** `mkdocs.yml`, `docs/index.md` und **Architekturskizze** eingebunden. 
* **IDE-Setup:** Projekt-Interpreter (venv), `src/` als Sources Root. 
* **Ignore-Regeln:** `.gitignore` inkl. `venv/`. 
* **Lokal paketieren:** wheel und tar ball erzeugt in `dist/` 


## Phase 2  Minimaler vertikaler Slice

* **Modernisierte WebSocket-Nutzung (Client & Relay)** : neue `websockets.asyncio.*` API, Host auf `localhost` vereinheitlicht.
* **Relay als eigenes Paket + CLI-Start** : `p2p_copy_server` unter `src/`, Befehl `p2p-copy run-relay-server` (TLS standardmäßig an).
* **E2E-Transfer (Vertical Slice)** : Ablauf `Original → (binäre Chunks) → Kopie`, eine Datei pro Transfer.
* **CLI-Argumente** : positional args (`send SERVER CODE FILE…`, `receive SERVER CODE`) geklärt.
* **CLI-Optionen** : `--out` nur bei `receive`, `--encrypt/--compress` nur bei `send`.
* **CompressMode** : Enum in `compressor.py`, CLI importiert entpsrechend.
* **`io_utils.ensure_dir`** : hinzugefügt und in `receive` genutzt
* **Tests** : E2E-WS-Transfer, Code-Isolation, Ablehnung zweiter Sender, CLI-E2E (`--no-tls`), hinzugefügt und ausgeführt.
* **Packaging-Feinschliff** : Hatch-Build-Targets für `p2p_copy_server` im `pyproject.toml` eingefügt. 
* **Dokumentation/Usage** : Aktualisierte CLI-Usage (Markdown) mit Beispielen und neuen Befehldetails.
