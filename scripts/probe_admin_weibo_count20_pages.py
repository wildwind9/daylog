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
/opt/daylog/python/venv/bin/python - <<'PY'
import json
import urllib.parse
import urllib.request
import pymysql

conn = pymysql.connect(host='127.0.0.1', user='root', password='CHWyZYH@IgK2#7eTc8xr46MdCYFU', database='daylog', charset='utf8mb4')
try:
    with conn.cursor() as cur:
        cur.execute("SELECT access_token, weibo_uid, screen_name FROM weibo_binding WHERE user_id=1 AND active=1 ORDER BY id DESC LIMIT 1")
        access_token, uid, screen_name = cur.fetchone()

    url = "https://api.weibo.com/2/statuses/user_timeline.json"
    results = []
    for page in (1, 2, 3):
        params = {
            "access_token": access_token,
            "uid": uid,
            "count": 20,
            "page": page,
        }
        full_url = f"{url}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(full_url, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        statuses = payload.get("statuses") or []
        results.append({
            "page": page,
            "count_param": 20,
            "returned_count": len(statuses),
            "ids": [str(item.get("id")) for item in statuses[:10]],
            "total_number": payload.get("total_number"),
            "error": payload.get("error"),
            "error_code": payload.get("error_code"),
        })

    print(json.dumps({
        "uid": uid,
        "screen_name": screen_name,
        "pages": results,
    }, ensure_ascii=False))
finally:
    conn.close()
PY
"""
        print(run_command(client, script, timeout=180))
    finally:
        client.close()


if __name__ == "__main__":
    main()
