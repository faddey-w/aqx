import configparser
import stat
import os
import logging
from typing import Tuple
from aqx.sshlib import SSH


log = logging.getLogger(__name__)


def maybe_resolve_host_alias(ini_file, server_name):
    if server_name is None:
        return server_name
    cp = configparser.ConfigParser()
    cp.read([ini_file])
    if cp.has_section("server.host-aliases"):
        server_name = cp.get("server.host-aliases", server_name, fallback=server_name)
    return server_name


def get_ssh_connection(ini_file, server_name=None) -> Tuple[SSH, str]:

    cp = configparser.ConfigParser()
    cp.read([ini_file])
    if server_name is None:
        server_name = cp.get("server", "default")
    if server_name.startswith("aws."):
        from aqx.awslib import EC2Instances

        api = EC2Instances(config_ini=ini_file)
        instance_name = server_name[4:]
        instance = api.get_by(name=instance_name)
        inst_ini_section = "server.aws." + instance_name
        private_key_path = cp.get(inst_ini_section, "private_key_path")
        username = cp.get(inst_ini_section, "user")
        home_dir = cp.get(inst_ini_section, "home_dir")
        return api.get_ssh(instance, private_key_path, username), home_dir
    section = f"server.{server_name}"
    ssh_user = cp.get(section, "ssh_user")
    ssh_address = cp.get(section, "ssh_address")
    home_dir = cp.get(section, "home_dir")
    private_key_path = cp.get(section, "private_key_path", fallback=None)
    client = SSH(ssh_address, ssh_user, private_key_path)
    return client, home_dir


def download_file_or_directory(
    ssh: SSH,
    remote_path,
    local_path,
    callback=None,
    skip_existing=False,
    _remote_st=None,
    _relpath="",
):
    if _remote_st is None:
        _remote_st = ssh.stat_file(remote_path)
    if _remote_st is None:
        raise FileNotFoundError(remote_path)
    local_dir = os.path.dirname(local_path)
    if local_dir != "":
        os.makedirs(local_dir, exist_ok=True)
    if stat.S_ISDIR(_remote_st.st_mode):
        fileattrs = ssh.listdir(remote_path, with_attrs=True)
        os.makedirs(local_path, exist_ok=True)
        for fattr in fileattrs:
            download_file_or_directory(
                ssh,
                os.path.join(remote_path, fattr.filename),
                os.path.join(local_path, fattr.filename),
                callback,
                skip_existing=skip_existing,
                _remote_st=fattr,
                _relpath=os.path.join(_relpath, fattr.filename),
            )
    else:

        def wrap_callback(n_done, n_total):
            if callback:
                callback(_relpath, n_done, n_total)

        if skip_existing and os.path.exists(local_path):
            log.info(
                f'skip remote file "{remote_path}" '
                f'- already exists locally at "{local_path}"'
            )
            return
        ssh.download_file(remote_path, local_path, wrap_callback)


def upload_file_or_directory(ssh: SSH, local_path, remote_path, callback=None):
    def wrap_callback(n_done, n_total):
        if callback:
            callback(display_path, n_done, n_total)

    if os.path.isdir(local_path):
        for parentdir, dirs, files in os.walk(local_path):
            dir_relpath = os.path.relpath(parentdir, local_path)
            if dir_relpath == ".":
                dir_relpath = ""
            ssh.cmd("mkdir " + os.path.join(remote_path, dir_relpath))
            for fname in files:
                file_path = os.path.join(parentdir, fname)
                relpath = os.path.relpath(file_path, local_path)
                display_path = file_path
                with open(file_path, "rb") as f:
                    ssh.send_file(os.path.join(remote_path, relpath), f, wrap_callback)
    else:
        display_path = local_path
        with open(local_path, "rb") as f:
            ssh.send_file(remote_path, f, wrap_callback)
