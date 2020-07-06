import os
import io
import paramiko
import logging
import warnings
import stat
import fnmatch
import threading


log = logging.getLogger("sshlib")


class SSH:
    def __init__(self, ssh_address, ssh_user, private_key_path=None, home_dir=None):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        if ssh_address.count(":") == 1:
            hostname, port = ssh_address.split(":")
            port = int(port)
        else:
            hostname, port = ssh_address, paramiko.config.SSH_PORT
        if private_key_path is None:
            private_key_path = os.path.expanduser("~/.ssh/id_rsa")
        pkey = paramiko.RSAKey.from_private_key_file(private_key_path)
        self._address = ssh_address
        self._connect_params = dict(
            hostname=hostname, port=port, username=ssh_user, timeout=30, pkey=pkey
        )
        self._private_key_path = private_key_path
        self._client = client
        self._sftp = None
        self.home_dir = home_dir
        self._connected = threading.Event()

    def __enter__(self):
        self.start()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()

    def start(self):
        log.info("%r: connecting...", self)
        with warnings.catch_warnings():
            # annoying deprecation warning from Crypto lib
            warnings.simplefilter("ignore")
            self._client.connect(**self._connect_params)
            self._connected.set()

    def stop(self):
        self._connected.clear()
        if self._sftp is not None:
            self._sftp.close()
        self._client.close()

    @property
    def connected(self):
        return self._connected.isSet()

    def cmd_stream(self, command: str):
        log.info("%r: cmd: %s", self, command)
        chan = self._client.get_transport().open_session()  # type: paramiko.Channel
        paramiko.agent.AgentRequestHandler(chan)
        chan.exec_command(command)
        stdout = chan.makefile("rb")
        stderr = chan.makefile_stderr("rb")

        def wait_fn():
            rc = chan.recv_exit_status()
            chan.close()
            return rc

        return wait_fn, stdout, stderr

    def cmd(self, command: str) -> bytes:
        wait_fn, stdout, stderr = self.cmd_stream(command)
        output = stdout.read()
        errors = stderr.read().decode()
        rc = wait_fn()
        if rc != 0:
            raise SshCommandError(f"{command} -> exited with {rc}: {errors}")
        return output

    def _get_stfp(self) -> paramiko.SFTP:
        if self._sftp is None:
            self._sftp = self._client.open_sftp()
        return self._sftp

    def send_file(self, remote_path: str, contents, callback=None):
        log.info("%r: sending file to %s", self, remote_path)
        if isinstance(contents, (str, bytes)):
            if isinstance(contents, str):
                contents = contents.encode()
            contents_io = io.BytesIO()
            contents_io.write(contents)
            contents_io.seek(0)
            contents = contents_io
        self._get_stfp().putfo(contents, remote_path, callback=callback)

    def download_file(self, remote_path: str, local_file=None, callback=None) -> bytes:
        log.info("%r: downloading file from %s", self, remote_path)
        if local_file is None:
            local_file = io.BytesIO()
            return_value = True
            need_close = False
        elif isinstance(local_file, str):
            local_file = open(local_file, "wb")
            return_value = False
            need_close = True
        else:
            return_value = False
            need_close = False
        self._get_stfp().getfo(remote_path, local_file, callback=callback)
        if need_close:
            local_file.close()
        if return_value:
            return local_file.getvalue()

    def stat_file(self, remote_path: str):
        try:
            return self._get_stfp().stat(remote_path)
        except FileNotFoundError:
            return None

    def listdir(self, remote_path: str, with_attrs=False) -> list:
        files = self._get_stfp().listdir_attr(remote_path)
        if not with_attrs:
            files = [f.filename for f in files]
        return files

    def __repr__(self):
        return f"SSH({self._connect_params['username']}@{self._address})"

    @property
    def remote_host(self):
        return self._connect_params["hostname"]


class SshCommandError(Exception):
    pass


def download_file_or_directory(
    ssh: SSH,
    remote_path,
    local_path,
    callback=None,
    skip_existing=False,
    pattern=None,
    _remote_st=None,
    _relpath="",
):
    if _remote_st is None:
        _remote_st = ssh.stat_file(remote_path)
    if _remote_st is None:
        raise FileNotFoundError(remote_path)
    if stat.S_ISDIR(_remote_st.st_mode):
        fileattrs = ssh.listdir(remote_path, with_attrs=True)
        for fattr in fileattrs:
            download_file_or_directory(
                ssh,
                os.path.join(remote_path, fattr.filename),
                os.path.join(local_path, fattr.filename),
                callback,
                skip_existing=skip_existing,
                pattern=pattern,
                _remote_st=fattr,
                _relpath=os.path.join(_relpath, fattr.filename),
            )
    else:

        if pattern is not None:
            remote_name = os.path.basename(remote_path)
            if not fnmatch.fnmatch(remote_name, pattern):
                return

        if skip_existing and os.path.exists(local_path):
            log.info(
                f'skip remote file "{remote_path}" '
                f'- already exists locally at "{local_path}"'
            )
            return

        def wrap_callback(n_done, n_total):
            if callback:
                callback(_relpath, n_done, n_total)

        local_dir = os.path.dirname(local_path)
        if local_dir != "":
            os.makedirs(local_dir, exist_ok=True)
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
