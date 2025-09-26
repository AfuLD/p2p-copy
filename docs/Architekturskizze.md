# Architektur & Modulskizze

> Hinweis: Im Repository liegen die Pakete unter `src/`. Die folgende Skizze zeigt die Module ohne `src/`‑Präfix, damit die Architektur klar bleibt.

```text
p2p_copy/                  # Kernbibliothek
  __init__.py
  api.py                   # High-level Python-API (send/receive)
  protocol.py              # Frame- und Nachrichtenformate
  compressor.py            # adaptive Kompression (auto|on|off; zstd bevorzugt)
  security.py              # Verschlüsselung, KDF (AES-256-GCM + Argon2)
  checksum.py              # Datei-Hash + Ketten-Checksummen
  resume.py                # Lücken-Ermittlung und -Übertragung
  io_utils.py              # asynchrones Dateihandling, Pfade, Iterator

p2p_copy_cli/              # Kommandozeilenoberfläche
  __init__.py
  main.py                  # Typer-CLI (send/receive + Optionen)

p2p_copy_server/           # Relay-Server zum weiterleiten von Nachrichten
  __init__.py
  relay.py                 # Asyncio + websockets, Matching per SHA-256(code)
  sessions.py              # Lebenszyklus, Pings, Limits

```

## Hinweis zur tatsächlichen Projektstruktur (src-Layout)

Im Projekt liegen die Pakete so:

```text
src/
  p2p_copy/...
  p2p_copy_cli/...
  p2p_copy_server/...
docs/
examples/
tests/
```
