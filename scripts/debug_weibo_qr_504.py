#!/usr/bin/env python
import argparse

import paramiko


def run_command(client: paramiko.SSHClient, command: str, timeout: int = 120) -> str:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return f"[exit={exit_status}]\nSTDOUT:\n{out}\nSTDERR:\n{err}"


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
        commands = [
            "systemctl is-active daylog-backend",
            "systemctl is-active daylog-python",
            "journalctl -u daylog-backend -n 120 --no-pager",
            "journalctl -u daylog-python -n 120 --no-pager",
            "curl -sS -i http://127.0.0.1:8000/health",
            "curl -sS -i -X POST 'http://127.0.0.1:8000/weibo/login/qr?userId=1'",
        ]
        for command in commands:
            print(f"\n===== {command} =====")
            print(run_command(client, command, timeout=180))
    finally:
        client.close()


if __name__ == "__main__":
    main()
