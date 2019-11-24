import os
import io
import paramiko
import logging
import warnings


log = logging.getLogger(__name__)


class SSH:
    def __init__(self, ssh_address, ssh_user, private_key_path=None):
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
        self.connect_commandline_flags = ""

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

    def stop(self):
        if self._sftp is not None:
            self._sftp.close()
        self._client.close()

    def cmd_stream(self, command: str):
        log.info("%r: cmd: %s", self, command)
        chan = self._client.get_transport().open_session()  # type: paramiko.Channel
        paramiko.agent.AgentRequestHandler(chan)
        chan.exec_command(command)
        stdout = chan.makefile("rb")
        stderr = chan.makefile_stderr("rb")
        wait_fn = chan.recv_exit_status
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

    def get_connect_commandline(self):
        user = self._connect_params["username"]
        return (
            f"ssh {self.connect_commandline_flags} "
            f"-A "
            f"-i {self._private_key_path} "
            f"{user}@{self._address}"
        )

    def __repr__(self):
        return f"SSH({self._connect_params['username']}@{self._address})"

    @property
    def remote_host(self):
        return self._connect_params["hostname"]


class SshCommandError(Exception):
    pass
