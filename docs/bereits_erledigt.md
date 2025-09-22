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


## Phase 4 Kompression & Optimierungen

* **Chunk-Größe optimiert:** 1MB am besten, kein großer Unterschied.
* **Performancevergleich Kompressionsmethoden:** `zstd` auf App-Ebene deutlich am besten.
* **Datei-Kompression integriert:** `compressor.py` implementiert mit `CompressMode` (`off`, `on`, `auto`) und Zstd (Level 3).
* **Automatische Kompressionsentscheidung:** Sender prüft ersten Chunk und aktiviert Kompression nur bei > 5 % Einsparung.
* **Protokoll-Erweiterung:** `file_begin` kündigt pro Datei die gewählte Kompressionsart (`zstd`/`none`) an; Empfänger dekomprimiert entsprechend.
* **API-Updates:** `send()` und `receive()` nutzen Kompressor; WebSocket-Kompression explizit auf `None` gesetzt.
* **CLI-Optionen:** `--compress {off,on,auto}` ergänzt, analog zur API.
* **Integrität trotz Kompression:** Chained Checksum wird über die tatsächlich übertragenen Bytes (komprimiert) gebildet, Größenprüfung bezieht sich auf Originaldateien.
* **Tests:** neue Tests prüfen End-to-End-Verhalten aller Modi (API & CLI), Auto-Fall mit komprimierbaren und nicht komprimierbaren Dateien, Timing-Messungen für Vergleich.
* **Code-Logik:** Kompression entkoppelt von API, zentral in `compressor.py`.
* **Dokumentation:** Erweiterung der Wire-Format-Notizen um Kompressionsangaben; Hinweise zu Performance und Einsatzgrenzen.  
* **Async I/O:** Disk read und write in async event-loop eingebunden


## Phase 5 Sicherheit

* **KDF:** argon2id implementiert zur Ableitung von hello und AES-GCM Key
* **Verschlüsselung:** AES-GCM implementiert zum verschlüsseln
* **Protokoll-Erweiterung:** Verschlüsselte Manifeste und Dateiinfo ergänzt
* **Optionalität:** unverschlüsselte Verwendung unbeeinträchtigt von Erweiterungen
* **Tests:** auf Funktionalität und Performanceauswirkungen geprüft