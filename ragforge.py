"""Install and run Ragforge from one terminal using only Python's standard library."""

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import venv

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def node_executable():
    node = shutil.which("node")
    npm = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not node or not npm:
        raise RuntimeError("Install Node.js 22+ (including npm), then retry.")
    version = subprocess.check_output([node, "--version"], text=True).strip()
    if int(version.lstrip("v").split(".")[0]) < 22:
        raise RuntimeError("Node.js 22+ is required.")
    return node, npm


def install():
    _, npm = node_executable()
    if not PYTHON.exists():
        print("Creating .venv ...", flush=True)
        venv.EnvBuilder(with_pip=True).create(ROOT / ".venv")
    subprocess.run(
        [str(PYTHON), "-m", "pip", "install", "-e", str(ROOT / "backend") + "[rag,providers]"],
        cwd=ROOT, check=True,
    )
    subprocess.run([npm, "install"], cwd=ROOT / "frontend", check=True)
    print("Setup complete. Run: python ragforge.py start", flush=True)


def stop(process):
    if os.name == "nt":
        # Include descendants even when their direct parent has already exited.
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
        )
    else:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        else:
            process.kill()
        process.wait()


def start():
    node, _ = node_executable()
    vite = ROOT / "frontend/node_modules/vite/bin/vite.js"
    if not PYTHON.exists() or not vite.exists():
        raise RuntimeError("Dependencies are missing. Run: python ragforge.py install")
    # Use the backend's own settings parser so .env and environment precedence match.
    config = subprocess.check_output(
        [str(PYTHON), "-c", "from app.config import Settings; import json; "
         "s=Settings(); print(json.dumps([s.port, s.dev_origin]))"],
        cwd=ROOT / "backend", text=True,
    )
    port, origin = json.loads(config)
    from urllib.parse import urlsplit

    frontend_port = urlsplit(origin).port
    if port == frontend_port:
        raise RuntimeError("Backend and frontend must use different ports.")
    for value in (port, frontend_port):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", value))
            except OSError as exc:
                raise RuntimeError(f"Port {value} is unavailable. Stop the existing server or change .env.") from exc
    env = dict(os.environ, RAG_API_PROXY=f"http://127.0.0.1:{port}")
    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    processes = []
    previous = signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        processes.append(subprocess.Popen([str(PYTHON), "-m", "app"], cwd=ROOT / "backend", **options))
        processes.append(subprocess.Popen(
            [node, str(vite), "--host", "127.0.0.1", "--port", str(frontend_port), "--strictPort"],
            cwd=ROOT / "frontend", env=env, **options,
        ))
        print(f"Frontend: {origin}\nBackend: http://127.0.0.1:{port}\nPress Ctrl+C to stop both servers.", flush=True)
        while True:
            for name, process in zip(("Backend", "Frontend"), processes):
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited (code {process.returncode}); stopping both servers.")
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nStopping both servers ...", flush=True)
    finally:
        for process in reversed(processes):
            stop(process)
        signal.signal(signal.SIGTERM, previous)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("install", "start"))
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.exit(1, "Python 3.11+ is required.\n")
    try:
        {"install": install, "start": start}[args.command]()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
