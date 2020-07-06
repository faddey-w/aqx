#!/usr/bin/env python3
from aqx import tool_cli
import logging.config


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

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "handlers": {
                "stderr": {
                    "level": "DEBUG",
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                }
            },
            "filters": {},
            "formatters": {
                "default": {
                    "()": _LevelConditionalFormatter,
                    "default_fmt": "%(asctime)s %(levelname)s:%(name)s: %(message)s",
                    "INFO": "%(asctime)s %(name)s: %(message)s",
                }
            },
            "loggers": {"": {"handlers": ["stderr"], "level": "INFO"}},
        }
    )

    import sys
    from aqx import core

    exec_srv = core.ExecutionService()

    try:
        sys.exit(func(opts, exec_srv))
    finally:
        pass


class _LevelConditionalFormatter(logging.Formatter):
    def __init__(self, default_fmt, **perlevel_formats):
        super(_LevelConditionalFormatter, self).__init__()
        self._default_style = logging.PercentStyle(default_fmt)
        self._perlevel_styles = {
            level: logging.PercentStyle(fmt)
            for level, fmt in perlevel_formats.items()
        }

    def formatMessage(self, record):
        style = self._perlevel_styles.get(record.levelname, self._default_style)
        return style.format(record)

    def usesTime(self):
        return True
