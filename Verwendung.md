# p2p-copy — CLI Usage (Phase 2)

> **Status (Phase 2):** Es wird nur die **erste** angegebene Datei übertragen.  
> `--encrypt`, `--compress`, `--resume` sind vorbereitet, aber funktional erst in späteren Phasen.

---

## Befehle

### `send`
**Synopsis**

p2p-copy send SERVER CODE FILE [FILE ...] [OPTIONS]

Argumente (positional)

    SERVER — Relay-URL, z. B. ws://localhost:8765 (für Produktion später wss://…)

    CODE — gemeinsames Passwort/Code zum Pairing

    FILE — eine oder mehrere Dateien (Phase 2: nur die erste wird gesendet)

Optionen

    --encrypt, -e — End-to-End-Verschlüsselung aktivieren (reserviert)

    --compress {auto,on,off} — Kompressionsmodus (reserviert)

    --resume / --no-resume — Übertragung fortsetzen (reserviert)

    --help — Hilfe anzeigen

Beispiele
```bash
# Lokal, minimal
p2p-copy send ws://localhost:8765 demo sample.txt

# Mehrere Dateien (Phase 2: nur sample.txt wird gesendet)
p2p-copy send ws://localhost:8765 demo sample.txt notes.md

# Mit (späteren) Features
p2p-copy send ws://localhost:8765 demo sample.txt --encrypt --compress on --resume
``` 
---

### `receive`

**Synopsis**

p2p-copy receive SERVER CODE [--out DIR] [OPTIONS]

Argumente (positional)

    SERVER — Relay-URL, z. B. ws://localhost:8765

    CODE — gemeinsames Passwort/Code zum Pairing

Optionen

    --out, -o DIR — Zielverzeichnis (Standard: aktuelles Verzeichnis)

    --resume / --no-resume — Fortsetzen (reserviert)

    --help — Hilfe anzeigen

Beispiele
```bash
# In ./downloads empfangen
p2p-copy receive ws://localhost:8765 demo --out ./downloads

# In aktuelles Verzeichnis empfangen
p2p-copy receive ws://localhost:8765 demo
```  
---  


## Typischer Ablauf (3 Terminals)

```bash
# Relay starten 
python server/relay.py --host localhost --port 8765
```

```bash
# Receiver (wartet)
p2p-copy receive ws://localhost:8765 demo --out ./downloads
```

```bash
# Sender
echo "test phase2" > sample.txt # erschafft das Testfile
p2p-copy send ws://localhost:8765 demo sample.txt
```

Ergebnis: downloads/sample.txt enthält den gesendeten Inhalt.

---  


## Hinweise

    Für lokale Tests ws://localhost:8765 verwenden; WSS auf 443 folgt später (benötigt Berechtigungen und TLS).

    Der Empfänger hat keine --encrypt/--compress-Flags; der Sender entscheidet (Protokoll verhandelt das später).

    chunk_size ist intern und nicht per CLI einstellbar.