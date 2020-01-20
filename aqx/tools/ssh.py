import os
from aqx import core


def main(app: core.AppService, server):
    server = app.maybe_resolve_host_alias(server)
    ssh_conn = app.create_ssh_connection(server)
    command = ssh_conn.get_connect_commandline()
    print(command)
    os.system(command)
