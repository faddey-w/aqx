import os
from aqx import sshutils


def main(config_ini, server):
    server = sshutils.maybe_resolve_host_alias(config_ini, server)
    ssh_conn, home_dir = sshutils.get_ssh_connection(config_ini, server)
    command = ssh_conn.get_connect_commandline()
    print(command)
    os.system(command)
