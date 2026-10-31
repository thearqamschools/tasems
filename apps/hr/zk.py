"""Reading punches straight from a ZKTeco attendance machine on the office network (TCP port 4370).

Written for TASEMS from the published ZKTeco "standalone SDK" protocol (the same one other free tools use), so no
outside library is needed: connect (with the comm key when the machine has one), read the machine's clock and
counts, read the attendance log, disconnect. Read-only: nothing on the machine is changed or deleted.
Project lead, 31 Oct 2026 (ZKTeco face + fingerprint terminal on LAN)."""

import datetime as dt
import socket
from dataclasses import dataclass, field
from struct import pack, unpack

CMD_CONNECT, CMD_EXIT, CMD_AUTH = 1000, 1001, 1102
CMD_ACK_OK, CMD_ACK_UNAUTH = 2000, 2005
CMD_GET_TIME, CMD_GET_FREE_SIZES, CMD_ATTLOG_RRQ = 201, 50, 13
CMD_PREPARE_DATA, CMD_DATA, CMD_FREE_DATA = 1500, 1501, 1502
CMD_PREPARE_BUFFER, CMD_READ_BUFFER = 1503, 1504
USHRT_MAX = 65535
TCP_START = (0x5050, 0x7D82)
MAX_CHUNK = 0xFFC0
DEFAULT_PORT = 4370


class MachineError(Exception):
    pass


@dataclass
class Reading:
    clock: dt.datetime | None = None
    users: int = 0
    records: int = 0
    punches: list = field(default_factory=list)  # (machine user id, naive local datetime)


def checksum(data):
    total = 0
    for i in range(0, len(data) - 1, 2):
        total += data[i] | (data[i + 1] << 8)
        if total > USHRT_MAX:
            total -= USHRT_MAX
    if len(data) % 2:
        total += data[-1]
    while total > USHRT_MAX:
        total -= USHRT_MAX
    total = ~total
    while total < 0:
        total += USHRT_MAX
    return total


def packet(command, session, reply, data=b""):
    """One TCP frame: start marker, length, then command, checksum, session id, reply id and data."""
    body = pack("<4H", command, 0, session, reply) + data
    body = pack("<4H", command, checksum(body), session, reply) + data
    return pack("<HHI", *TCP_START, len(body)) + body


def comm_key(key, session, ticks=50):
    """The machine's comm key (password) scrambled with the session, as the machine expects it."""
    key, k = int(key), 0
    for i in range(32):
        k = (k << 1 | 1) if key & (1 << i) else k << 1
    k += session
    b = pack("<I", k & 0xFFFFFFFF)
    b = bytes([b[0] ^ ord("Z"), b[1] ^ ord("K"), b[2] ^ ord("S"), b[3] ^ ord("O")])
    a1, a2 = unpack("<HH", b)
    b = pack("<HH", a2, a1)
    t = 0xFF & ticks
    return bytes([b[0] ^ t, b[1] ^ t, t, b[3] ^ t])


def decode_time(raw):
    t = unpack("<I", raw)[0]
    second, t = t % 60, t // 60
    minute, t = t % 60, t // 60
    hour, t = t % 24, t // 24
    day, t = t % 31 + 1, t // 31
    month, t = t % 12 + 1, t // 12
    return dt.datetime(t + 2000, month, day, hour, minute, second)


def parse_attendance(data, records):
    """Attendance log → (user id, time). Older machines use 8 or 16 bytes a record, newer ones 40."""
    if len(data) < 4:
        return []
    size = unpack("<I", data[:4])[0]
    data = data[4 : 4 + size]
    if not records:
        return []
    record = size // records
    out = []
    for i in range(0, len(data) - record + 1, record):
        chunk = data[i : i + record]
        if record == 8:
            uid, _status, stamp, _punch = unpack("<HB4sB", chunk)
            user = str(uid)
        elif record == 16:
            user_id, stamp, _status, _punch, _r, _w = unpack("<I4sBB2sI", chunk)
            user = str(user_id)
        elif record >= 40:
            _uid, raw_user, _status, stamp, _punch, _space = unpack("<H24sB4sB8s", chunk[:40])
            user = raw_user.split(b"\x00")[0].decode("ascii", "ignore").strip()
        else:
            raise MachineError(f"unknown record size {record}")
        try:
            out.append((user, decode_time(stamp)))
        except ValueError:
            continue  # a damaged record on the machine
    return out


