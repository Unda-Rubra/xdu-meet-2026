"""Bounded Minecraft RCON transport. Credentials are read from a local file."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import socket
import struct
import sys
import tempfile

MAX_PACKET = 4 * 1024 * 1024
MAX_RESPONSE = 16 * 1024 * 1024


class RconError(RuntimeError):
    pass


class Rcon:
    def __init__(self, host: str, port: int, password: str, timeout: float = 10):
        endpoint = hashlib.sha256(f"{host}:{port}".encode()).hexdigest()[:16]
        self.lock_path = Path(tempfile.gettempdir()) / f"xdu-rcon-{endpoint}.lock"
        self.socket = socket.create_connection((host, port), timeout=timeout)
        try:
            self.socket.settimeout(timeout)
            self.send(1, 3, password)
            while True:
                request_id, kind, _ = self.receive()
                if request_id == -1:
                    raise RconError("RCON authentication rejected")
                if request_id == 1 and kind == 2:
                    break
        except BaseException:
            self.close()
            raise
        self.next_id = 10

    def close(self) -> None:
        self.socket.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _read(self, size: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < size:
            block = self.socket.recv(size - len(chunks))
            if not block:
                raise RconError("RCON connection closed before complete response")
            chunks.extend(block)
        return bytes(chunks)

    def send(self, request_id: int, kind: int, body: str) -> None:
        encoded = body.encode("utf-8")
        if b"\x00" in encoded or len(encoded) > 32758:
            raise RconError("Invalid or oversized RCON command")
        packet = struct.pack("<ii", request_id, kind) + encoded + b"\x00\x00"
        self.socket.sendall(struct.pack("<i", len(packet)) + packet)

    def receive(self) -> tuple[int, int, bytes]:
        size = struct.unpack("<i", self._read(4))[0]
        if not 10 <= size <= MAX_PACKET:
            raise RconError("Invalid RCON packet length")
        packet = self._read(size)
        if packet[-2:] != b"\x00\x00":
            raise RconError("Invalid RCON packet termination")
        request_id, kind = struct.unpack("<ii", packet[:8])
        return request_id, kind, packet[8:-2]

    def command(self, command: str) -> str:
        # Native RCON response ownership must not overlap across local clients.
        # This includes health probes, control commands and snapshot readers.
        with self.lock_path.open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            try:
                return self._command(command)
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def _command(self, command: str) -> str:
        request_id = self.next_id
        boundary_id = request_id + 1
        self.next_id += 2
        self.send(request_id, 2, command)
        # Wait for the first response before sending the delimiter. Vanilla's
        # request reader can reject coalesced back-to-back command frames.
        boundary_sent = False
        chunks = bytearray()
        while True:
            current_id, kind, data = self.receive()
            if not boundary_sent:
                self.send(boundary_id, 2, "")
                boundary_sent = True
            if current_id == boundary_id:
                return chunks.decode("utf-8", errors="strict")
            if current_id != request_id or kind != 0:
                raise RconError("Unexpected RCON response identity or type")
            chunks.extend(data)
            if len(chunks) > MAX_RESPONSE:
                raise RconError("RCON response exceeds configured bound")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=25575)
    parser.add_argument("--secret", type=Path, default=Path("/run/secrets/rcon"))
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        password = args.secret.read_text().strip()
        if not password:
            raise RconError("Empty RCON credential")
        command = sys.stdin.read(32760)
        if not command.strip() or len(command.encode("utf-8")) > 32758:
            raise RconError("Provide one bounded command on stdin")
        if "\n" in command.strip() or "\r" in command:
            raise RconError("Only one command is accepted")
        with Rcon(args.host, args.port, password, args.timeout) as client:
            response = client.command(command.strip())
        print(json.dumps({"response": response}, ensure_ascii=False) if args.json else response)
        return 0
    except (OSError, UnicodeError, RconError) as error:
        print(f"rcon: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
