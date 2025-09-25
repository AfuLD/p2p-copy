# asyncio is used to run code asynchronously in an event-loop
import asyncio
from p2p_copy_server import run_relay

def usage_of_relay():
    # To copy over a network listen on all interfaces on port 443
    # This might require elevated privileges
    host, port = "0.0.0.0", 443
    # For local tests use this
    host, port = "localhost", 8765


    # Start the relay. It runs in a coroutine
    # host and port are always required
    # If TLS is used (which is the default) TLS cert- and keyfile are also required
    """
    relay_coroutine = run_relay(host=host, port=port, use_tls=True,
        certfile="/etc/letsencrypt/live/relay.example.org/fullchain.pem",
        keyfile="/etc/letsencrypt/live/relay.example.org/privkey.pem")
    """

    # For local tests instead, no TLS needs to be used
    relay_coroutine = run_relay(host=host, port=port, use_tls=False)

    # If the relay should not run forever, add a timeout
    relay_coroutine_with_timeout = asyncio.wait_for(relay_coroutine, timeout=20)
    return relay_coroutine_with_timeout

if __name__ == "__main__":
    # run the eventloop
    try:
        asyncio.run(usage_of_relay())
    except (asyncio.TimeoutError, KeyboardInterrupt):
        print("relay stopped")