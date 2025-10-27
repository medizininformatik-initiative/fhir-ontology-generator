from collections.abc import Callable
from os import remove
from typing import Optional, Literal

import docker

from docker.models.containers import Container

from common.constants.docker import POSTGRES_IMAGE
from common.util.log.functions import get_logger


_logger = get_logger(__file__)


class DockerContainer(object):
    __container: Container
    __on_exit: Optional[Callable[[Container], None]] = None

    def __init__(self, name: str, remove_existing: bool = True, detach: bool = True,
                 on_exit: Optional[Callable[[Container], None]] = None, **kwargs):
        """
        Creates a context manager instance managing a Docker container object

        :param name: Container name
        :param remove_existing: If `True` removes existing Docker containers with the same container name
        :param detach: If `True` run Docker container in detached mode
        :param on_exit: Action to run using Docker container before its shutdown and removal
        :param kwargs: Additional arguments passed to the Docker container object constructor. See
                       `docker.models.containers.ContainerCollection::run`
        """
        client = docker.from_env()
        if remove_existing:
            existing_containers = client.containers.list(all=True, filters={"name": name})
            if existing_containers:
                _logger.debug(f"Stopping and removing {len(existing_containers)} existing containers named '{name}'")
            for container in existing_containers:
                container.stop()
                container.remove()
        _logger.debug(f"Starting container '{name}'")
        self.__container = client.containers.run(name=name, detach=detach, **kwargs)
        self.__on_exit = on_exit

    def __enter__(self) -> Container:
        return self.__container

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        _logger.debug(f"Stopping and removing container '{self.__container.name}'")
        exit_action_exc = None
        if self.__on_exit:
            try:
                self.__on_exit(self.__container)
            except Exception as exc:
                exit_action_exc = Exception(f"Failed to execute exit action defined for Docker container "
                                            f"'{self.__container.name}'")
                exit_action_exc.__cause__ = exc
        self.__container.stop()
        self.__container.remove()
        if exc_val is None:
            return True
        else:
            # If the exit action raised itself chain the raised exception with the exception originating from within the
            # 'with' block. Technically the method does not handle the exception originating from within the 'with'
            # block although the printed traceback will indicate otherwise since this method does not handle it
            if exit_action_exc is not None:
                raise exit_action_exc from exc_val
            # Else return 'False' to indicate that the exception originating from within the 'with' block has not been
            # handled by this method
            else:
                return False


class PostgresContainer(DockerContainer):
    def __init__(self, name: str, host_port: int = 5432, volume_dir: Optional[str] = None, pg_user: str = "postgres",
                 pg_pw: str = "postgres", pg_db: str = "postgres", **kwargs):
        """
        Creates a context manager instance managing a PostgreSQL Docker container object

        :param name: Container name
        :param host_port: Port onto which the Docker containers port `5432` is mapped on the host machine
        :param volume_dir: Volume directory on the host machine to mount the PostgreSQL database file directory onto
        :param pg_user: Value for environment variable `POSTGRES_USER`
        :param pg_pw: Value for environment variable `POSTGRES_PASSWORD`
        :param pg_db: Value for environment variable `POSTGRES_DB`
        :param kwargs: Additional arguments passed to the constructor of the `DockerContainer` parent class
        """
        volumes = None
        if volume_dir:
            volumes = { volume_dir: {'bind': '/opt/db_data', 'mode': 'rw'} }
        environment = { 'POSTGRES_USER': pg_user, 'POSTGRES_PASSWORD': pg_pw, 'POSTGRES_DB': pg_db }
        super().__init__(name=name, remove_existing=True, ports={ '5432/tcp': host_port }, volumes=volumes,
                         environment=environment, image=POSTGRES_IMAGE, **kwargs)
