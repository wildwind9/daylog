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
    parser.add_argument("--username", default="admin")
    parser.add_argument("--login-password", default="changeme")
    args = parser.parse_args()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=args.password, timeout=30)
    try:
        login_command = (
            "curl -sS -X POST http://127.0.0.1:8080/api/auth/login "
            "-H 'Content-Type: application/json' "
            f"-d '{json.dumps({'username': args.username, 'password': args.login_password})}'"
        )
        login_payload = json.loads(run_command(client, login_command, timeout=60))
        token = login_payload["data"]["token"]

        status_command = (
            "curl -sS http://127.0.0.1:8080/api/weibo/sync/status "
            f"-H 'Authorization: Bearer {token}'"
        )
        qr_command = (
            "curl -sS -X POST http://127.0.0.1:8080/api/weibo/login/qr "
            f"-H 'Authorization: Bearer {token}'"
        )

        print("===== STATUS =====")
        print(run_command(client, status_command, timeout=60))
        print("\n===== QR START =====")
        print(run_command(client, qr_command, timeout=120))
    finally:
        client.close()


if __name__ == "__main__":
    main()
