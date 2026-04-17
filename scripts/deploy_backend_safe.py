#!/usr/bin/env python
import argparse
import sys
import time

import paramiko


def run_command(client: paramiko.SSHClient, command: str, timeout: int = 120) -> str:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    output = stdout.read().decode("utf-8", errors="replace")
    error = stderr.read().decode("utf-8", errors="replace")
    code = stdout.channel.recv_exit_status()
    if code != 0:
        raise RuntimeError(f"remote command failed ({code}): {error or output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely deploy the Spring Boot backend jar without overwriting a running fat jar."
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--local-jar", required=True)
    parser.add_argument(
        "--remote-jar",
        default="/opt/daylog/backend/daylog-backend.jar",
        help="Remote jar path on the server.",
    )
    parser.add_argument(
        "--service",
        default="daylog-backend",
        help="Systemd service name.",
    )
    parser.add_argument(
        "--health-url",
        default="http://127.0.0.1:8080/api-docs",
        help="Health check URL to verify after restart.",
    )
    args = parser.parse_args()

    remote_temp = f"{args.remote_jar}.next"
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(args.host, username=args.user, password=args.password, timeout=20)

        sftp = client.open_sftp()
        sftp.put(args.local_jar, remote_temp)
        sftp.close()

        run_command(client, f"systemctl stop {args.service}", timeout=180)
        run_command(client, f"mv {remote_temp} {args.remote_jar}")
        run_command(client, f"systemctl start {args.service}", timeout=180)

        time.sleep(8)

        status = run_command(
            client,
            f"systemctl is-active {args.service} && curl -fsS '{args.health_url}' > /dev/null && echo ok",
            timeout=180,
        ).strip()
        print(status)
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
