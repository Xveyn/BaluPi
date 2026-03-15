"""Kill running BaluPi development server processes.

Usage:
    Windows: python kill_dev.py
    Linux:   python3 kill_dev.py

Finds and terminates all Python/uvicorn processes related to BaluPi.
Counterpart to start_dev.py.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time

# ANSI colors
if os.name == "nt":
    os.system("")  # enable VT100 on Windows 10+

CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
RESET = "\033[0m"


def log(level: str, msg: str) -> None:
    colors = {"info": CYAN, "kill": YELLOW, "ok": GREEN, "error": RED}
    color = colors.get(level, "")
    print(f"{color}[{level}]{RESET} {msg}")


def find_and_kill_windows() -> int:
    """Find BaluPi-related Python processes on Windows via WMIC."""
    # Find python processes whose command line contains 'app.main:app'
    try:
        result = subprocess.run(
            [
                "wmic",
                "process",
                "where",
                "Name='python.exe' or Name='python3.exe'",
                "get",
                "ProcessId,CommandLine",
                "/format:list",
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        # Fallback: use tasklist + PowerShell
        return _find_and_kill_windows_ps()

    pids: list[int] = []
    current_cmdline = ""
    current_pid = ""

    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith("CommandLine="):
            current_cmdline = line[len("CommandLine=") :]
        elif line.startswith("ProcessId="):
            current_pid = line[len("ProcessId=") :]
            if current_cmdline and current_pid:
                if "app.main:app" in current_cmdline:
                    try:
                        pids.append(int(current_pid))
                    except ValueError:
                        pass
            current_cmdline = ""
            current_pid = ""

    return _kill_pids(pids)


def _find_and_kill_windows_ps() -> int:
    """Fallback: use PowerShell to find processes."""
    try:
        result = subprocess.run(
            [
                "powershell",
                "-Command",
                (
                    "Get-CimInstance Win32_Process "
                    "| Where-Object { $_.CommandLine -like '*app.main:app*' } "
                    "| Select-Object -ExpandProperty ProcessId"
                ),
            ],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        log("error", "Cannot find wmic or powershell")
        return 1

    pids: list[int] = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))

    return _kill_pids(pids)


def find_and_kill_unix() -> int:
    """Find BaluPi-related Python processes on Linux/macOS."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "app.main:app"],
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        # pgrep not available, try ps
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
        )
        pids: list[int] = []
        for line in result.stdout.splitlines():
            if "app.main:app" in line and "kill_dev" not in line:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        pids.append(int(parts[1]))
                    except ValueError:
                        pass
        return _kill_pids(pids)

    pids = []
    for line in result.stdout.strip().splitlines():
        line = line.strip()
        if line.isdigit():
            pids.append(int(line))

    # Filter out our own PID
    own_pid = os.getpid()
    pids = [p for p in pids if p != own_pid]

    return _kill_pids(pids)


def _kill_pids(pids: list[int]) -> int:
    """Terminate a list of PIDs gracefully, then force-kill if needed."""
    if not pids:
        log("info", "No BaluPi dev server processes found.")
        return 0

    log("info", f"Found {len(pids)} process(es): {pids}")
    killed = 0

    for pid in pids:
        try:
            if os.name == "nt":
                # Windows: taskkill with tree flag to get child processes too
                subprocess.run(
                    ["taskkill", "/F", "/T", "/PID", str(pid)],
                    capture_output=True,
                )
            else:
                os.kill(pid, signal.SIGTERM)
            log("kill", f"Terminated PID {pid}")
            killed += 1
        except ProcessLookupError:
            log("info", f"PID {pid} already gone")
        except PermissionError:
            log("error", f"Permission denied for PID {pid} — try running as admin/sudo")
        except Exception as e:
            log("error", f"Failed to kill PID {pid}: {e}")

    # On Unix, wait a moment then force-kill any survivors
    if os.name != "nt" and killed > 0:
        time.sleep(1)
        for pid in pids:
            try:
                os.kill(pid, 0)  # check if still alive
                log("kill", f"Force-killing PID {pid}")
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass  # already dead
            except Exception:
                pass

    if killed > 0:
        log("ok", f"Killed {killed} BaluPi process(es).")
    return 0


def main() -> int:
    log("info", "Looking for BaluPi dev server processes...")
    if os.name == "nt":
        return find_and_kill_windows()
    else:
        return find_and_kill_unix()


if __name__ == "__main__":
    raise SystemExit(main())
