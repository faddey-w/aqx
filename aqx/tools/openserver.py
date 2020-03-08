import webbrowser
from aqx import core


def main(app: core.AppService, server, port):
    server = app.maybe_resolve_host_alias(server)
    address = app.get_host(server).get_inet_address()
    url = f"http://{address}:{port}"
    webbrowser.open(url)
