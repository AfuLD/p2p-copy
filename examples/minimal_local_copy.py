# asyncio is used to run code asynchronously in an event-loop
import asyncio

from examples.receive_usage import usage_of_receive
from examples.relay_usage import usage_of_relay
from examples.send_usage import usage_of_send


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