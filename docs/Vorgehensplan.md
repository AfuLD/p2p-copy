# Vorgehensplan (Phasen & Meilensteine)
Angelehnt an das Softwareentwicklungsmodell "Vertical Slice Architecture".  
[Artikel hierzu](https://software-architecture-summit.de/blog/software-architektur/vertical-slice-architecture-einfuhrung/) (Autor: Thomas Bayer, last accessed: 14.08.25)

## Phase 1 – Projektgrundlagen

    Repo & Packaging: pyproject.toml (PEP 621), strukturierte Library + CLI, semantische Versionierung, Lizenz.

    Tooling: Pytest

    Grundstruktur: p2p_copy/ (Library) + p2p_copy_cli/ (CLI) + server/ (Relay).
    Ziel: lauffähiges Gerüst, importierbar und installierbar.

## Phase 2 – Minimaler vertikaler Slice

    Relay-Server (MVP): Asyncio + websockets, Session-Matching via SHA-256(passphrase), Weiterleitung ohne Persistenz („glue together“).

    Client (MVP): receive/send mit einfachem Chunk-Streaming (Start: 1 MiB, konfigurierbar), Binärweiterleitung, speichern.

    CLI-Befehle (MVP) erstellen:

        p2p-copy receive ...

        p2p-copy send ...

        Ziel: eine Datei Ende-zu-Ende übertragen.

## Phase 3 – Protokoll & Integrität

    Kontrollframes: Handshake, Manifest (Dateiliste, Größen, Zielpfade), Acks, Fehlermeldungen (JSON/Msgpack), Datenframes binär.

    Integrität: Datei-SHA-256 (Ende), optional laufende Ketten-Prüfsumme pro Chunk (Detektion von Lücken/Out-of-Order). 

    Backpressure & Keepalive: Flow-Control, Ping/Pong, Timeouts.

## Phase 4 – Performance-Features

    Adaptive Kompression: Heuristik (Sniffing der ersten Bytes), zstd bevorzugt, Fallback gzip, Modi auto|on|off. 

    Chunk-Tuning: Benchmark 512 KiB–4 MiB, konfigurierbar.

    I/O-Optimierungen: memoryview, asynchrones File-I/O, Rahmen für spätere Multiplex-Streams (optional, „später“).

## Phase 5 – Sicherheit

    Optionales E2E (AES-256-GCM): Schlüsselableitung robust (z. B. scrypt/HKDF) aus gemeinsamem Code; Nonce/IV-Handling; Umschlag im Frame-Header. Exposé sieht AES-256 auf Basis der Passphrase als Option vor, eventuell "härten" ohne die Performance-Option ohne E2E zu verlieren. 

    TLS-Betrieb: WSS hinter Nginx/Traefik auf :443 (Let’s Encrypt) oder direkt mit Zertifikat.

## Phase 6 – Resumieren & Robustheit

    Wiederaufnahme: Manifest enthält Chunk-Index/Hashes; Empfänger kann prüfen bis wohin er eine Datei korrekt erhalten hat. 

    Crash-Sicherheit: Temp-Dateien + atomare Renames; Idempotente Zielpfade; Konfliktstrategie.

    Fehlerbilder: Netzwerkprobleme, Timeouts, Speicherproblem, sauberes Fortsetzen ermöglichen.

## Phase 7 – Python-API & DX

    Öffentliche API: from p2p_copy import send(files, code, server, **opts), receive(...) – identische Optionen wie CLI, aber ohne Subprozess-Overhead. 

    Beispiele/Notebooks: Minimalbeispiele für Pipeline-Integration und API Nutzung.

## Phase 8 – Doku, Benchmarks, Release

    Doc-Strings: in NumPy style formulieren
    
    Doku: MkDocs (Architektur, Protokoll, Deployment, Security-Notes, Tuning).

    Benchmarks: Datensätze (Text, Binär, Mix), Metriken (Durchsatz, CPU, Kompressionsgewinn, Latenz). Vergleich: ohne/mit Kompression, ohne/mit E2E.

    v0.1.0 Release: Wheels, Changelog, README Quickstart.
