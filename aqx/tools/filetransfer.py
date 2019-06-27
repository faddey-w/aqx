import os
import tqdm
from aqx import sshutils


def main(config_ini, server, is_download, file1, file2):
    ssh_conn, home_dir = sshutils.get_ssh_connection(config_ini, server)

    with ssh_conn:
        pb = None
        last_filename = None

        def callback(filename, n_done, n_total):
            nonlocal pb, last_filename
            if filename != last_filename:
                if pb:
                    pb.close()
                pb = tqdm.tqdm(desc=filename)
                last_filename = filename
            pb.total = n_total
            pb.n = n_done
            pb.update(0)

        if is_download:
            sshutils.download_file_or_directory(
                ssh_conn, os.path.join(home_dir, file1), file2, callback
            )
        else:
            sshutils.upload_file_or_directory(
                ssh_conn, file1, os.path.join(home_dir, file2), callback
            )
