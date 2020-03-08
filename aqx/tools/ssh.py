import os
from aqx import core


def main(app: core.AppService, server):
    server = app.maybe_resolve_host_alias(server)
    command = app.get_host(server).get_shh_connect_commandline()
    print(command)
    os.system(command)
