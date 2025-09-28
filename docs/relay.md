# Relay Setup

The relay server pairs senders and receivers using their shared code hash, forwarding data without storage. It supports TLS and binds to a specified host and port. One sender and one receiver are allowed per code.

For security details, see [Security](./security.md). For CLI usage, see [Usage](./usage.md).

## Quick Start

For development (no TLS):

```bash
p2p-copy run-relay-server localhost 8765 --no-tls
```

For production (TLS recommended):
1. Already have or generate trusted TLS certificates (e.g., via Let's Encrypt).
2. Run:
   ```bash
   p2p-copy run-relay-server 0.0.0.0 443 \
   --certfile /etc/letsencrypt/live/relay.example.com/fullchain.pem \
   --keyfile /etc/letsencrypt/live/relay.example.com/privkey.pem
   ```

## Configuration

### TLS
- Enabled by default or explicitly with `--tls`.
- Requires `--certfile` and `--keyfile` (PEM format).
- Generate certificates using tools like Certbot:

```bash
sudo certbot certonly --standalone -d relay.example.com # --register-unsafely-without-email
```

- Set up renewal via crontab:

```bash
sudo crontab -e
# Add: 0 4 * * * certbot renew --deploy-hook "systemctl reload run-relay-server.service"
```

### Port Privileges
- Ports below 1024 (e.g., 443) require elevated privileges.
- Run as root or use capabilities (e.g., `setcap` for specific permissions).
- Using port forwarding or a reverse proxy might also be elegant solutions. 

### Logging
- Logs to stdout (or a file if redirected).
- Suppresses verbose handshake errors caused by non-WebSocket traffic.
- Minimal output on localhost for testing.

### Scaling
- Low CPU and memory usage due to I/O-focused design.
- No persistence; restarts clear pairings.
- Performance limited by network bandwidth.

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
WorkingDirectory=/root
StandardOutput=append:/root/run-relay-server.log
StandardError=inherit
ExecStart=/root/.venv/bin/p2p-copy run-relay-server 0.0.0.0 443 --certfile /etc/letsencrypt/live/relay.example.com/fullchain.pem --keyfile /etc/letsencrypt/live/relay.example.com/privkey.pem
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=multi-user.target
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now run-relay-server.service
```

### Firewall
- Open the bound port (e.g., 443).
- No additional ports required.

For common issues, see [Troubleshooting](./troubleshooting.md). For features, see [Features](./features.md).