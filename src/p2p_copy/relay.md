# Relay Setup

The relay server acts as a lightweight middleman to pair senders and receivers without storing data. It binds to a host/port, supports TLS, and uses a shared code hash for matching (one sender + one receiver per code).

## Quick Start

Run locally for development:
```bash
p2p-copy run-relay-server localhost 8765 --no-tls
```

For production (TLS recommended):
1. Already have or generate trusted TLS certs (e.g., via Let's Encrypt).
2. Run:
   ```bash
   p2p-copy run-relay-server 0.0.0.0 443 \
   --certfile /etc/letsencrypt/live/relay.example.com/fullchain.pem \
   --keyfile /etc/letsencrypt/live/relay.example.com/privkey.pem
   ```

## Configuration

### TLS
- Enabled by default (`--tls`).
- Requires `--certfile` and `--keyfile` (PEM format).
- Use certbot to create domain-validated certs:

```bash
sudo certbot certonly --standalone -d relay.example.com # --register-unsafely-without-email
```

-  Set up a crontab for monthly cert renew and restart of the relay app if cert changed:

```bash
sudo crontab -e  # opens a file in editor
#add this to it without "#": 
# 0 4 * * * certbot renew --deploy-hook "systemctl reload run-relay-server.service" 
```

### Port privileges
- to use port 443 you need elevated privileges
- easy solution: run as root 
- advanced cleaner solution: give limited precise privileges

### Logging
- Concise logger suppresses long handshake failure tracebacks.
- Handshake failures happen when non-user packages arrive at 443
- Logger prints to std.out or to log file if redirected
- For testing on localhost no logs will be printed

### Scaling
- CPU usage is low since relay does nothing but network I/O
- Memory usage is low since files are streamed in chunks.
- No storage usage, no persistence; restarts clear active pairings.
- Performance usually is limited by network bandwidth

## Deployment

### Systemd Service 
- Use a service to perpetually run and restart the relay 
- it will log to a file
- Create the service file `/etc/systemd/system/run-relay-server.service`:
```
[Unit]
Description=WebSocket File-Forwarding Server
After=network.target

[Service]
Type=simple
# no need to specify a non-root User= line when running as root
WorkingDirectory=/root
StandardOutput=append:/root/run-relay-server.log
StandardError=inherit
ExecStart=/root/.venv/bin/p2p-copy run-relay-server 0.0.0.0 443 --certfile /etc/letsencrypt/live/relay.example.com/fullchain.pem --keyfile /etc/letsencrypt/live/relay.example.com/privkey.pem
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Enable/start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now run-relay-server.service
```

### Firewall
- Open port 443 (or whichever is actually used)
- No other ports needed.


For troubleshooting, see [Troubleshooting](troubleshooting.md).
