"""TASEMS on one Windows computer (offline test copy, docs/WINDOWS_INSTALL.md).

Installed layout (TASEMS-Setup.exe):  <program>/python  <program>/pgsql  <program>/gtk  <program>/app
Data (kept when the program is updated or removed):  %LOCALAPPDATA%\\TASEMS-data

    python launcher.py            start TASEMS (database + web server) and open it in the browser
    python launcher.py --master   make a master login (every permission)
    python launcher.py --backup   save all data to Documents\\TASEMS backups
    python launcher.py --stop     stop the database (close the TASEMS window to stop the web server)
"""

import base64
import datetime as dt
import os
import secrets
import socket
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

WINDOWS = os.name == "nt"
APP = Path(__file__).resolve().parents[1]
PROGRAM = APP.parent
PG_BIN = Path(os.environ.get("TASEMS_PG_BIN") or PROGRAM / "pgsql" / "bin")
GTK_BIN = PROGRAM / "gtk" / "bin"
DATA = Path(os.environ.get("TASEMS_DATA") or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "TASEMS-data")
PGDATA = DATA / "pgdata"
LOGS = DATA / "logs"
CONFIG = DATA / "config.env"
DB_PORT = int(os.environ.get("TASEMS_DB_PORT", "55432"))
WEB_PORT = int(os.environ.get("TASEMS_PORT", "8000"))
DEMO_PASSWORD = "ArqamOffline2026"


def say(text):
    print(text, flush=True)


def exe(name):
    return str(PG_BIN / (f"{name}.exe" if WINDOWS else name))


def run(args, **kw):
    kw.setdefault("check", True)
    kw.setdefault("capture_output", True)
    kw.setdefault("text", True)
    if WINDOWS:
        kw.setdefault("creationflags", 0x08000000)  # no extra black windows
    return subprocess.run(args, **kw)


def read_config():
    values = {}
    if CONFIG.exists():
        for line in CONFIG.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                key, value = line.split("=", 1)
                values[key.strip()] = value.strip()
    return values


def first_run_config():
    """Keys and passwords are made once on this computer; the demo/empty choice is asked once."""
    DATA.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(exist_ok=True)
    values = read_config()
    if values:
        return values
    say("")
    say("  The Arqam Schools — TASEMS (offline test copy)")
    say("  First start. Choose how to start:")
    say("    1 = with fictional DEMO data and demo logins (recommended for testing)")
    say("    2 = EMPTY school, two-step sign-in on, like the real server")
    choice = os.environ.get("TASEMS_MODE") or input("  Type 1 or 2 and press Enter: ").strip()
    values = {
        "DEMO_MODE": "False" if choice == "2" else "True",
        "SECRET_KEY": secrets.token_urlsafe(50),
        "FIELD_ENCRYPTION_KEY": base64.urlsafe_b64encode(os.urandom(32)).decode(),
        "PG_SUPER_PASSWORD": secrets.token_urlsafe(24),
        "APP_DB_PASSWORD": secrets.token_urlsafe(24),
    }
    CONFIG.write_text(
        "# Made on this computer the first time TASEMS started. Keep it private; do not share it.\n"
        + "".join(f"{k}={v}\n" for k, v in values.items()),
        encoding="utf-8",
    )
    return values


def pg_env(values):
    env = dict(os.environ, PGPASSWORD=values["PG_SUPER_PASSWORD"], PGPORT=str(DB_PORT), PGHOST="127.0.0.1")
    return env


def database_up(values):
    """Starts PostgreSQL on this computer only (127.0.0.1); creates it the first time."""
    fresh = not (PGDATA / "PG_VERSION").exists()
    if fresh:
        say("  Preparing the database (first time only)...")
        pwfile = DATA / "pw.tmp"
        pwfile.write_text(values["PG_SUPER_PASSWORD"], encoding="utf-8")
        try:
            run([exe("initdb"), "-D", str(PGDATA), "-U", "postgres", "--pwfile", str(pwfile), "-E", "UTF8",
                 "--locale=C", "--auth=scram-sha-256"])  # fmt: skip
        finally:
            pwfile.unlink(missing_ok=True)
    status = run([exe("pg_ctl"), "status", "-D", str(PGDATA)], check=False)
    if status.returncode != 0:
        # Not captured: the database keeps running after pg_ctl ends and would hold a captured pipe open.
        with open(LOGS / "pg_ctl.log", "a", encoding="utf-8") as log:
            run([exe("pg_ctl"), "start", "-w", "-t", "60", "-D", str(PGDATA), "-l", str(LOGS / "postgres.log"),
                 "-o", f"-p {DB_PORT} -c listen_addresses=127.0.0.1"],
                capture_output=False, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)  # fmt: skip
    if fresh:
        # The app uses an ordinary role, so row-level security protects branch data as on the real server.
        sql = (
            f"CREATE ROLE tasems_app LOGIN PASSWORD '{values['APP_DB_PASSWORD']}' "
            "NOSUPERUSER NOBYPASSRLS NOCREATEROLE NOCREATEDB;"
        )
        run([exe("psql"), "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-c", sql], env=pg_env(values))
        run([exe("psql"), "-U", "postgres", "-d", "postgres", "-c", "CREATE DATABASE tasems OWNER tasems_app;"],
            env=pg_env(values))  # fmt: skip


