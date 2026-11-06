"""Reading punches straight from a ZKTeco attendance machine on the office network (TCP port 4370).

Written for TASEMS from the published ZKTeco "standalone SDK" protocol (the same one other free tools use), so no
outside library is needed: connect (with the comm key when the machine has one), read the machine's clock and
counts, read the attendance log, disconnect. Read-only: nothing on the machine is changed or deleted.
Project lead, 31 Oct 2026 (ZKTeco face + fingerprint terminal on LAN)."""

import datetime as dt
import ipaddress
import socket
from dataclasses import dataclass, field
from struct import pack, unpack

CMD_CONNECT, CMD_EXIT, CMD_AUTH = 1000, 1001, 1102
CMD_ACK_OK, CMD_ACK_UNAUTH = 2000, 2005
CMD_GET_TIME, CMD_GET_FREE_SIZES, CMD_ATTLOG_RRQ, CMD_USERTEMP_RRQ = 201, 50, 13, 9
FCT_USER = 5
CMD_PREPARE_DATA, CMD_DATA, CMD_FREE_DATA = 1500, 1501, 1502
CMD_PREPARE_BUFFER, CMD_READ_BUFFER = 1503, 1504
USHRT_MAX = 65535
TCP_START = (0x5050, 0x7D82)
MAX_CHUNK = 0xFFC0
MAX_CHUNK_UDP = 16 * 1024
DEFAULT_PORT = 4370


class MachineError(Exception):
    pass


@dataclass
class Reading:
    clock: dt.datetime | None = None
    users: int = 0
    records: int = 0
    punches: list = field(default_factory=list)  # (machine user id, naive local datetime)
    transport: str = "tcp"
    names: dict = field(default_factory=dict)  # machine user number → name


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
    """One TCP frame: start marker, length, then command, checksum, session id, reply id and data.

    As the machines expect it (and as pyzk and node-zklib send it): the checksum is worked out with the *previous*
    reply id `reply`, and the frame carries `reply + 1`. A frame with any other checksum is dropped by the machine
    without an answer, which looks like a time-out."""
    body = pack("<4H", command, 0, session, reply) + data
    total = checksum(body)
    reply = (reply + 1) % USHRT_MAX
    body = pack("<4H", command, total, session, reply) + data
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
    if record <= 0:
        return []
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


def _text(raw):
    return raw.split(b"\x00")[0].decode("utf-8", "ignore").strip()


def parse_users(data, count):
    """User list → {user number: name}. Records are 28 bytes (older machines), 72 or 120 bytes (NGTeco)."""
    if len(data) < 4 or not count:
        return {}
    size = unpack("<I", data[:4])[0]
    data = data[4 : 4 + size]
    record = size // count
    if record <= 0:
        return {}
    out = {}
    for i in range(0, len(data) - record + 1, record):
        chunk = data[i : i + record]
        if record == 28:
            _uid, _priv, _pw, name, _card, _group, _tz, user_id = unpack("<HB5s8sIxBhI", chunk)
            number, name = str(user_id), _text(name)
        elif record == 120:
            number = _text(chunk[96:120])
            name = f"{_text(chunk[35:59])} {_text(chunk[59:83])}".strip()
        elif record >= 72:
            _uid, _priv, _pw, name, _card, _group, user_id = unpack("<HB8s24sIx7sx24s", chunk[:72])
            number, name = _text(user_id), _text(name)
        else:
            raise MachineError(f"unknown user record size {record}")
        if number:
            out[number] = name
    return out


