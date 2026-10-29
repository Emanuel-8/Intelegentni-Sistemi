"""
net.py
─────────────────────────────────────────────────────────────
Online multiplayer for Arena Fighters.

Model: HOST-AUTHORITATIVE.
  • The host runs the normal game simulation (exactly the same code as
    offline play) with the remote player's keys as Player 2's input.
  • The client sends its key state every frame and draws the snapshots
    the host sends back.  Nothing about the game rules is duplicated.

Transport: TCP, one JSON object per line.  Two ways to connect:
  • Direct  – host listens on DEFAULT_PORT; the client types the host's
              IP (LAN, Wi-Fi, a VPN such as Tailscale/ZeroTier, or a
              forwarded port).  Hosts on the same LAN are discovered
              automatically through a UDP broadcast beacon.
  • Relay   – both players connect out to relay_server.py running on any
              public machine; the host gets a short room code and the
              friend joins with it.  No port forwarding needed.
"""

import json
import random
import socket
import string
import threading
import time
from collections import deque

PROTOCOL_VERSION = 1
DEFAULT_PORT = 50555
DISCOVERY_PORT = 50556
DEFAULT_RELAY_PORT = 7777
GAME_ID = "arena-fighters"

# input button bits
BTN_DASH, BTN_MELEE, BTN_SHOOT = 1, 2, 4


def _encode(msg):
    return (json.dumps(msg, separators=(",", ":")) + "\n").encode()


def parse_address(text, default_port):
    text = text.strip()
    if not text:
        raise ValueError("address is empty")
    if text.count(":") == 1:
        host, port = text.rsplit(":", 1)
        return host.strip(), int(port)
    return text, default_port


