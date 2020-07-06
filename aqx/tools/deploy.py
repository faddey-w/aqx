#!/usr/bin/env python

import subprocess
import logging
import datetime
import sys
import threading
from concurrent.futures import Future
from aqx import sshlib, core


log = logging.getLogger("deploy")


def get_local_git_commit():
    gh = subprocess.check_output("git rev-parse HEAD", shell=True).decode().strip()
    log.info("Local git hash: %s", gh)
    return gh


def get_remote_git_commit(client: sshlib.SSH, remote_dir: str):
    gh = client.cmd(f"cd {remote_dir}; git rev-parse HEAD")
    gh = gh.decode().strip()
    log.info("%s: Remote git hash: %s", client, gh)
    return gh


def generate_patch():
    log.info("generating patch...")
    try:
        return subprocess.check_output("git diff HEAD", shell=True)
    finally:
        log.info("patch generated")


def send_and_deploy_patch(client: sshlib.SSH, patch_contents: bytes, remote_dir: str):
    rem_temp_file = client.cmd("mktemp").decode().strip()
    # rem_temp_file = os.path.join(remote_dir, "tmp.patch")
    client.cmd(f"cd {remote_dir}; git reset --hard")
    if patch_contents:
        log.info("%s: sending patch contents...", client)
        client.send_file(rem_temp_file, patch_contents)
        client.cmd(f"cd {remote_dir}; git apply --index {rem_temp_file}")
        client.cmd(f"rm {rem_temp_file}")
    else:
        log.info("%s: no local changes to deploy with patch - just cancel remote changes", client)


def freshen_remote(client: sshlib.SSH, remote_dir: str):
    log.info("%s: Freshen remote's code...", client)
    client.cmd(f"cd {remote_dir}; git reset --hard")
    client.cmd(f"cd {remote_dir}; git pull")


def deploy_one_server(app, server, local_commit_f, patch_f):
    server = app.maybe_resolve_host_alias(server)
    log.info("Deploying to server %s...", server)
    ssh_conn = app.get_host(server).make_ssh_connection()
    log.info("%s: connection=%s", server, ssh_conn)
    remote_path = ssh_conn.home_dir

    with ssh_conn:

        remote_commit = get_remote_git_commit(ssh_conn, remote_path)

        local_commit = local_commit_f.result()
        if local_commit != remote_commit:
            freshen_remote(ssh_conn, remote_path)
            remote_commit = get_remote_git_commit(ssh_conn, remote_path)

        if local_commit != remote_commit:
            raise RevisionMismatchError
        patch = patch_f.result()
        send_and_deploy_patch(ssh_conn, patch, remote_path)
    log.info("%s: done", server)


def main(app: core.AppService, servers):
    local_commit_f = _acall(get_local_git_commit)
    patch_f = _acall(generate_patch)
    deploy_fs = [
        _acall(deploy_one_server, app, server, local_commit_f, patch_f)
        for server in servers
    ]
    for server, deploy_f in zip(servers, deploy_fs):
        try:
            deploy_f.result()
        except RevisionMismatchError:
            log.error("%s: Git versions do not match", server)
        except:
            log.exception("%s")


def _acall(function, *args, **kwargs):
    future = Future()

    def function_call_main():
        try:
            result = function(*args, **kwargs)
        except BaseException as exc:
            future.set_exception(exc)
        else:
            future.set_result(result)

    threading.Thread(target=function_call_main).start()

    return future


class RevisionMismatchError(Exception):
    pass
