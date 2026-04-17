import argparse
import os
import posixpath
from stat import S_ISDIR

import paramiko


def sftp_mkdir_p(sftp: paramiko.SFTPClient, remote_path: str) -> None:
    parts = remote_path.strip('/').split('/')
    current = ''
    for part in parts:
      current = f'{current}/{part}' if current else f'/{part}'
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


def upload_file(sftp: paramiko.SFTPClient, local_file: str, remote_file: str) -> None:
    if not os.path.exists(local_file):
        return
    remote_dir = posixpath.dirname(remote_file)
    sftp_mkdir_p(sftp, remote_dir)
    sftp.put(local_file, remote_file)


def run_command(client: paramiko.SSHClient, command: str, timeout: int = 120) -> str:
    stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
    exit_status = stdout.channel.recv_exit_status()
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if exit_status != 0:
        raise RuntimeError(f'command failed: {command}\nstdout:\n{out}\nstderr:\n{err}')
    return out + err


def remove_remote_tree(sftp: paramiko.SFTPClient, remote_path: str) -> None:
    for entry in sftp.listdir_attr(remote_path):
        child = posixpath.join(remote_path, entry.filename)
        if S_ISDIR(entry.st_mode):
            remove_remote_tree(sftp, child)
            sftp.rmdir(child)
        else:
            sftp.remove(child)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--user', required=True)
    parser.add_argument('--password', required=True)
    parser.add_argument('--frontend-dist', required=True)
    parser.add_argument('--frontend-remote', default='/opt/daylog/frontend')
    parser.add_argument('--python-root', required=True)
    parser.add_argument('--python-remote', default='/opt/daylog/python/app')
    args = parser.parse_args()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=args.password, timeout=30)

    try:
        sftp = client.open_sftp()
        try:
            run_command(client, f"mkdir -p {args.frontend_remote} {args.python_remote}/scrapers {args.python_remote}/db")
            try:
                remove_remote_tree(sftp, args.frontend_remote)
            except FileNotFoundError:
                pass
            upload_tree(sftp, args.frontend_dist, args.frontend_remote)
            upload_file(
                sftp,
                os.path.join(args.python_root, 'main.py'),
                posixpath.join(args.python_remote, 'main.py'),
            )
            upload_file(
                sftp,
                os.path.join(args.python_root, 'models.py'),
                posixpath.join(args.python_remote, 'models.py'),
            )
            upload_file(
                sftp,
                os.path.join(args.python_root, 'scrapers', 'weibo.py'),
                posixpath.join(args.python_remote, 'scrapers', 'weibo.py'),
            )
            upload_file(
                sftp,
                os.path.join(args.python_root, 'db', 'repository.py'),
                posixpath.join(args.python_remote, 'db', 'repository.py'),
            )
        finally:
            sftp.close()

        run_command(
            client,
            f'python3 -m py_compile {args.python_remote}/main.py '
            f'{args.python_remote}/models.py '
            f'{args.python_remote}/db/repository.py '
            f'{args.python_remote}/scrapers/weibo.py',
        )
        run_command(client, 'systemctl restart daylog-python')
        run_command(client, 'systemctl restart nginx')
        run_command(client, 'systemctl is-active daylog-python')
        run_command(client, 'systemctl is-active nginx')
    finally:
        client.close()


if __name__ == '__main__':
    main()
