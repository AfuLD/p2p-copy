# Vorgehensplan (Phasen & Meilensteine)

## Phase 1 – Projektgrundlagen (Woche 1)

    Repo & Packaging: pyproject.toml (PEP 621), strukturierte Library + CLI, semantische Versionierung, Lizenz.

    Tooling: Pytest

    Grundstruktur: p2p_copy/ (Library) + p2p_copy_cli/ (CLI) + server/ (Relay).
    Ziel: lauffähiges Gerüst, importierbar und installierbar.

## Phase 2 – Minimaler vertikaler Slice (Woche 2)

    Relay-Server (MVP): Asyncio + websockets, Session-Matching via SHA-256(passphrase), Weiterleitung ohne Persistenz („glue together“). Lauscht auf WSS:443. 

Client (MVP): receive/send mit einfachem Chunk-Streaming (Start: 1 MiB, konfigurierbar), Binärweiterleitung, speichern.

    CLI-Befehle (MVP):

        p2p-copy receive --server wss://HOST --code <pass>

        p2p-copy send --server wss://HOST --code <pass> --files ...
        Ziel: eine Datei Ende-zu-Ende übertragen.

## Phase 3 – Protokoll & Integrität (Woche 3)

    Kontrollframes: Handshake, Manifest (Dateiliste, Größen, Zielpfade), Acks, Fehlermeldungen (JSON/Msgpack), Datenframes binär.

    Integrität: Datei-SHA-256 (Ende), optional laufende Ketten-Prüfsumme pro Chunk (Detektion von Lücken/Out-of-Order). 

    Backpressure & Keepalive: Flow-Control, Ping/Pong, Timeouts.

## Phase 4 – Performance-Features (Woche 4)

    Adaptive Kompression: Heuristik (Sniffing der ersten Bytes), zstd bevorzugt, Fallback gzip, Modi auto|on|off. 

Chunk-Tuning: Benchmark 512 KiB–4 MiB, konfigurierbar.

I/O-Optimierungen: memoryview, asynchrones File-I/O, Rahmen für spätere Multiplex-Streams (optional, „später“).

## Phase 5 – Sicherheit (Woche 5)

    Optionales E2E (AES-256-GCM): Schlüsselableitung robust (z. B. scrypt/HKDF) aus gemeinsamem Code; Nonce/IV-Handling; Umschlag im Frame-Header. Dein Exposé sieht AES-256 auf Basis der Passphrase als Option vor – wir härten das gegenüber „nur SHA-256(pass)“ ab, ohne die Performance-Option ohne E2E zu verlieren. 

    TLS-Betrieb: WSS hinter Nginx/Traefik auf :443 (Let’s Encrypt) oder direkt mit Zertifikat.

## Phase 6 – Resumieren & Robustheit (Woche 6)

    Wiederaufnahme: Manifest enthält Chunk-Index/Hashes; Receiver meldet „fehlende Ranges“, Sender überträgt nur Lücken (rsync-ähnlich). 

    Crash-Sicherheit: Temp-Dateien + atomare Renames; Idempotente Zielpfade; Konfliktstrategie.

    Fehlerbilder: Netzwerk-Flaps, Timeouts, Platte voll – saubere Recovery.

## Phase 7 – Python-API & DX (Woche 7)

    Öffentliche API: from p2p_copy import send(files, code, server, **opts), receive(...) – identische Optionen wie CLI, aber ohne Subprozess-Overhead (wichtig für HPC-Workflows). 

    Beispiele/Notebooks: Minimalbeispiele für Pipeline-Integration.

## Phase 8 – Doku, Benchmarks, Release (Woche 8)

    Doku: MkDocs (Architektur, Protokoll, Deployment, Security-Notes, Tuning).

    Benchmarks: Datensätze (Text, Binär, Mix), Metriken (Durchsatz, CPU, Kompressionsgewinn, Latenz). Vergleich: ohne/mit Kompression, ohne/mit E2E.

    v0.1.0 Release: Wheels, Changelog, README Quickstart.