class Machine:
    def __init__(self, host, port=DEFAULT_PORT, password=0, timeout=10):
        self.host, self.port, self.password, self.timeout = host, int(port or DEFAULT_PORT), password or 0, timeout
        self.sock = None
        self.session, self.reply = 0, USHRT_MAX - 1

    # --- frames ---
    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise MachineError("the machine closed the connection")
            buf += chunk
        return buf

    def _recv_frame(self):
        start = self._recv_exact(8)
        m1, m2, length = unpack("<HHI", start)
        if (m1, m2) != TCP_START:
            raise MachineError("not a ZKTeco machine (wrong reply)")
        body = self._recv_exact(length)
        command, _checksum, session, reply = unpack("<4H", body[:8])
        return command, session, reply, body[8:]

    def _send(self, command, data=b""):
        self.reply = (self.reply + 1) % USHRT_MAX
        self.sock.sendall(packet(command, self.session, self.reply, data))
        command, _session, reply, payload = self._recv_frame()
        self.reply = reply
        return command, payload

    # --- commands ---
    def connect(self):
        try:
            self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as error:
            raise MachineError(str(error)) from error
        self.reply = (self.reply + 1) % USHRT_MAX
        self.sock.sendall(packet(CMD_CONNECT, 0, self.reply))
        command, session, reply, _payload = self._recv_frame()
        self.session, self.reply = session, reply
        if command == CMD_ACK_UNAUTH:
            command, _p = self._send(CMD_AUTH, comm_key(self.password, self.session))
        if command != CMD_ACK_OK:
            raise MachineError("the machine refused the connection (check the comm key)")
        return self

    def disconnect(self):
        if self.sock:
            try:
                self._send(CMD_EXIT)
            except (OSError, MachineError):
                pass
            self.sock.close()
            self.sock = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.disconnect()

    def clock(self):
        command, payload = self._send(CMD_GET_TIME)
        return decode_time(payload[:4]) if command == CMD_ACK_OK and len(payload) >= 4 else None

    def sizes(self):
        command, payload = self._send(CMD_GET_FREE_SIZES)
        if command != CMD_ACK_OK or len(payload) < 80:
            return 0, 0
        fields = unpack("<20i", payload[:80])
        return fields[4], fields[8]  # users, attendance records

    def _read_chunk(self, start, size):
        command, payload = self._send(CMD_READ_BUFFER, pack("<ii", start, size))
        if command == CMD_DATA:
            return payload
        if command != CMD_PREPARE_DATA:
            raise MachineError("unexpected reply while reading")
        total = unpack("<I", payload[:4])[0]
        data = b""
        while len(data) < total:
            command, _s, _r, part = self._recv_frame()
            if command != CMD_DATA:
                break
            data += part
        command, _s, _r, _p = self._recv_frame()  # the closing ACK_OK
        return data

    def read_buffer(self, command):
        cmd, payload = self._send(CMD_PREPARE_BUFFER, pack("<bhii", 1, command, 0, 0))
        if cmd == CMD_DATA:
            return payload
        if cmd != CMD_ACK_OK or len(payload) < 5:
            raise MachineError("the machine did not send its records")
        size = unpack("<I", payload[1:5])[0]
        data, start = b"", 0
        while start < size:
            part = min(MAX_CHUNK, size - start)
            data += self._read_chunk(start, part)
            start += part
        self._send(CMD_FREE_DATA)
        return data

    def attendance(self, records):
        if not records:
            return []
        return parse_attendance(self.read_buffer(CMD_ATTLOG_RRQ), records)


def read(host, port=DEFAULT_PORT, password=0, with_punches=True):
    """Clock, counts and (optionally) every punch on the machine."""
    with Machine(host, port, password) as machine:
        reading = Reading(clock=machine.clock())
        reading.users, reading.records = machine.sizes()
        if with_punches:
            reading.punches = machine.attendance(reading.records)
        return reading
