import webbrowser
from aqx import sshutils


def main(config_ini, server, port):
    ssh_conn, _ = sshutils.get_ssh_connection(config_ini, server)
    url = f"http://{ssh_conn.remote_host}:{port}"
    webbrowser.open(url)
