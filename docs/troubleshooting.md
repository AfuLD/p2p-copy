# Troubleshooting

This page addresses common issues with p2p-copy. For setup, see [Installation](./installation.md) and [Relay Setup](./relay.md). For usage, see [Usage](./usage.md).

## Connection Problems

- **No Connection to Relay**: Ensure relay is running and accessible. Check firewall rules allow the port.
- **Timeout Waiting for peer**: Sender and receiver must use the same code, encrypt flag and relay.
- **Handshake Failed**: Non-WebSocket traffic caused by use of the wrong protocol (i.e. WS instead of WSS)
- **Duplicate Role for Code**: Two senders or receivers with the same code. Use unique codes per pair.

## Transfer Errors

- **Chained Checksum Mismatch**: Data corruption in transit. Retry; check network stability.
- **Size Mismatch**: Incomplete transfer. Use `--resume` to continue.
- **Unexpected Frame/Control**: Protocol violation. Ensure matching versions of sender/receiver.
>Note: No transfer errors were actually encountered in testing.

## Encryption Issues

- **ModuleNotFoundError for Security Libs**: Install with `[security]` extras. See [Installation](./installation.md).

## Performance and Resource Issues

- **High RAM Usage on Transfer Start**: Encryption uses memory-hard KDF which temporarily spikes memory usage.
- **Slow Transfers**: Slow network speed of either relay, sender or receiver will limit transfer speed. 

## Relay-Specific

- **Port Binding Fails**: Privileges needed for low ports. Run as root or use higher ports for testing.
- **TLS Errors**: Invalid or untrusted certificates. Use Certbot for valid ones; check file paths.
- **No Logs on Localhost**: Expected for testing; deploy to non-localhost for full logging.

## General Tips

- Test locally with `--no-tls` and on user-space ports.
- If using a relay service check the system logs (systemd status).
- If issues persist, review code or report on GitHub.

For security-related troubleshooting, see [Security](./security.md). For features, see [Features](./features.md).
