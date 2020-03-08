import socketserver
import argparse
import logging.config
import threading
import struct
from aqx import tool_cli, core


interfaces_map = {
    "ssh": tool_cli.interface_ssh,
    "filetransfer": tool_cli.interface_filetransfer,
    "deploy": tool_cli.interface_deploy,
    "openserver": tool_cli.interface_openserver,
}


class Protocol:
    STDERR = 1
    STDOUT = 2
    EXEC = 3
    BROWSE_URL = 4


def encode_message(protocol_header, msg):
    result = struct.pack("!I", protocol_header)
    result += msg.encode("utf-8")
    result += b"\0"
    return result


class AqxRequestHandler(socketserver.StreamRequestHandler):
    def handle(self):
        data = self.rfile.read()
        self.server.client_logger.stream = self.wfile
        parts = data.split(b"\0")
        parts = [part.decode("utf-8") for part in parts]

        cmd_type = parts[0]
        cmd_line = parts[1:]

        cli, call_cmd = interfaces_map[cmd_type]()
        opts = cli.parse_args(cmd_line)

        call_cmd(opts, self.server.execution_service)

    def finish(self):
        self.server.client_logger.stream = None


def main():
    client_logger = LogToClientHandler()
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "standard": {
                    "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
                }
            },
            "handlers": {
                "default": {
                    "level": "INFO",
                    "formatter": "standard",
                    "class": "logging.StreamHandler",
                },
                "client": {
                    "level": "INFO",
                    "formatter": "standard",
                    "()": lambda: client_logger,
                },
            },
            "loggers": {
                "": {
                    "handlers": ["default", "client"],
                    "level": "INFO",
                    "propagate": False,
                }
            },
        }
    )

    server = socketserver.ThreadingTCPServer("localhost:11397", AqxRequestHandler)
    server.execution_service = core.ExecutionService()
    server.client_logger = client_logger


class LogToClientHandler(logging.StreamHandler):

    terminator = b""

    def __init__(self):
        self._stream = threading.local()
        super(LogToClientHandler, self).__init__()
        self.stream = None

    @property
    def stream(self):
        return self._stream.stream

    @stream.setter
    def stream(self, stream):
        self._stream.stream = stream

    def emit(self, record):
        if self.stream is None:
            return
        return super(LogToClientHandler, self).emit(record)

    def format(self, record):
        msg = super(LogToClientHandler, self).format(record)
        return encode_message(Protocol.STDERR, msg + "\n")
