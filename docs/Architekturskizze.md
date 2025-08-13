# Architektur & Modulskizze

> Hinweis: Im Repository liegen die Pakete unter `src/`. Die folgende Skizze zeigt die Module ohne `src/`‑Präfix, damit die Architektur klar bleibt.

```text
p2p_copy/
  __init__.py
  api.py                   # High-level Python-API (send/receive)
  protocol.py              # Frame- und Nachrichtenformate
  chunker.py               # Lesen/Schreiben in Chunks (≈1 MiB, konfigurierbar)
  compressor.py            # adaptive Kompression (auto|on|off; zstd bevorzugt)
  crypto.py                # optionale E2E-Verschlüsselung (AES-256-GCM + KDF)
  checksum.py              # Datei-Hash + Ketten-Checksummen
  resume.py                # Lücken-Ermittlung und -Übertragung
  io_utils.py              # asynchrones Dateihandling, Pfade, Tempfiles
  errors.py                # Exceptions

p2p_copy_cli/
  __init__.py
  main.py                  # Typer-CLI (send/receive + Optionen)

p2p_copy_server/
  __init__.py
  relay.py                 # Asyncio + websockets, Matching per SHA-256(code)
  sessions.py              # Lebenszyklus, Pings, Limits

tests/                     # Unit-, Property-, Integrations- und E2E-Tests
benchmarks/                # Skripte & Daten
docs/                      # MkDocs, Architektur und Modulskizze, Vorgehensplan
```

## Hinweis zur tatsächlichen Projektstruktur (src-Layout)

Im Projekt liegen die Pakete so:

```text
src/
  p2p_copy/...
  p2p_copy_cli/...
  p2p_copy_server/...
tests/
benchmarks/
docs/
```
