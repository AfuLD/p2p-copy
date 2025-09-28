>Note: Complete examples in python files can be found in /examples. Tests can be found in /test. 


```python
# import the needed functions from the api, maybe alias them
from p2p_copy import send as api_send, receive as api_receive
from p2p_copy_server import run_relay
imported_functions = api_send, api_receive, run_relay

# alternatively just import the modules and refer accordingly
import p2p_copy, p2p_copy_server
imported_module_functions = p2p_copy.send, p2p_copy.receive, p2p_copy_server.run_relay

assert imported_functions == imported_module_functions, "Error: functions are different"

```

```python
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

```

```python
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

```

```python
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

```

```python
# asyncio is used to run code asynchronously in an event-loop
import asyncio

async def local_test():
    """
    After running this a file should be copied into "examples/downloads"
    The same can be done by running the *usage.py examples separately at the same time
    """

    # Usage code examples need to either run on different machines or in different processes/tasks/threats
    # Else awaiting one will block the others

    # Step 1 Create a task that runs the relay in parallel
    relay_task = asyncio.create_task(usage_of_relay())
    await asyncio.sleep(0.1)  # give it a moment to bind

    # Step 2 or 3 Create a task that runs the receiver in parallel
    # After the relay was started
    # Order between starting send or receive does not matter
    recv_task = asyncio.create_task(usage_of_receive())

    # Step 2 or 3 Create a task that runs the sender in parallel
    send_task = asyncio.create_task(usage_of_send())

    # Get the return codes
    # This will block until both tasks are finished
    return_code_receive = await recv_task
    return_code_send = await send_task

    # Alternatively avoid blocking for too long by interpreting as error after a timeout
    try:
        return_code_send = await asyncio.wait_for(send_task, timeout=10)
    except asyncio.TimeoutError:
        return_code_send = -1
    try:
        return_code_receive = await asyncio.wait_for(recv_task, timeout=1)
    except asyncio.TimeoutError:
        return_code_receive = -1

    # Make sure no error codes had been returned
    assert return_code_receive == 0 and return_code_send == 0, "Returned with error code"

    # Step 4 cancel the relay task
    try:
        relay_task.cancel()
        await relay_task
    except asyncio.CancelledError:
        pass

if __name__ == "__main__":
    # run the eventloop
    asyncio.run(local_test())
```