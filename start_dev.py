"""Convenience launcher for BaluPi development server.

Usage:
    Windows: python start_dev.py
    Linux:   python3 start_dev.py

Press Ctrl+C to stop. The script detects a backend virtual environment
and uses it to run Uvicorn with --reload. Run from the repository root.

Platform Support:
    - Windows: Full support with proper process group handling
    - Linux/Debian (Raspberry Pi): Full support with python3, setsid
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Tuple

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"

BACKEND_VENV = BACKEND_DIR / (
    ".venv\\Scripts\\python.exe" if os.name == "nt" else ".venv/bin/python"
)

ProcessInfo = Tuple[str, subprocess.Popen]

# ANSI colors (disabled on Windows without VT support)
if os.name == "nt":
    os.system("")  # enable VT100 on Windows 10+

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def log(level: str, msg: str) -> None:
    colors = {"info": CYAN, "start": GREEN, "stop": YELLOW, "error": RED}
    color = colors.get(level, "")
    print(f"{color}[{level}]{RESET} {msg}")


def resolve_backend_python() -> str:
    """Find the best Python interpreter for the backend."""
    # 1. Check venv
    if BACKEND_VENV.exists():
        return str(BACKEND_VENV)

    # 2. Linux: also try python3 in venv
    if os.name != "nt":
        python3_path = BACKEND_DIR / ".venv" / "bin" / "python3"
        if python3_path.exists():
            return str(python3_path)

    # 3. Fallback: system Python
    log("info", "No venv found — using system Python")
    return sys.executable


def check_dependencies(python: str) -> bool:
    """Verify critical packages are importable."""
    result = subprocess.run(
        [python, "-c", "import fastapi; import uvicorn; import kasa"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log("error", "Missing dependencies. Run:")
        log("error", f"  cd {BACKEND_DIR} && pip install -e '.[dev]'")
        return False
    return True


def start_process(name: str, cmd: List[str], cwd: Path) -> subprocess.Popen:
    log("start", f"{name}: {' '.join(cmd)}")
    if os.name == "nt":
        return subprocess.Popen(
            cmd, cwd=cwd, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
    else:
        return subprocess.Popen(cmd, cwd=cwd, start_new_session=True)


def terminate_processes(processes: List[ProcessInfo]) -> None:
    for name, proc in processes:
        if proc.poll() is not None:
            continue
        log("stop", name)
        try:
            if os.name == "nt":
                proc.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                if hasattr(os, "killpg"):
                    try:
                        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                else:
                    proc.terminate()
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if os.name != "nt" and hasattr(os, "killpg"):
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass
            else:
                proc.kill()
        except Exception as e:
            log("error", f"Failed to terminate {name}: {e}")
            proc.kill()


def main() -> int:
    processes: List[ProcessInfo] = []
    backend_python = resolve_backend_python()

    log("info", f"Python: {backend_python}")
    log("info", f"Backend: {BACKEND_DIR}")

    if not check_dependencies(backend_python):
        return 1

    try:
        # Set dev environment defaults
        os.environ.setdefault("BALUPI_DEBUG", "true")
        os.environ.setdefault("BALUPI_LOG_LEVEL", "INFO")
        os.environ.setdefault("BALUPI_ENVIRONMENT", "development")

        # Backend: uvicorn with auto-reload
        backend_cmd = [
            backend_python,
            "-m",
            "uvicorn",
            "app.main:app",
            "--reload",
            "--host",
            "0.0.0.0",
            "--port",
            "8000",
        ]

        proc = start_process("backend", backend_cmd, BACKEND_DIR)
        processes.append(("backend", proc))

        log("info", "")
        log("info", f"  API:     http://localhost:8000/api")
        log("info", f"  Health:  http://localhost:8000/api/health")
        log("info", f"  Docs:    http://localhost:8000/docs")
        log("info", "")
        log("info", "Press Ctrl+C to stop")

        # Monitor process
        while True:
            for name, proc in processes:
                retcode = proc.poll()
                if retcode is not None:
                    log("info", f"{name} exited with code {retcode}")
                    return retcode or 0
            time.sleep(0.5)

    except FileNotFoundError as exc:
        log("error", str(exc))
        return 1
    except KeyboardInterrupt:
        print()
        log("info", "Ctrl+C received, shutting down...")
        return 0
    finally:
        terminate_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
