import asyncio
import websockets
import json

HOST = "localhost"  # or your HyperHDR IP
PORT = 8090         # or the actual WS port
TAN = 1             # transaction number

async def main():
    uri = f"ws://{HOST}:{PORT}"
    async with websockets.connect(uri) as ws:
        print("[+] Connected to HyperHDR WebSocket")

        # 1. Start LED colors stream
        start_msg = {
            "command": "ledcolors",
            "subcommand": "ledstream-start",
            "tan": TAN
        }

        await ws.send(json.dumps(start_msg))
        print("[+] LED color stream started")

        try:
            # 2. Listen for a few frames
            for _ in range(10):  # receive 10 messages
                msg = await ws.recv()
                try:
                    data = json.loads(msg)
                    print("[Frame]", data)
                except json.JSONDecodeError:
                    print("[Binary frame received]", type(msg), len(msg))

        finally:
            # 3. Stop LED colors stream
            stop_msg = {
                "command": "ledcolors",
                "subcommand": "ledstream-stop",
                "tan": TAN
            }
            await ws.send(json.dumps(stop_msg))
            print("[+] LED color stream stopped")

            # 4. Close connection
            await ws.close()
            print("[+] Connection closed")

if __name__ == "__main__":
    asyncio.run(main())