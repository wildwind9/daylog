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
import urllib.error
import pymysql

hosts = [
    "https://api.weibo.com/2/statuses/user_timeline/biz.json",
    "https://c.api.weibo.com/2/statuses/user_timeline/biz.json",
    "https://api.weibo.cn/2/statuses/user_timeline/biz.json",
]

conn = pymysql.connect(host='127.0.0.1', user='root', password='CHWyZYH@IgK2#7eTc8xr46MdCYFU', database='daylog', charset='utf8mb4')
try:
    with conn.cursor() as cur:
        cur.execute("SELECT access_token FROM weibo_binding WHERE user_id=1 AND active=1 ORDER BY id DESC LIMIT 1")
        access_token = cur.fetchone()[0]

    results = []
    for url in hosts:
        params = {
            "access_token": access_token,
            "count": 20,
            "page": 1,
        }
        full_url = f"{url}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(full_url, timeout=20) as response:
                body = response.read().decode("utf-8", errors="replace")
            payload = json.loads(body)
            results.append({
                "url": url,
                "http_status": 200,
                "returned_count": len(payload.get("statuses") or []),
                "error": payload.get("error"),
                "error_code": payload.get("error_code"),
            })
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            results.append({
                "url": url,
                "http_status": exc.code,
                "body": body[:300],
            })
        except Exception as exc:
            results.append({
                "url": url,
                "http_status": None,
                "body": str(exc),
            })

    print(json.dumps(results, ensure_ascii=False))
finally:
    conn.close()
PY
"""
        print(run_command(client, script, timeout=180))
    finally:
        client.close()


if __name__ == "__main__":
    main()
