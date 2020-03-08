import configparser
import threading
import socket
import logging
import time
import traceback
from concurrent.futures.thread import ThreadPoolExecutor
from aqx.sshlib import SSH


log = logging.getLogger(__name__)


class AppService:
    def __init__(self, ini_file):
        self._cp = configparser.ConfigParser()
        self._cp.read([ini_file])

    def maybe_resolve_host_alias(self, server_name):
        if server_name is None:
            return server_name
        if self._cp.has_section("server.host-aliases"):
            server_name = self._cp.get(
                "server.host-aliases", server_name, fallback=server_name
            )
        return server_name

    def create_ssh_connection(self, server_name) -> SSH:
        cp = self._cp
        if server_name is None:
            server_name = cp.get("server", "default")
        if server_name.startswith("aws."):
            
            from aqx.awslib import EC2Instances, Options

            if cp.has_section("aws.options"):
                ec2_use_private_ip = cp.getboolean(
                    "aws.options", "ec2_use_private_ip", fallback=False
                )
            else:
                ec2_use_private_ip = False
            options = Options(
                aws_access_key_id=cp.get("aws.access", "access_token"),
                aws_secret_access_key=cp.get("aws.access", "secret_token"),
                region_name=cp.get("aws.access", "region"),
                ec2_use_private_ip=ec2_use_private_ip,
            )

            api = EC2Instances(options=options)
            instance_name = server_name[4:]
            instance = api.get_by(name=instance_name)
            inst_ini_section = "server.aws." + instance_name
            private_key_path = cp.get(inst_ini_section, "private_key_path")
            username = cp.get(inst_ini_section, "user")
            home_dir = cp.get(inst_ini_section, "home_dir")
            ssh = api.get_ssh(instance, private_key_path, username)
            ssh.home_dir = home_dir
            return ssh
        section = f"server.{server_name}"
        ssh_user = cp.get(section, "ssh_user")
        ssh_address = cp.get(section, "ssh_address")
        home_dir = cp.get(section, "home_dir")
        private_key_path = cp.get(section, "private_key_path", fallback=None)
        return SSH(ssh_address, ssh_user, private_key_path, home_dir)


class ExecutionService:
    def __init__(self):
        self._executor = ThreadPoolExecutor()
        self._lock = threading.Lock()
        self._ssh_connections = {}
        self._pinger_thread = threading.Thread(
            target=_wrap_with_dumping_traceback(self._ping_worker), daemon=True
        )
        self._pinger_thread.start()

    def async_call(self, function, *args, **kwargs):
        """
        :return: Re-entrant blocking function that returns the result of call 
        """
        future = self._executor.submit(function, *args, **kwargs)
        return future.result

    def get_ssh_connection(self, server):
        with self._lock:
            return self._ssh_connections.pop(server)

    def add_ssh_connection(self, server, ssh: SSH):
        with self._lock:
            self._ssh_connections[server] = ssh

    def _ping_worker(self):
        while True:
            with self._lock:
                keys_and_conns = list(self._ssh_connections.items())
            for server, ssh in keys_and_conns:
                should_stop = False
                with self._lock:
                    if ssh.connected:
                        wait_fn, stdout, stderr = ssh.cmd_stream("echo")
                        try:
                            stdout.read()
                            wait_fn()
                        except socket.error:
                            log.info(f"Failed to ping to server: {server}, {ssh}")
                            should_stop = True
                            if self._ssh_connections.get(server) is ssh:
                                self._ssh_connections.pop(server)
                if should_stop:
                    ssh.stop()
            time.sleep(60)


def _wrap_with_dumping_traceback(function):
    def wrapper(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except BaseException:
            traceback.print_exc()
            raise

    return wrapper
