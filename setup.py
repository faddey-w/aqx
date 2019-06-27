from distutils.core import setup

setup(
    name="aqx",
    version="0.0.1",
    description="Command-line tools for developers",
    packages=["aqx", "aqx.tools"],
    install_requires=["boto3", "tqdm", "paramiko"],
    python_requires=">=3.6.0",
    entry_points={"console_scripts": [
        "aqx-cmd=aqx.main:main_cmd",
        "aqx-deploy=aqx.main:main_deploy",
        "aqx-filetransfer=aqx.main:main_filetransfer",
        "aqx-openserver=aqx.main:main_openserver",
        "aqx-ssh=aqx.main:main_ssh",
    ]},
)
