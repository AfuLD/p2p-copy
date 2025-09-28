# p2p-copy CLI Usage (Phase 2)


---

## Befehle

### `send`
**Synopsis**

p2p-copy send SERVER CODE FILE [FILE ...] [OPTIONS]

Argumente (positional)

    SERVER — Relay-URL, z. B. ws://localhost:8765 (für Produktion später wss://…:443)

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
# In /downloads empfangen
p2p-copy receive ws://localhost:8765 demo --out ../downloads

# In aktuelles Verzeichnis empfangen
p2p-copy receive ws://localhost:8765 demo
```  
---  

### `run-relay-server`

**Synopsis**

p2p-copy run-relay-server HOST PORT [--tls/--no-tls] [--certfile PATH] [--keyfile PATH]

Argumente

    HOST — Interface, z. B. localhost oder 0.0.0.0

    PORT — verwendeter Port, z. B. 8765 oder 443

Optionen

    --tls/--no-tls — TLS (WSS) verwenden. Standard: -tls verwendet 

    --certfile PATH, --keyfile PATH — notwendig, wenn --tls gesetzt ist

    --help — Hilfe anzeigen

Beispiele

```bash
# Lokaler Relay (ohne TLS)
p2p-copy run-relay-server localhost 8765 --no-tls

# # Mit TLS (Zertifikat+Key notwendig)
p2p-copy run-relay-server 0.0.0.0 443 --certfile /etc/ssl/certs/fullchain.pem --keyfile /etc/ssl/private/privkey.pem
```

---

## Typischer Ablauf (3 Terminals)

```bash
# Relay starten 
p2p-copy run-relay-server localhost 8765 --no-tls
```

```bash
# Receiver (wartet)
p2p-copy receive ws://localhost:8765 demo --out ../downloads
```

```bash
# Sender
echo "hello test" > sample.txt # erschafft Testfile
p2p-copy send ws://localhost:8765 demo sample.txt
rm sample.txt # entfernt Testfile 
```

Ergebnis: downloads/sample.txt enthält den gesendeten Inhalt.

---  


## Hinweise

    Für lokale Tests ws://localhost:8765 verwenden; WSS auf 443 folgt später (benötigt Berechtigungen und TLS).

    Der Empfänger hat keine --encrypt/--compress-Flags; der Sender entscheidet (Protokoll verhandelt das später).

    chunk_size ist intern und nicht per CLI einstellbar.