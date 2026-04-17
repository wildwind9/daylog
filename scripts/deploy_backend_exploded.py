#!/usr/bin/env python
import argparse
import os
import posixpath

import paramiko


def sftp_mkdir_p(sftp: paramiko.SFTPClient, remote_path: str) -> None:
    parts = remote_path.strip("/").split("/")
    current = ""
    for part in parts:
        current = f"{current}/{part}" if current else f"/{part}"
        try:
            sftp.stat(current)
        except FileNotFoundError:
            sftp.mkdir(current)


def upload_tree(sftp: paramiko.SFTPClient, local_root: str, remote_root: str) -> None:
    sftp_mkdir_p(sftp, remote_root)
    for entry in os.scandir(local_root):
        local_path = entry.path
        remote_path = posixpath.join(remote_root, entry.name)
        if entry.is_dir():
            upload_tree(sftp, local_path, remote_path)
        else:
            sftp.put(local_path, remote_path)


def upload_files(sftp: paramiko.SFTPClient, local_root: str, remote_root: str, suffix: str = ".jar") -> None:
    sftp_mkdir_p(sftp, remote_root)
    for entry in os.scandir(local_root):
        if entry.is_file() and entry.name.endswith(suffix):
            sftp.put(entry.path, posixpath.join(remote_root, entry.name))


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
    parser.add_argument("--backend-classes", required=True)
    parser.add_argument("--backend-lib", required=True)
    parser.add_argument("--backend-remote", default="/opt/daylog/backend")
    parser.add_argument("--service", default="daylog-backend")
    parser.add_argument("--health-url", default="http://127.0.0.1:8080/api-docs")
    args = parser.parse_args()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=args.password, timeout=30)

    try:
        sftp = client.open_sftp()
        try:
            run_command(client, f"mkdir -p {args.backend_remote}/classes {args.backend_remote}/lib")
            upload_tree(sftp, args.backend_classes, posixpath.join(args.backend_remote, "classes"))
            upload_files(sftp, args.backend_lib, posixpath.join(args.backend_remote, "lib"))
        finally:
            sftp.close()

        override_dir = f"/etc/systemd/system/{args.service}.service.d"
        override_path = f"{override_dir}/override.conf"
        override_content = (
            "[Service]\n"
            "ExecStart=\n"
            f"ExecStart=/usr/bin/java -cp {args.backend_remote}/classes:{args.backend_remote}/lib/* com.daylog.DaylogApplication\n"
        )
        run_command(client, f"mkdir -p {override_dir}")
        run_command(client, f"cat > {override_path} <<'EOF'\n{override_content}EOF")
        run_command(client, "systemctl daemon-reload")
        run_command(client, f"systemctl restart {args.service}", timeout=180)
        run_command(client, "sleep 10")
        status = run_command(
            client,
            f"systemctl is-active {args.service} && curl -fsS '{args.health_url}' > /dev/null && echo ok",
            timeout=180,
        ).strip()
        print(status)
    finally:
        client.close()


if __name__ == "__main__":
    main()
