import asyncio
from pathlib import Path

# Import the needed functions from the api, maybe alias them
from p2p_copy import receive as api_receive

def usage_of_receive():
    # If TLS is used the protocol/url-prefix changes from ws to wss
    # To copy over a Server use
    host, port = "relay.example.org", 443
    server_url = f"wss://{host}:{port}"

    # For local tests use
    host, port = "localhost", 8765
    server_url = f"ws://{host}:{port}"

    # A shared code that will be used as passphrase
    # It must only be known by trusted peers
    code = "demoCode123"

    # Optionally End-to-End encryption can be enabled if set to True
    # Sender and receiver need to use the same settings
    encrypt = True

    # Define a directory to store received files in
    # Else they end up in the current directory
    out_dir = Path("downloads")

    # Start receiving in coroutine
    # Awaiting the coroutine returns the return code
    # Any nonzero return code indicates an error
    receive_coroutine = api_receive(server=server_url, code=code, encrypt=encrypt, out=str(out_dir))
    return receive_coroutine

if __name__ == "__main__":
    # run the eventloop
    asyncio.run(usage_of_receive())
    print("done receiving")