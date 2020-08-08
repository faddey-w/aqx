from distutils.core import setup

setup(
    name="aqx",
    version="0.0.3",
    description="Command-line tools for developers",
    packages=["aqx", "aqx.tools"],
    install_requires=["boto3", "tqdm", "paramiko"],
    python_requires=">=3.6.0",
    entry_points={"console_scripts": [
        "aqx-deploy=aqx.main_local:main_deploy",
        "aqx-filetransfer=aqx.main_local:main_filetransfer",
        "aqx-openserver=aqx.main_local:main_openserver",
        "aqx-ssh=aqx.main_local:main_ssh",
    ]},
)
