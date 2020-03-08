import argparse


def interface_ssh():
    cli = argparse.ArgumentParser()
    cli.add_argument("server", nargs="?")
    cli.add_argument("--config", "-C", default=".aqx.ini")

    def call(opts, execution_service):
        from aqx.tools import ssh
        from aqx.core import AppService

        app = AppService(opts.config)
        return ssh.main(app, opts.server)

    return cli, call


def interface_filetransfer():
    cli = argparse.ArgumentParser()
    cli.add_argument("server", nargs="?")
    cli.add_argument("--config", "-C", default=".aqx.ini")
    cli.add_argument("--skip-existing", action="store_true")
    cli.add_argument("--pattern")
    cli.add_argument("direction", choices=["get", "put"])
    cli.add_argument("file1")
    cli.add_argument("file2", nargs="?")

    def call(opts, execution_service):
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

    return cli, call


def interface_deploy():
    cli = argparse.ArgumentParser()
    cli.add_argument("servers", nargs="+")
    cli.add_argument("--config", "-C", default=".aqx.ini")

    def call(opts, execution_service):
        from aqx.tools import deploy
        from aqx.core import AppService

        app = AppService(opts.config)
        return deploy.main(app, opts.servers)

    return cli, call


def interface_openserver():
    cli = argparse.ArgumentParser()
    cli.add_argument("--config", "-C", default=".aqx.ini")
    cli.add_argument("server")
    cli.add_argument("port", type=int)

    def call(opts, execution_service):
        from aqx.tools import openserver
        from aqx.core import AppService

        app = AppService(opts.config)
        return openserver.main(app, opts.server, opts.port)

    return cli, call


def _run_main(cli, func, argv):
    opts = cli.parse_args(argv)

    import logging

    logging.basicConfig(level=logging.INFO)

    import sys

    try:
        sys.exit(func(opts))
    finally:
        pass