def database_down():
    if (PGDATA / "PG_VERSION").exists():
        run([exe("pg_ctl"), "stop", "-D", str(PGDATA), "-m", "fast"], check=False)


def django_setup(values):
    os.environ.update(
        DATABASE_URL=f"postgres://tasems_app:{values['APP_DB_PASSWORD']}@127.0.0.1:{DB_PORT}/tasems",
        SECRET_KEY=values["SECRET_KEY"],
        FIELD_ENCRYPTION_KEY=values["FIELD_ENCRYPTION_KEY"],
        DEMO_MODE=values["DEMO_MODE"],
        DEMO_PASSWORD=DEMO_PASSWORD,
        DEBUG="False",
        LOCAL_NETWORK="True",
        MEDIA_ROOT=str(DATA / "media"),
        DJANGO_SETTINGS_MODULE="config.settings",
    )
    if GTK_BIN.exists():  # PDFs (WeasyPrint) use the GTK libraries shipped with TASEMS
        os.environ["WEASYPRINT_DLL_DIRECTORIES"] = str(GTK_BIN)
        os.environ["PATH"] = str(GTK_BIN) + os.pathsep + os.environ.get("PATH", "")
        if WINDOWS:
            os.add_dll_directory(str(GTK_BIN))
    (DATA / "media").mkdir(exist_ok=True)
    sys.path.insert(0, str(APP))
    os.chdir(APP)
    import django

    django.setup()


def port_busy(port):
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def lan_addresses():
    try:
        names = socket.gethostbyname_ex(socket.gethostname())[2]
    except OSError:
        names = []
    return [a for a in names if not a.startswith("127.")]


def start():
    if port_busy(WEB_PORT):
        say("  TASEMS is already running. Opening it...")
        webbrowser.open(f"http://localhost:{WEB_PORT}")
        return
    values = first_run_config()
    database_up(values)
    say("  Starting TASEMS... (the first start takes a few minutes)")
    django_setup(values)
    from django.core.management import call_command

    call_command("migrate", interactive=False, verbosity=0)
    call_command("seed_tasems", verbosity=0)
    if values["DEMO_MODE"] == "True":
        try:
            call_command("seed_demo", verbosity=0)
        except Exception as error:  # the site starts even if demo data cannot be added
            say(f"  Demo data not loaded: {error}")
    # Large PDFs are made in the background, as on the server.
    threading.Thread(target=lambda: call_command("run_jobs"), daemon=True).start()

    if WINDOWS:  # closing this window also stops the database
        import ctypes

        @ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)
        def on_close(_event):
            database_down()
            return False

        ctypes.windll.kernel32.SetConsoleCtrlHandler(on_close, True)
        start.on_close = on_close  # keep a reference

    from waitress import serve

    from config.wsgi import application

    say("")
    say(f"  TASEMS is running:  http://localhost:{WEB_PORT}")
    for address in lan_addresses():
        say(f"  Other computers on this network:  http://{address}:{WEB_PORT}")
    if values["DEMO_MODE"] == "True":
        say(f"  Demo logins: demo-network, demo-director, demo-principal ... password {DEMO_PASSWORD}")
    say("  Keep this window open. Close it to stop TASEMS.")
    threading.Timer(2, lambda: webbrowser.open(f"http://localhost:{WEB_PORT}")).start()
    try:
        serve(application, host="0.0.0.0", port=WEB_PORT, threads=8, _quiet=True)
    finally:
        database_down()


def master():
    values = first_run_config()
    database_up(values)
    django_setup(values)
    from django.core.management import call_command

    call_command("migrate", interactive=False, verbosity=0)
    call_command("seed_tasems", verbosity=0)
    say("  Make a master login (it can do everything in every branch).")
    call_command("createsuperuser")


def backup():
    values = first_run_config()
    database_up(values)
    folder = Path.home() / "Documents" / "TASEMS backups"
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"tasems-{dt.datetime.now():%Y-%m-%d_%H%M}.dump"
    run([exe("pg_dump"), "-U", "postgres", "-d", "tasems", "-Fc", "-f", str(target)], env=pg_env(values))
    say(f"  Saved: {target}")


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    LOGS.mkdir(parents=True, exist_ok=True)
    try:
        if action == "--master":
            master()
        elif action == "--backup":
            backup()
        elif action in ("--stop", "--stop-quiet"):
            database_down()
            say("  The TASEMS database is stopped.")
            if action == "--stop-quiet":  # used by the uninstaller
                return
        else:
            start()
    except Exception as error:
        say("")
        say(f"  TASEMS could not start: {error}")
        if getattr(error, "stderr", None):
            say(f"  {error.stderr.strip()[:800]}")
        say(f"  Details are in {LOGS}")
        with open(LOGS / "launcher-error.log", "a", encoding="utf-8") as log:
            import traceback

            log.write(f"\n--- {dt.datetime.now()}\n{traceback.format_exc()}")
    if action or WINDOWS:
        try:
            input("  Press Enter to close this window.")
        except EOFError:
            pass


if __name__ == "__main__":
    main()
