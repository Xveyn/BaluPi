#!/usr/bin/env python3
"""Download and install the BaluHost frontend for BaluPi.

Three modes of operation:

1. **From repo branch** (preferred on Pi — no Node.js needed):
       python sync_frontend.py --from-branch frontend
   Fetches pre-built assets from a dedicated branch in this repo
   (pushed by BaluHost's GitHub Actions workflow).

2. **From GitHub source** (fallback — requires Node.js):
       python sync_frontend.py
       python sync_frontend.py --branch main
   Downloads client/ source from BaluHost, runs npm build.

3. **From local source** (development):
       python sync_frontend.py --source ../BaluHost/client
   Uses a local BaluHost checkout.

Requirements:
    - Mode 1: git only
    - Mode 2: Node.js >= 18 and npm
    - Mode 3: Node.js >= 18 and npm (unless --skip-build)
"""

from __future__ import annotations

import argparse
import io
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import tempfile
import typing
from pathlib import Path

REPO = "Xveyn/BaluHost"
DEFAULT_BRANCH = "development"
DEFAULT_FRONTEND_BRANCH = "frontend"
CLIENT_DIR = "client"
DEST_DIR = Path(__file__).resolve().parent / "dist"

# ANSI colors (disabled on Windows without ANSI support)
_NO_COLOR = os.environ.get("NO_COLOR") or (os.name == "nt" and not os.environ.get("WT_SESSION"))
GREEN = "" if _NO_COLOR else "\033[32m"
YELLOW = "" if _NO_COLOR else "\033[33m"
RED = "" if _NO_COLOR else "\033[31m"
BOLD = "" if _NO_COLOR else "\033[1m"
RESET = "" if _NO_COLOR else "\033[0m"


def log(msg: str, color: str = GREEN) -> None:
    print(f"{color}{BOLD}[sync-frontend]{RESET} {msg}")


def error(msg: str) -> typing.NoReturn:
    log(msg, RED)
    sys.exit(1)


def check_node() -> None:
    """Verify Node.js and npm are available."""
    for cmd in ("node", "npm"):
        if not shutil.which(cmd):
            error(f"'{cmd}' not found. Install Node.js >= 18 to build the frontend.")
    result = subprocess.run(["node", "--version"], capture_output=True, text=True)
    log(f"Using Node.js {result.stdout.strip()}")


def download_source(branch: str, dest: Path) -> Path:
    """Download repo tarball and extract client/ directory."""
    import urllib.request

    url = f"https://github.com/{REPO}/archive/refs/heads/{branch}.tar.gz"
    log(f"Downloading {REPO}@{branch} ...")

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BaluPi-sync/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = io.BytesIO(resp.read())
    except Exception as exc:
        error(f"Download failed: {exc}")

    log("Extracting client/ source ...")
    with tarfile.open(fileobj=data, mode="r:gz") as tar:
        # Tarball root is "BaluHost-<branch>/"
        root_prefix = tar.getnames()[0].split("/")[0]
        client_prefix = f"{root_prefix}/{CLIENT_DIR}/"

        members = []
        for member in tar.getmembers():
            if member.name.startswith(client_prefix):
                # Strip prefix so files land directly in dest
                member.name = member.name[len(client_prefix):]
                if member.name:  # skip empty root entry
                    members.append(member)

        if not members:
            error(f"No '{CLIENT_DIR}/' directory found in {REPO}@{branch}")

        client_dest = dest / CLIENT_DIR
        client_dest.mkdir(parents=True, exist_ok=True)
        tar.extractall(path=client_dest, members=members)

    return client_dest


def build_frontend(client_dir: Path) -> Path:
    """Run npm ci && npm run build, return path to dist/."""
    log("Installing dependencies (npm ci) ...")
    subprocess.run(
        ["npm", "ci", "--no-audit", "--no-fund"],
        cwd=client_dir,
        check=True,
        shell=(os.name == "nt"),
    )

    # Patch API base URL for BaluPi (same origin, /api prefix)
    env = os.environ.copy()
    env["VITE_API_BASE_URL"] = ""  # empty = same origin

    log("Building frontend (npm run build) ...")
    subprocess.run(
        ["npm", "run", "build"],
        cwd=client_dir,
        check=True,
        env=env,
        shell=(os.name == "nt"),
    )

    dist = client_dir / "dist"
    if not dist.exists():
        error("Build succeeded but dist/ directory not found!")
    return dist


