import configparser
import threading
import socket
import logging
import time
import traceback
from concurrent.futures.thread import ThreadPoolExecutor
from aqx import hostlib


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

    def get_host(self, server_name):
        return hostlib.Host.from_configparser(self._cp, server_name)


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

    def add_ssh_connection(self, server, ssh):
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
