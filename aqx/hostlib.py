import dataclasses
import typing


@dataclasses.dataclass
class Host:
    name: str
    address: str
    username: str
    home_dir: str
    private_key_path: str = None
    is_aws_ec2: bool = False
    aws_options: object = None

    @classmethod
    def from_configparser(cls, cp, server_name) -> "Host":
        if server_name is None:
            server_name = cp.get("server", "default")
        if server_name.startswith("aws."):

            from aqx.awslib import Options

            options = Options(
                aws_access_key_id=cp.get("aws.access", "access_token"),
                aws_secret_access_key=cp.get("aws.access", "secret_token"),
                region_name=cp.get("aws.access", "region"),
            )

            instance_name = server_name[4:]
            inst_ini_section = "server.aws." + instance_name
            return cls(
                name=server_name,
                address=instance_name,
                username=cp.get(inst_ini_section, "user"),
                home_dir=cp.get(inst_ini_section, "home_dir"),
                private_key_path=cp.get(inst_ini_section, "private_key_path"),
                is_aws_ec2=True,
                aws_options=options,
            )
        else:
            section = f"server.{server_name}"
            return cls(
                name=server_name,
                address=cp.get(section, "ssh_address"),
                username=cp.get(section, "ssh_user"),
                home_dir=cp.get(section, "home_dir"),
                private_key_path=cp.get(section, "private_key_path", fallback=None),
                is_aws_ec2=False,
                aws_options=None,
            )

    @property
    def ec2_instances_api(self):
        if not self.is_aws_ec2:
            raise ValueError("Not an AWS EC2 host")
        from aqx.awslib import EC2Instances, Options

        api = EC2Instances(options=typing.cast(Options, self.aws_options))
        self.__dict__["ec2_instances_api"] = api
        return api

    def get_inet_address(self):
        if self.is_aws_ec2:
            api = self.ec2_instances_api
            instance = api.get_by(name=self.address)
            return instance.ip_address
        else:
            return self.address

    def make_ssh_connection(self):
        if self.is_aws_ec2:
            api = self.ec2_instances_api
            instance = api.get_by(name=self.address)
            ssh = api.get_ssh(instance, self.private_key_path, self.username)
            ssh.home_dir = self.home_dir
            return ssh
        else:
            from aqx.sshlib import SSH

            return SSH(
                self.address, self.username, self.private_key_path, self.home_dir
            )

    def get_shh_connect_commandline(self):
        if self.is_aws_ec2:
            flags = "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
        else:
            flags = ""
        return (
            f"ssh {flags} -A -i {self.private_key_path} "
            f"{self.username}@{self.get_inet_address()}"
        )
