#!/usr/bin/env python
import argparse

import paramiko


def run_command(client: paramiko.SSHClient, command: str, timeout: int = 120) -> str:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    if exit_status != 0:
      return f"[exit={exit_status}]\nSTDOUT:\n{out}\nSTDERR:\n{err}"
    return out + err


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
        command = (
            "cat /etc/os-release; "
            "printf '\\n====PKGS====\\n'; "
            "(command -v apt-get || command -v yum || command -v dnf || true); "
            "printf '\\n====TOOLS====\\n'; "
            "for tool in Xvfb x11vnc websockify novnc_proxy openbox fluxbox; do "
            "printf '%s: ' \"$tool\"; command -v \"$tool\" || true; "
            "done"
        )
        print(run_command(client, command, timeout=120))
    finally:
        client.close()


if __name__ == "__main__":
    main()
