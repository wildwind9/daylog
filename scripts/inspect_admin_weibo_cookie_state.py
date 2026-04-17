#!/usr/bin/env python
import argparse

import paramiko


def run_command(client: paramiko.SSHClient, command: str, timeout: int = 120) -> str:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if exit_status != 0:
        raise RuntimeError(f"command failed: {command}\nstdout:\n{out}\nstderr:\n{err}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    args = parser.parse_args()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=args.password, timeout=30)
    try:
        script = r"""
cd /opt/daylog/python/app && /opt/daylog/python/venv/bin/python - <<'PY'
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

env_path = Path("/opt/daylog/python/app/.env")
load_dotenv(env_path, override=True)

from scrapers.weibo import _get_weibo_cookie, _resolve_uid_from_login_state, get_weibo_login_status

cookie = _get_weibo_cookie(1)
print("cookie_length=", len(cookie or ""))
print("status=", get_weibo_login_status(1))
print("resolved_uid=", asyncio.run(_resolve_uid_from_login_state(1)))
PY
"""
        print(run_command(client, script, timeout=180))
    finally:
        client.close()


if __name__ == "__main__":
    main()
