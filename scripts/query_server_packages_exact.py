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

    packages = [
        "xorg-x11-server-Xvfb",
        "x11vnc",
        "tigervnc-server",
        "tigervnc",
        "python3-websockify",
        "websockify",
        "novnc",
        "openbox",
        "fluxbox",
    ]

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=args.password, timeout=30)
    try:
        for package in packages:
            print(f"==== {package} ====")
            print(run_command(client, f"yum info {package} 2>/dev/null | head -n 80"))
    finally:
        client.close()


if __name__ == "__main__":
    main()
