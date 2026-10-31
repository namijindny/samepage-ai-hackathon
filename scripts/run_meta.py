from __future__ import annotations

import getpass
import os
import subprocess
import sys


def main():
    key = os.environ.get("MODEL_API_KEY") or getpass.getpass("Meta Model API key (hidden): ").strip()
    if not key:
        raise SystemExit("No API key supplied. No API calls were made.")
    env = os.environ.copy()
    env["MODEL_API_KEY"] = key
    env["ANALYSIS_MODE"] = "meta"
    env.setdefault("MAX_META_CALLS_PER_DAY", "10")
    print("SamePage is starting in Meta mode. Daily API attempt limit:", env["MAX_META_CALLS_PER_DAY"])
    print("Billing is managed by Meta; this request allowance is not a monetary spending cap.")
    try:
        return subprocess.call([sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000"], env=env)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
