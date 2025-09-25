import asyncio
import time
from pathlib import Path

# Import the needed functions from the api, maybe alias them
from p2p_copy import send as api_send

def usage_of_send():
    # If TLS is used the protocol/url-prefix changes from ws to wss
    # To copy over a Server use
    host, port = "relay.example.org", 443
    server_url = f"wss://{host}:{port}"

    host, port = "localhost", 8765
    server_url = f"ws://{host}:{port}"

    # A shared code that will be used as passphrase
    # It must only be known by trusted peers
    code = "demoCode123"

    # Optionally End-to-End encryption can be enabled if set to True
    # Sender and receiver need to use the same settings
    encrypt = True

    # The send function will automatically decide whether files should be compressed
    # Optionally compression can be manually set to "on", "off" or "auto"
    compress = "on"
    # For clarity the enum can be used
    from p2p_copy import CompressMode
    compress = CompressMode.on

    # The resume keyword can be used to skip files or parts of files that already exist on the receiver side
    # Else the send function will send each file in full and overwrite existing files with the same name
    resume = True

    # Create a test file to be sent
    src = Path("sample.txt")
    src.write_text("sample text created: " + time.ctime())

    # Prepare a list of multiple paths
    # Those can be files or directories that will be sent
    paths = [str(src)]

    # Start sending in a coroutine
    # Awaiting the coroutine returns the return code
    # Any nonzero return code indicates an error
    send_coroutine = api_send(server=server_url, code=code, files=paths, encrypt=encrypt, compress=compress, resume=resume)
    return send_coroutine

if __name__ == "__main__":
    # run the eventloop
    asyncio.run(usage_of_send())
    print("done sending")
