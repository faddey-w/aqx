from aqx import sshutils


def main(config_ini, server, commandline):
    ssh_conn, home_dir = sshutils.get_ssh_connection(config_ini, server)
    ssh_conn.cmd()
