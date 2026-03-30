import os
import asyncio


# Windows Fix: "too many file descriptors in select()"
# Uvicorn on Windows defaults to SelectorEventLoop which has a 512 limit.
# We MUST set ProactorEventLoop *before* uvicorn starts.
if os.name == "nt":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    # loop="none" prevents uvicorn from overriding our ProactorEventLoop override
    uvicorn.run("main:app", host="127.0.0.1", port=8000, loop="none")
