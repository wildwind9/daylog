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
    return out + err


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
        token = json.loads(run_command(client, login_command, timeout=60))["data"]["token"]

        commands = {
            "status": (
                "curl -sS http://127.0.0.1:8080/api/weibo/sync/status "
                f"-H 'Authorization: Bearer {token}'"
            ),
            "handoff_start": (
                "curl -sS -X POST http://127.0.0.1:8080/api/weibo/web-login/handoff/start "
                f"-H 'Authorization: Bearer {token}'"
            ),
        }

        for name, command in commands.items():
            print(f"\n===== {name.upper()} =====")
            print(run_command(client, command, timeout=60))
    finally:
        client.close()


if __name__ == "__main__":
    main()
