#!/usr/bin/env python3
import argparse


def main_ssh():
    cli = argparse.ArgumentParser()
    cli.add_argument("server", nargs="?")
    cli.add_argument("--config", "-C", default=".aqx.ini")

    def call(opts):
        from aqx.tools import ssh
        from aqx.core import AppService

        app = AppService(opts.config)
        return ssh.main(app, opts.server)

    _run_main(cli, call)


def main_filetransfer():
    cli = argparse.ArgumentParser()
    cli.add_argument("server", nargs="?")
    cli.add_argument("--config", "-C", default=".aqx.ini")
    cli.add_argument("--skip-existing", action="store_true")
    cli.add_argument("--pattern")
    cli.add_argument("direction", choices=["get", "put"])
    cli.add_argument("file1")
    cli.add_argument("file2", nargs="?")

    def call(opts):
        from aqx.tools import filetransfer
        from aqx.core import AppService

        app = AppService(opts.config)
        if opts.file2 is None:
            opts.file2 = opts.file1
        if opts.skip_existing and opts.direction != "get":
            cli.error("--skip-existing is only supported for direction=get")
        return filetransfer.main(
            app,
            opts.server,
            opts.direction == "get",
            opts.file1,
            opts.file2,
            skip_existing=opts.skip_existing,
            pattern=opts.pattern,
        )

    _run_main(cli, call)


def main_deploy():
    cli = argparse.ArgumentParser()
    cli.add_argument("servers", nargs="+")
    cli.add_argument("--config", "-C", default=".aqx.ini")

    def call(opts):
        from aqx.tools import deploy
        from aqx.core import AppService

        app = AppService(opts.config)
        return deploy.main(app, opts.servers)

    _run_main(cli, call)


def main_openserver():
    cli = argparse.ArgumentParser()
    cli.add_argument("--config", "-C", default=".aqx.ini")
    cli.add_argument("server")
    cli.add_argument("port", type=int)

    def call(opts):
        from aqx.tools import openserver
        from aqx.core import AppService

        app = AppService(opts.config)
        return openserver.main(app, opts.server, opts.port)

    _run_main(cli, call)


def _run_main(cli, func):
    opts = cli.parse_args()

    import logging

    logging.basicConfig(level=logging.INFO)

    import sys

    sys.exit(func(opts))
