import asyncio
import websockets
import json

async def test_tick():
    uri = "wss://ws.binaryws.com/websockets/v3?app_id=1089"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"ticks": "R_10", "subscribe": 1}))
        res = await ws.recv()
        print("Initial response:", res)
        # some initial responses might be generic, let's get a few
        for _ in range(3):
            msg = await ws.recv()
            print("Tick:", msg)

asyncio.run(test_tick())