def local_ip():
    """Best guess at this machine's LAN address (no packets are sent)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "127.0.0.1"


def _read_line(sock, timeout=15.0, limit=256):
    sock.settimeout(timeout)
    buf = b""
    while not buf.endswith(b"\n"):
        ch = sock.recv(1)
        if not ch:
            raise ConnectionError("connection closed")
        buf += ch
        if len(buf) > limit:
            raise ConnectionError("bad response")
    return buf.decode(errors="replace").strip()


# ─────────────────────────────────────────────
#  PEER: a connected socket with background I/O
# ─────────────────────────────────────────────
class Peer:
    """
    send(msg)        – reliable control message (always delivered, in order)
    send_state(msg)  – "latest wins" slot for snapshots / inputs.  If the
                       network is slower than the game, older states are
                       merged into the newest one instead of piling up.
    """

    def __init__(self, sock):
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(None)
        self.sock = sock
        self.alive = True
        self.error = ""
        self._cv = threading.Condition()
        self._outbox = deque()
        self._slot = None
        self._inbox = deque()
        self._state = None
        self._state_seq = 0
        self._events = []
        self._buttons = 0
        self._sending = False
        self.last_recv = time.time()
        threading.Thread(target=self._send_loop, daemon=True).start()
        threading.Thread(target=self._recv_loop, daemon=True).start()

    # ── sending ────────────────────────────────────────────────
    def send(self, msg):
        with self._cv:
            self._outbox.append(msg)
            self._cv.notify()

    def send_state(self, msg):
        with self._cv:
            old = self._slot
            if old is not None:
                if msg.get("t") == "s":
                    msg["ev"] = old.get("ev", []) + msg.get("ev", [])
                elif msg.get("t") == "i":
                    msg["b"] = msg.get("b", 0) | old.get("b", 0)
            self._slot = msg
            self._cv.notify()

    def _send_loop(self):
        try:
            while self.alive:
                with self._cv:
                    while self.alive and not self._outbox and self._slot is None:
                        self._cv.wait(0.5)
                    batch = list(self._outbox)
                    self._outbox.clear()
                    if self._slot is not None:
                        batch.append(self._slot)
                        self._slot = None
                    self._sending = bool(batch)
                if batch:
                    self.sock.sendall(b"".join(_encode(m) for m in batch))
                with self._cv:
                    self._sending = False
        except OSError as exc:
            self._fail(f"connection lost ({exc.__class__.__name__})")

    # ── receiving ──────────────────────────────────────────────
    def _recv_loop(self):
        buf = b""
        try:
            while self.alive:
                data = self.sock.recv(65536)
                if not data:
                    self._fail("the other player disconnected")
                    return
                self.last_recv = time.time()
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if line:
                        self._dispatch(json.loads(line))
        except (OSError, ValueError) as exc:
            self._fail(f"connection lost ({exc.__class__.__name__})")

    def _dispatch(self, msg):
        kind = msg.get("t")
        with self._cv:
            if kind == "s":
                self._events.extend(msg.pop("ev", []))
                self._state = msg
                self._state_seq += 1
            elif kind == "i":
                self._buttons |= msg.get("b", 0)
                self._state = msg
                self._state_seq += 1
            else:
                self._inbox.append(msg)

    def messages(self):
        with self._cv:
            out = list(self._inbox)
            self._inbox.clear()
        return out

    def latest_state(self):
        """(sequence number, latest state message or None)."""
        with self._cv:
            return self._state_seq, self._state

    def take_events(self):
        with self._cv:
            ev, self._events = self._events, []
        return ev

    def take_input(self):
        """Latest remote input, with every button pressed since the last call."""
        with self._cv:
            st = self._state or {}
            buttons, self._buttons = self._buttons | st.get("b", 0), 0
        return st.get("x", 0), st.get("y", 0), bool(st.get("s", 0)), buttons

    # ── lifecycle ──────────────────────────────────────────────
    def _fail(self, reason):
        if self.alive:
            self.error = reason
        self.close()

    def close(self):
        self.alive = False
        with self._cv:
            self._cv.notify_all()
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            self.sock.close()
        except OSError:
            pass

    def close_gracefully(self, reason="bye", timeout=0.5):
        """Tell the other side we are leaving (via the sender thread, so the
        message is never interleaved with a half-sent snapshot), then close."""
        if self.alive:
            with self._cv:
                self._slot = None
            self.send({"t": "bye", "reason": reason})
            deadline = time.time() + timeout
            while self.alive and time.time() < deadline:
                with self._cv:
                    if not self._outbox and not self._sending:
                        break
                time.sleep(0.01)
        self.close()


# ─────────────────────────────────────────────
#  CONNECTING (runs in a thread so the UI stays alive)
# ─────────────────────────────────────────────
class _Connector:
    def __init__(self):
        self.peer = None
        self.error = ""
        self.status = "starting…"
        self.done = False
        self._cancel = False
        self._socks = []
        threading.Thread(target=self._safe_run, daemon=True).start()

    def _safe_run(self):
        try:
            self._run()
        except Exception as exc:
            if not self._cancel:
                self.error = _friendly_error(exc)
        finally:
            self.done = True

    def _track(self, sock):
        self._socks.append(sock)
        return sock

    def cancel(self):
        self._cancel = True
        for s in self._socks:
            try:
                s.close()
            except OSError:
                pass
        if self.peer:
            self.peer.close()


class HostConnector(_Connector):
    """Waits for one opponent, either on a local port or via a relay."""

    def __init__(self, port=DEFAULT_PORT, relay=None):
        self.port = port
        self.relay = relay
        self.room = ""
        self.addresses = []
        super().__init__()

    def _run(self):
        if self.relay:
            host, port = parse_address(self.relay, DEFAULT_RELAY_PORT)
            self.status = f"Contacting relay {host}:{port}…"
            sock = self._track(socket.create_connection((host, port), timeout=10))
            sock.sendall(f"HOST {GAME_ID}\n".encode())
            reply = _read_line(sock)
            if not reply.startswith("ROOM "):
                raise ConnectionError(reply or "relay refused")
            self.room = reply.split()[1]
            self.status = "Waiting for your friend to join…"
            reply = _read_line(sock, timeout=60 * 30)
            if reply != "PAIRED":
                raise ConnectionError(reply or "relay closed the room")
            if not self._cancel:
                self.peer = Peer(sock)
            return
        srv = self._track(socket.socket(socket.AF_INET, socket.SOCK_STREAM))
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("0.0.0.0", self.port))
        srv.listen(1)
        self.addresses = [f"{local_ip()}:{self.port}"]
        self.status = "Waiting for an opponent…"
        sock, _addr = srv.accept()
        srv.close()
        if not self._cancel:
            self.peer = Peer(sock)


class JoinConnector(_Connector):
    def __init__(self, target, relay=None):
        self.target = target.strip()
        self.relay = relay
        super().__init__()

    def _run(self):
        if self.relay:
            host, port = parse_address(self.relay, DEFAULT_RELAY_PORT)
            self.status = f"Contacting relay {host}:{port}…"
            sock = self._track(socket.create_connection((host, port), timeout=10))
            sock.sendall(f"JOIN {GAME_ID} {self.target.upper()}\n".encode())
            reply = _read_line(sock)
            if reply != "OK":
                raise ConnectionError(reply.replace("ERR ", "") or "room not found")
        else:
            host, port = parse_address(self.target, DEFAULT_PORT)
            self.status = f"Connecting to {host}:{port}…"
            sock = self._track(socket.create_connection((host, port), timeout=8))
        if not self._cancel:
            self.peer = Peer(sock)


def _friendly_error(exc):
    if isinstance(exc, socket.timeout):
        return "Timed out – check the address and the host's firewall."
    if isinstance(exc, ConnectionRefusedError):
        return "Connection refused – is the host waiting in the lobby?"
    if isinstance(exc, socket.gaierror):
        return "Unknown address – check what you typed."
    if isinstance(exc, OSError) and getattr(exc, "errno", None) in (98, 48, 10048):
        return "That port is already in use (is another game hosting?)."
    if isinstance(exc, ValueError):
        return "Address must look like 192.168.1.20 or 192.168.1.20:50555"
    return str(exc) or exc.__class__.__name__


# ─────────────────────────────────────────────
#  LAN DISCOVERY
# ─────────────────────────────────────────────
class LanBeacon:
    """Host side: announces the game on the local network once a second."""

    def __init__(self, info):
        self.info = dict(info, g=GAME_ID, v=PROTOCOL_VERSION)
        self.sock = None
        self.next_send = 0.0
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        except OSError:
            self.sock = None

    def tick(self):
        if self.sock is None or time.time() < self.next_send:
            return
        self.next_send = time.time() + 1.0
        try:
            self.sock.sendto(json.dumps(self.info).encode(), ("255.255.255.255", DISCOVERY_PORT))
        except OSError:
            pass

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None


class LanScanner:
    """Client side: lists games announced on the LAN in the last few seconds."""

    def __init__(self):
        self.games = {}
        self.sock = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if hasattr(socket, "SO_REUSEPORT"):
                try:
                    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
                except OSError:
                    pass
            s.bind(("", DISCOVERY_PORT))
            s.setblocking(False)
            self.sock = s
        except OSError:
            self.sock = None

    def poll(self):
        if self.sock is not None:
            while True:
                try:
                    data, (ip, _port) = self.sock.recvfrom(2048)
                except (BlockingIOError, OSError):
                    break
                try:
                    info = json.loads(data)
                except ValueError:
                    continue
                if info.get("g") == GAME_ID and info.get("v") == PROTOCOL_VERSION:
                    info["addr"] = f"{ip}:{info.get('port', DEFAULT_PORT)}"
                    info["seen"] = time.time()
                    self.games[info["addr"]] = info
        now = time.time()
        self.games = {k: v for k, v in self.games.items() if now - v["seen"] < 3.5}
        return sorted(self.games.values(), key=lambda g: g["addr"])

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None


def random_room_code(n=5):
    alphabet = "".join(c for c in string.ascii_uppercase + string.digits if c not in "O0I1")
    return "".join(random.choice(alphabet) for _ in range(n))
