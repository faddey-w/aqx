#!/usr/bin/env python3
from aqx import tool_cli


def main_ssh():
    _run_main(tool_cli.interface_ssh)


def main_filetransfer():
    _run_main(tool_cli.interface_filetransfer)


def main_deploy():
    _run_main(tool_cli.interface_deploy)


def main_openserver():
    _run_main(tool_cli.interface_openserver)


def _run_main(cli_fn):
    cli, func = cli_fn()
    opts = cli.parse_args()

    import logging

    logging.basicConfig(level=logging.INFO)

    import sys
    from aqx import core

    exec_srv = core.ExecutionService()

    try:
        sys.exit(func(opts, exec_srv))
    finally:
        pass