class Machine:
    """One connection to the machine. Newer machines talk TCP; many older ones (and some newer firmware) only
    answer UDP on the same port, so `transport` is "tcp" or "udp" (`read()` tries both)."""

    def __init__(self, host, port=DEFAULT_PORT, password=0, timeout=10, transport="tcp"):
        self.host, self.port, self.password, self.timeout = host, int(port or DEFAULT_PORT), password or 0, timeout
        self.transport = transport
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
        if self.transport == "udp":
            body = self.sock.recv(65535)  # one datagram is one whole frame, without the TCP start marker
        else:
            start = self._recv_exact(8)
            m1, m2, length = unpack("<HHI", start)
            if (m1, m2) != TCP_START:
                raise MachineError("not a ZKTeco machine (wrong reply)")
            body = self._recv_exact(length)
        if len(body) < 8:
            raise MachineError("not a ZKTeco machine (short reply)")
        command, _checksum, session, reply = unpack("<4H", body[:8])
        return command, session, reply, body[8:]

    def _frame(self, command, session, reply, data=b""):
        frame = packet(command, session, reply, data)
        return frame[8:] if self.transport == "udp" else frame

    def _send(self, command, data=b""):
        self.sock.sendall(self._frame(command, self.session, self.reply, data))
        command, _session, reply, payload = self._recv_frame()
        self.reply = reply
        return command, payload

    # --- commands ---
    def connect(self):
        try:
            if self.transport == "udp":
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                self.sock.settimeout(self.timeout)
                self.sock.connect((self.host, self.port))
            else:
                self.sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        except OSError as error:
            self.close()
            raise MachineError(f"could not open a connection: {error}") from error
        try:
            self.session, self.reply = 0, USHRT_MAX - 1
            self.sock.sendall(self._frame(CMD_CONNECT, 0, self.reply))
            command, session, reply, _payload = self._recv_frame()
        except OSError as error:
            self.close()
            raise MachineError(f"connected, but no reply to TASEMS: {error}") from error
        self.session, self.reply = session, reply
        if command == CMD_ACK_UNAUTH:
            command, _p = self._send(CMD_AUTH, comm_key(self.password, self.session))
        if command != CMD_ACK_OK:
            self.close()
            raise MachineError("the machine refused the connection (check the comm key)")
        return self

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None

    def disconnect(self):
        if self.sock:
            try:
                self._send(CMD_EXIT)
            except (OSError, MachineError):
                pass
            self.close()

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
        data = b""
        while True:  # data frames, then the closing ACK_OK
            command, _s, _r, part = self._recv_frame()
            if command == CMD_DATA:
                data += part
            elif command == CMD_ACK_OK:
                return data
            else:
                raise MachineError("unexpected reply while reading")

    def read_buffer(self, command, fct=0):
        cmd, payload = self._send(CMD_PREPARE_BUFFER, pack("<bhii", 1, command, fct, 0))
        if cmd == CMD_DATA:
            return payload
        if cmd != CMD_ACK_OK or len(payload) < 5:
            raise MachineError("the machine did not send its records")
        size = unpack("<I", payload[1:5])[0]
        data, start = b"", 0
        while start < size:
            part = min(MAX_CHUNK_UDP if self.transport == "udp" else MAX_CHUNK, size - start)
            data += self._read_chunk(start, part)
            start += part
        self._send(CMD_FREE_DATA)
        return data

    def users(self, count):
        """Machine user number → name (read only; the user list as pyzk reads it)."""
        if not count:
            return {}
        return parse_users(self.read_buffer(CMD_USERTEMP_RRQ, FCT_USER), count)

    def attendance(self, records):
        if not records:
            return []
        return parse_attendance(self.read_buffer(CMD_ATTLOG_RRQ), records)


def _read_with(transport, host, port, password, with_punches, timeout):
    with Machine(host, port, password, timeout=timeout, transport=transport) as machine:
        reading = Reading(clock=machine.clock(), transport=transport)
        reading.users, reading.records = machine.sizes()
        if with_punches:
            reading.punches = machine.attendance(reading.records)
            try:  # names only help matching; a machine that will not give them still gives its punches
                reading.names = machine.users(reading.users)
            except (MachineError, OSError):
                reading.names = {}
        return reading


def read(host, port=DEFAULT_PORT, password=0, with_punches=True, timeout=6):
    """Clock, counts and (optionally) every punch on the machine. Tries TCP, then UDP; when neither answers the
    error says why in plain words (see `explain`)."""
    errors = {}
    for transport in ("tcp", "udp"):
        try:
            return _read_with(transport, host, port, password, with_punches, timeout)
        except (MachineError, OSError) as error:
            errors[transport] = str(error)
            if "comm key" in str(error):
                raise  # it answered: the key is wrong, UDP will say the same
    raise MachineError(explain(host, port, errors))


def explain(host, port, errors=None):
    """Why the machine could not be reached, in words the office can act on."""
    from apps.core.escpos import local_networks

    errors = errors or {}
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        ip = None
    networks = local_networks()
    here = ", ".join(str(n.network_address).rsplit(".", 1)[0] + ".x" for n in networks) or "?"
    if ip is not None and networks and not any(ip in n for n in networks):
        return (
            f"This computer is on network {here} but the machine ({host}) is on "
            f"{str(ip).rsplit('.', 1)[0]}.x, so they cannot reach each other. Give the machine an IP address on "
            f"this computer's network (on the machine: M/OK → Comm → Ethernet), or connect this computer to the "
            f"machine's network."
        )
    tcp = errors.get("tcp", "")
    if "refused" in tcp.lower():
        return f"{host} is on the network but port {port} is closed. Check the port on the machine (Comm → Ethernet)."
    if "no reply" in tcp:
        return (
            f"{host} accepted the connection on port {port} but did not reply (tried TCP and UDP). Check the comm key "
            f"and the port on the machine (Comm → Comm. Key / Ethernet), then restart the machine once."
        )
    pinged = ping(host)
    if pinged is False:
        return (
            f"{host} does not answer a ping from this computer ({here}): the machine is off, its network cable is "
            f"out, or its IP address is not {host} (check M/OK → Comm → Ethernet on the machine)."
        )
    seen = "answers a ping but " if pinged else ""
    return (
        f"{host} {seen}gives no answer on port {port} (tried TCP and UDP; this computer is on {here}). Check the "
        f"port on the machine (Comm → Ethernet), and that Windows Firewall or antivirus is not blocking TASEMS."
    )


def ping(host):
    """True / False from one ping, or None when ping cannot be run here."""
    import platform
    import subprocess

    windows = platform.system() == "Windows"
    command = ["ping", "-n", "1", "-w", "1500", host] if windows else ["ping", "-c", "1", "-W", "2", host]
    try:
        done = subprocess.run(  # noqa: S603 - fixed program, the host is an IP address typed by staff
            command, capture_output=True, timeout=6, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    except (OSError, subprocess.SubprocessError):
        return None
    out = done.stdout.decode(errors="ignore")
    # Windows says "Reply from x: Destination host unreachable" with exit code 0 when it fails, so look for TTL.
    return done.returncode == 0 and "TTL=" in out.upper()
