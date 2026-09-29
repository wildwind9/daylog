#!/usr/bin/env python
import argparse
import json

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
set -a; . /opt/daylog/backend/daylog-backend.env; set +a
/opt/daylog/python/venv/bin/python - <<'PY'
import os
import json
import pymysql
import urllib.parse
import urllib.request

conn = pymysql.connect(host=os.environ.get('DB_HOST', '127.0.0.1'), user=os.environ['DB_USERNAME'], password=os.environ['DB_PASSWORD'], database=os.environ.get('DB_NAME', 'daylog'), charset='utf8mb4')
try:
    with conn.cursor() as cur:
        cur.execute("SELECT access_token, weibo_uid, screen_name FROM weibo_binding WHERE user_id=1 AND active=1 ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if not row:
            raise RuntimeError('No active admin weibo binding found')
        access_token, uid, screen_name = row

    url = "https://api.weibo.com/2/statuses/user_timeline.json"
    params = {
        "access_token": access_token,
        "uid": uid,
        "count": 100,
        "page": 1,
    }
    full_url = f"{url}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(full_url, timeout=30) as response:
        payload = json.loads(response.read().decode('utf-8'))
    preview = {
        "http_status": 200,
        "uid": uid,
        "screen_name": screen_name,
        "statuses_count": len(payload.get("statuses") or []),
        "total_number": payload.get("total_number"),
        "first_status_ids": [str(item.get("id")) for item in (payload.get("statuses") or [])[:5]],
        "error": payload.get("error"),
        "error_code": payload.get("error_code"),
    }
    print(json.dumps(preview, ensure_ascii=False))
finally:
    conn.close()
PY
"""
        print(run_command(client, script, timeout=180))
    finally:
        client.close()


if __name__ == "__main__":
    main()
