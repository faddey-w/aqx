#!/usr/bin/env python

import subprocess
import logging
import threading
from typing import Optional
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


def send_patch(client: sshlib.SSH, patch_f):
    patch_contents: bytes = patch_f.result()
    if patch_contents:
        log.info("%s: sending patch contents...", client)
        rem_temp_file = client.cmd("mktemp").decode().strip()
        client.send_file(rem_temp_file, patch_contents)
        return rem_temp_file


def deploy_patch(client: sshlib.SSH, remote_dir: str, remote_patch_file: Optional[str]):
    client.cmd(f"cd {remote_dir}; git reset --hard")
    if remote_patch_file is not None:
        log.info("%s: installing patch...", client)
        client.cmd(f"cd {remote_dir}; git apply --index {remote_patch_file}")
    else:
        log.info(
            "%s: no local changes to deploy with patch - just cancel remote changes",
            client)


def cleanup_patch_on_remote(client: sshlib.SSH, remote_patch_file: Optional[str]):
    if remote_patch_file is not None:
        client.cmd(f"rm {remote_patch_file}")


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
        # send the patch in advance
        # even if later we'll find that git hashes are not OK, we more win than lose
        # because usually they're OK, so we save few additional seconds
        remote_patch_file_f = _acall(send_patch, ssh_conn, patch_f)

        # while patch is sending, check the git hashes
        remote_commit = get_remote_git_commit(ssh_conn, remote_path)
        local_commit = local_commit_f.result()
        if local_commit != remote_commit:
            freshen_remote(ssh_conn, remote_path)
            remote_commit = get_remote_git_commit(ssh_conn, remote_path)

        remote_patch_file = remote_patch_file_f.result()
        # now patch is sent, so we can install it if everything is fine
        if local_commit == remote_commit:
            deploy_patch(ssh_conn, remote_path, remote_patch_file)
            cleanup_patch_on_remote(ssh_conn, remote_patch_file)
        else:
            cleanup_patch_on_remote(ssh_conn, remote_patch_file)
            raise RevisionMismatchError
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