def copy_dist(dist_dir: Path) -> None:
    """Copy built dist/ to backend/static/."""
    if DEST_DIR.exists():
        log(f"Cleaning {DEST_DIR} ...")
        shutil.rmtree(DEST_DIR)

    log(f"Copying to {DEST_DIR.relative_to(Path(__file__).resolve().parent)} ...")
    shutil.copytree(dist_dir, DEST_DIR)

    # Count files for summary
    file_count = sum(1 for _ in DEST_DIR.rglob("*") if _.is_file())
    size_mb = sum(f.stat().st_size for f in DEST_DIR.rglob("*") if f.is_file()) / (1024 * 1024)
    log(f"Done! {file_count} files, {size_mb:.1f} MB ->{DEST_DIR}")


def sync_from_branch(branch: str) -> None:
    """Fetch pre-built frontend from a git branch and copy to backend/static/.

    The BaluHost GitHub Actions workflow pushes pre-built dist-pi/
    to a dedicated branch (e.g. 'frontend') in this repo.
    """
    repo_root = Path(__file__).resolve().parent

    log(f"Fetching branch '{branch}' ...")
    result = subprocess.run(
        ["git", "fetch", "origin", branch],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        error(f"git fetch failed: {result.stderr.strip()}")

    # Check if the branch exists
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"origin/{branch}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        error(f"Branch 'origin/{branch}' not found. Has the BaluHost workflow run yet?")

    commit = result.stdout.strip()[:8]
    log(f"Using origin/{branch} @ {commit}")

    # Extract files from that branch into a temp dir
    with tempfile.TemporaryDirectory(prefix="balupi-frontend-") as tmp:
        tmp_path = Path(tmp)
        result = subprocess.run(
            ["git", "archive", f"origin/{branch}"],
            cwd=repo_root,
            capture_output=True,
        )
        if result.returncode != 0:
            error("git archive failed")

        # Extract tar
        with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as tar:
            tar.extractall(path=tmp_path)

        # Verify index.html exists
        if not (tmp_path / "index.html").exists():
            error(f"No index.html found on branch '{branch}'. Check BaluHost workflow config.")

        copy_dist(tmp_path)

    log(f"Frontend synced from origin/{branch} @ {commit}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync BaluHost frontend for BaluPi")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--from-branch",
        metavar="BRANCH",
        nargs="?",
        const=DEFAULT_FRONTEND_BRANCH,
        default=None,
        help=f"Pull pre-built frontend from git branch (default: {DEFAULT_FRONTEND_BRANCH}). "
             "No Node.js required — preferred on Pi.",
    )
    mode.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Use local client/ source instead of downloading",
    )
    parser.add_argument(
        "--branch", "-b",
        default=DEFAULT_BRANCH,
        help=f"Git branch to download source from (default: {DEFAULT_BRANCH})",
    )
    parser.add_argument(
        "--skip-build",
        action="store_true",
        help="Skip npm build (use if dist/ is pre-built locally)",
    )
    args = parser.parse_args()

    print(f"\n{BOLD}=== BaluPi Frontend Sync ==={RESET}\n")

    if args.from_branch:
        # Mode 1: Pull pre-built from git branch (no Node.js needed)
        sync_from_branch(args.from_branch)

    elif args.source:
        # Mode 3: Use local source directory
        client_dir = args.source.resolve()
        if not (client_dir / "package.json").exists():
            error(f"No package.json found in {client_dir}")
        log(f"Using local source: {client_dir}")

        if args.skip_build:
            dist = client_dir / "dist"
            if not dist.exists():
                error(f"No dist/ in {client_dir} — run build first or remove --skip-build")
        else:
            check_node()
            dist = build_frontend(client_dir)

        copy_dist(dist)
    else:
        # Mode 2: Download from GitHub and build
        check_node()

        with tempfile.TemporaryDirectory(prefix="balupi-frontend-") as tmp:
            client_dir = download_source(args.branch, Path(tmp))

            if args.skip_build:
                error("--skip-build requires --source (dist/ is not in the repo)")

            dist = build_frontend(client_dir)
            copy_dist(dist)

    print(f"\n{GREEN}{BOLD}Frontend ready!{RESET} FastAPI will serve it from /\n")


if __name__ == "__main__":
    main()
