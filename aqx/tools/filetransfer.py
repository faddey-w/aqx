import os
import tqdm
from aqx import sshlib, core


def main(
    app: core.AppService, server, is_download, file1, file2, skip_existing, pattern
):
    server = app.maybe_resolve_host_alias(server)
    ssh_conn = app.get_host(server).make_ssh_connection()

    with ssh_conn:
        run_filetransfer(ssh_conn, is_download, file1, file2, skip_existing, pattern)


def run_filetransfer(
    ssh_conn: sshlib.SSH, is_download, file1, file2, skip_existing, pattern
):
    pb = None
    last_filename = None

    remote_home_dir = ssh_conn.home_dir

    def callback(filename, n_done, n_total):
        nonlocal pb, last_filename
        if filename != last_filename:
            if pb:
                pb.close()
            pb = tqdm.tqdm(desc=filename, unit="B", unit_scale=True, unit_divisor=1024)
            last_filename = filename
        pb.total = n_total
        pb.n = n_done
        pb.update(0)

    if is_download:
        sshlib.download_file_or_directory(
            ssh_conn,
            os.path.join(remote_home_dir, file1),
            file2,
            callback,
            skip_existing=skip_existing,
            pattern=pattern,
        )
    else:
        sshlib.upload_file_or_directory(
            ssh_conn, file1, os.path.join(remote_home_dir, file2), callback
        )

    if pb:
        pb.close()
