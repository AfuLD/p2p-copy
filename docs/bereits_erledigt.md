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


## Phase 3 Protokoll & Integrität

* **Manifest & Multi-File-Support** : Sender erstellt Manifest (Dateien + Verzeichnisse, rekursiv), Empfänger rekonstruiert Struktur unter Zielpfad.
* **File-Framing** : Pro Datei `file`-Ankündigung und `file_eof`-Markierung mit erwarteter SHA-256.
* **Chunk-Übertragung** : Binärframes tragen Sequenznummer + verkettete Prüfsumme, Empfänger prüft Reihenfolge & Chain sofort.
* **End-to-End-Integrität** : Laufende Hash-Berechnung während Transfer; Abbruch bei Mismatch.
* **API-Updates** : `send()` & `receive()` implementieren Mehrdatei-Logik, prüfen Integrität on-the-fly, erzeugen Zielverzeichnisse automatisch.
* **CLI-Updates** : `p2p-copy send SERVER CODE FILE [FILE…]` unterstützt jetzt mehrere Dateien/Verzeichnisse, `receive` schreibt Baum unter `--out` (default: `.`).
* **Hilfs-Module** : `iter_manifest_entries` in `io_utils.py` löst Verzeichnisbäume auf; 
* **Relay-Server** : striktere Pairing-Logik (1 Sender + 1 Empfänger pro Code), sauberes Bidirektionales Weiterleiten, TLS weiterhin default=on.
* **Tests** : Neue Tests `tests/test_phase3_features.py` prüfen Manifest-Roundtrip, API-Multi-File-Transfer inkl. Hashprüfung, CLI mit mehreren Dateien;
* **Dokumentation** : Wire-Format (Hello, Manifest, FileBegin/End, Chunks mit Chain, EOF) in Code und Notizen festgehalten.
