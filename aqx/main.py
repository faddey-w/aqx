#!/usr/bin/env python3
import argparse


def main_ssh():
    cli = argparse.ArgumentParser()
    cli.add_argument("server", nargs="?")
    cli.add_argument("--config", "-C", default=".aqx.ini")

    def call(opts):
        from aqx.tools import ssh

        return ssh.main(opts.config, opts.server)

    _run_main(cli, call)


def main_filetransfer():
    cli = argparse.ArgumentParser()
    cli.add_argument("server", nargs="?")
    cli.add_argument("--config", "-C", default=".aqx.ini")
    cli.add_argument("direction", choices=["get", "put"])
    cli.add_argument("file1")
    cli.add_argument("file2", nargs="?")

    def call(opts):
        from aqx.tools import filetransfer

        if opts.file2 is None:
            opts.file2 = opts.file1
        return filetransfer.main(
            opts.config, opts.server, opts.direction == "get", opts.file1, opts.file2
        )

    _run_main(cli, call)


def main_cmd():
    cli = argparse.ArgumentParser()
    cli.add_argument("--server", "-S")
    cli.add_argument("--config", "-C", default=".aqx.ini")
    cli.add_argument("command", nargs="*")

    def call(opts):
        from aqx.tools import cmd

        return cmd.main(opts.config, opts.server, opts.command)

    _run_main(cli, call)


def main_deploy():
    cli = argparse.ArgumentParser()
    cli.add_argument("servers", nargs="+")
    cli.add_argument("--config", "-C", default=".aqx.ini")

    def call(opts):
        from aqx.tools import deploy

        return deploy.main(opts.config, opts.servers)

    _run_main(cli, call)


def main_openserver():
    cli = argparse.ArgumentParser()
    cli.add_argument("server", nargs="?")
    cli.add_argument("--config", "-C", default=".aqx.ini")
    cli.add_argument("--port", "-p", type=int)

    def call(opts):
        from aqx.tools import openserver

        return openserver.main(opts.config, opts.server, opts.port)

    _run_main(cli, call)


def _run_main(cli, func):
    opts = cli.parse_args()

    import logging
    logging.basicConfig(level=logging.INFO)

    import sys
    sys.exit(func(opts))


