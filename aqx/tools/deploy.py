#!/usr/bin/env PYTHONPATH=. python

import subprocess
import logging
import datetime
from aqx import sshlib, core


log = logging.getLogger(__name__)


def get_local_git_commit():
    gh = subprocess.check_output("git rev-parse HEAD", shell=True).decode().strip()
    log.info("Local git hash: %s", gh)
    return gh


def get_remote_git_commit(client: sshlib.SSH, remote_dir: str):
    gh = client.cmd(f"cd {remote_dir}; git rev-parse HEAD")
    gh = gh.decode().strip()
    log.info("Remote git hash: %s", gh)
    return gh


def generate_patch():
    log.info("generating patch...")
    return subprocess.check_output("git diff HEAD", shell=True)


def send_and_deploy_patch(client: sshlib.SSH, patch_contents: bytes, remote_dir: str):
    rem_temp_file = client.cmd("mktemp").decode().strip()
    # rem_temp_file = os.path.join(remote_dir, "tmp.patch")
    client.cmd(f"cd {remote_dir}; git reset --hard")
    if patch_contents:
        log.info("sending patch contents...")
        client.send_file(rem_temp_file, patch_contents)
        client.cmd(f"cd {remote_dir}; git apply --index {rem_temp_file}")
        client.cmd(f"rm {rem_temp_file}")
    else:
        log.info("no local changes to deploy with patch - just cancel remote changes")


def freshen_remote(client: sshlib.SSH, remote_dir: str):
    log.info("Freshen remote's code...")
    client.cmd(f"cd {remote_dir}; git reset --hard")
    client.cmd(f"cd {remote_dir}; git pull")


def main(app: core.AppService, servers):
    for server in servers:
        server = app.maybe_resolve_host_alias(server)
        log.info("Deploying to server %s...", server)
        ssh_conn = app.get_host(server).make_ssh_connection()
        remote_path = ssh_conn.home_dir

        with ssh_conn:

            local_commit = get_local_git_commit()
            remote_commit = get_remote_git_commit(ssh_conn, remote_path)

            if local_commit != remote_commit:
                freshen_remote(ssh_conn, remote_path)
                remote_commit = get_remote_git_commit(ssh_conn, remote_path)

            if local_commit != remote_commit:
                raise Exception("Git commits do not match")
            patch = generate_patch()
            send_and_deploy_patch(ssh_conn, patch, remote_path)
    log.info("Done at %s", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
