import webbrowser
from aqx import core


def main(app: core.AppService, server, port):
    server = app.maybe_resolve_host_alias(server)
    ssh_conn = app.create_ssh_connection(server)
    url = f"http://{ssh_conn.remote_host}:{port}"
    webbrowser.open(url)
