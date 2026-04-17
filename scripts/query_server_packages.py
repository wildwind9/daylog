#!/usr/bin/env python
import argparse

import paramiko


def run_command(client: paramiko.SSHClient, command: str, timeout: int = 180) -> str:
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
        for query in [
            "yum list available '*Xvfb*' '*x11vnc*' '*websockify*' '*novnc*' '*fluxbox*' '*openbox*' 2>/dev/null | head -n 120",
            "yum search Xvfb x11vnc websockify novnc fluxbox openbox | head -n 160",
        ]:
            print("==== QUERY ====")
            print(query)
            print(run_command(client, query))
    finally:
        client.close()


if __name__ == "__main__":
    main()
