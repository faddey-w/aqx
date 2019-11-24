import boto3
import configparser
import os
import time
import logging
import dataclasses
from aqx import sshlib


log = logging.getLogger(__name__)


def get_default_api(service, config_ini=".aqx.ini"):
    if config_ini is not None:
        cp = _load_config(config_ini)
    else:
        cp = None
    return _get_default_api(service, cp)


def _load_config(config_ini=None) -> configparser.ConfigParser:
    cp = configparser.ConfigParser()
    if config_ini is not None:
        config_path = os.path.join(os.getcwd(), config_ini)
        cp.read(config_path)
    return cp


def _get_default_api(service, config: configparser.ConfigParser = None):
    kwargs = {}
    if config is not None and config.has_section("aws.access"):
        kwargs.update(
            aws_access_key_id=config.get("aws.access", "access_token"),
            aws_secret_access_key=config.get("aws.access", "secret_token"),
            region_name=config.get("aws.access", "region"),
        )

    return boto3.client(service, **kwargs)


@dataclasses.dataclass
class EC2Instance:
    id: str
    name: str
    type: str
    state: str
    key_name: str
    ip_address: str = None


class EC2Instances:
    def __init__(self, api=None, config_ini=None):
        cfg = _load_config(config_ini)
        self.api = api or _get_default_api("ec2", cfg)
        self._cache = None
        self.use_private_ip = False
        if cfg and cfg.has_section("aws.options"):
            self.use_private_ip = cfg.getboolean(
                "aws.options", "ec2_use_private_ip", fallback=False
            )

    def create(self, name, instance_type, ssh_key_id):
        raise NotImplementedError

    def _load(self, instance_ids=None):
        kwargs = {}
        if instance_ids is not None:
            kwargs["InstanceIds"] = instance_ids
        instances_data = self.api.describe_instances(**kwargs)
        result = []
        for item in instances_data["Reservations"]:
            inst = item["Instances"][0]
            name = None
            for tag in inst["Tags"]:
                if tag["Key"] == "Name":
                    name = tag["Value"]
                    break
            inst_obj = EC2Instance(
                id=inst["InstanceId"],
                name=name,
                type=inst["InstanceType"],
                state=inst["State"]["Name"],
                key_name=inst["KeyName"],
            )
            if inst_obj.state == "running":
                if self.use_private_ip:
                    inst_obj.ip_address = inst["PrivateIpAddress"]
                else:
                    inst_obj.ip_address = inst["PublicIpAddress"]
            result.append(inst_obj)
        log.debug("found instances on AWS: %s", result)
        return result

    def load(self):
        self._cache = self._load()

    def list(self):
        if self._cache is None:
            self.load()
        return self._cache[:]

    def get_by(self, *, name=None, id=None) -> EC2Instance:
        if self._cache is None:
            self.load()
        for inst in self._cache:
            if name is not None and name == inst.name:
                return inst
            if id is not None and id == inst.id:
                return inst
        raise KeyError(name)

    def run(self, instance, wait=False):
        inst_id = self._get_instance_id(instance)
        self.api.start_instances(InstanceIds=[inst_id])
        if wait:
            self._wait_until_state(inst_id, "running")

    def stop(self, instance, wait=False):
        inst_id = self._get_instance_id(instance)
        self.api.stop_instances(InstanceIds=[inst_id])
        if wait:
            self._wait_until_state(inst_id, "stopped")

    def delete(self, instance):
        raise NotImplementedError

    def get_ssh(self, instance, key_path, user="ec2-user"):
        if isinstance(instance, EC2Instance):
            ip_addr = instance.ip_address
        else:
            inst_id = self._get_instance_id(instance)
            instance = self.get_by(id=inst_id)
            ip_addr = instance.ip_address
        conn = sshlib.SSH(ip_addr, user, private_key_path=key_path)
        conn.connect_commandline_flags = (
            "-o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no"
        )
        return conn

    def _get_instance_id(self, instance):
        if isinstance(instance, EC2Instance):
            return instance.id
        if isinstance(instance, str):
            if instance.startswith("i-"):
                return instance
            return self.get_by(name=instance).id
        raise TypeError(type(instance))

    def _wait_until_state(self, instance_id, state, timeout=60):
        deadline_time = time.time() + timeout
        while time.time() < deadline_time:
            [inst] = self._load([instance_id])
            if inst.state == state:
                return
            time.sleep(5)
        raise Exception(f"could not wait for state {state} of instance {instance_id}")
