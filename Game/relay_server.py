"""
relay_server.py
─────────────────────────────────────────────────────────────
Tiny matchmaking relay for playing Arena Fighters over the internet
without port forwarding.

Run it on any machine with a public IP (a cheap VPS, a cloud VM, a
Raspberry Pi with one forwarded port …):

    python relay_server.py              # listens on 0.0.0.0:7777
    python relay_server.py --port 9000

Players then put  your-server-address:7777  in the "Relay server"
field of the Online screen.  The host gets a 5-letter room code, the
friend types it, and the relay pipes bytes between them.

The relay never looks inside the game traffic and needs no extra
packages (pure Python standard library).
"""

import argparse
import asyncio
import time

from net import GAME_ID, random_room_code

ROOM_TIMEOUT = 30 * 60      # an unjoined room expires after 30 minutes
HANDSHAKE_TIMEOUT = 15

rooms = {}                  # code -> (future resolved with joiner streams, created_at)


def log(*parts):
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


async def pipe(reader, writer):
    try:
        while True:
            data = await reader.read(65536)
            if not data:
                break
            writer.write(data)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        try:
            writer.close()
        except Exception:
            pass


async def handle(reader, writer):
    peer = writer.get_extra_info("peername")
    try:
        line = await asyncio.wait_for(reader.readline(), HANDSHAKE_TIMEOUT)
    except (asyncio.TimeoutError, ConnectionError):
        writer.close()
        return
    parts = line.decode(errors="replace").split()
    if len(parts) < 2 or parts[1] != GAME_ID:
        writer.write(b"ERR unknown game\n")
        writer.close()
        return

    if parts[0] == "HOST":
        await host_room(reader, writer, peer)
    elif parts[0] == "JOIN" and len(parts) == 3:
        await join_room(parts[2].upper(), reader, writer, peer)
    else:
        writer.write(b"ERR bad request\n")
        writer.close()


async def host_room(reader, writer, peer):
    code = random_room_code()
    while code in rooms:
        code = random_room_code()
    joined = asyncio.get_running_loop().create_future()
    rooms[code] = (joined, time.time())
    writer.write(f"ROOM {code}\n".encode())
    await writer.drain()
    log(f"room {code} opened by {peer}")

    # wait for a joiner, or for the host to give up (disconnect)
    host_gone = asyncio.ensure_future(reader.read(1))
    done, _ = await asyncio.wait({joined, host_gone}, timeout=ROOM_TIMEOUT,
                                 return_when=asyncio.FIRST_COMPLETED)
    rooms.pop(code, None)
    if joined not in done:
        host_gone.cancel()
        if not joined.done():
            joined.cancel()
        writer.close()
        log(f"room {code} closed (host left or timeout)")
        return
    host_gone.cancel()
    j_reader, j_writer, finished = joined.result()
    writer.write(b"PAIRED\n")
    await writer.drain()
    log(f"room {code} paired, relaying")
    await asyncio.gather(pipe(reader, j_writer), pipe(j_reader, writer))
    finished.set_result(True)
    log(f"room {code} finished")


async def join_room(code, reader, writer, peer):
    entry = rooms.pop(code, None)
    if entry is None or entry[0].done():
        writer.write(b"ERR room not found\n")
        writer.close()
        return
    writer.write(b"OK\n")
    await writer.drain()
    finished = asyncio.get_running_loop().create_future()
    entry[0].set_result((reader, writer, finished))
    log(f"{peer} joined room {code}")
    await finished          # keep this connection's handler alive while piping


async def main(host, port):
    server = await asyncio.start_server(handle, host, port)
    log(f"Arena Fighters relay listening on {host}:{port}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Arena Fighters online relay")
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=7777)
    args = ap.parse_args()
    try:
        asyncio.run(main(args.host, args.port))
    except KeyboardInterrupt:
        pass
