import os
import sys
import asyncio

# Windows Fix: "too many file descriptors in select()"
# Uvicorn on Windows defaults to SelectorEventLoop which has a 512 limit.
# We MUST set ProactorEventLoop *before* uvicorn starts.
if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    # Get port from command line arguments or use default
    port = 8001
    for i, arg in enumerate(sys.argv):
        if arg == "--port" and i + 1 < len(sys.argv):
            port = int(sys.argv[i + 1])

    # loop="none" prevents uvicorn from overriding our ProactorEventLoop override
    uvicorn.run("main:app", host="127.0.0.1", port=port, loop="none")
