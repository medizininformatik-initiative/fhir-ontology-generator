from contextlib import contextmanager
from typing import ContextManager

from docker.models.containers import Container

_logger = logging.getLogger(__name__)


@contextmanager
def docker_container(name: str, image: str, **kwargs) -> ContextManager[Container]:
    """
    Context manager for a Docker Container under the given name using the given image. Handles creation, start up, and
    stopping of the container

    :param name: Name of the container
    :param image: Image to create the container from
    :param kwargs: Key words arguments to pass to ``docker.containers.run()``
    :return: Docker container object
    """
    client = docker.from_env()
    existing_containers = client.containers.list(
        all=True, filters={"name": container_name}
    )
    for container in existing_containers:
        _logger.debug(
            f"Stopping and removing existing Docker container {container.name!r}"
        )
        container.stop()
        container.remove()
    container = client.containers.run(
        image,
        detach=True,
        **kwargs
    )
    _logger.debug(f"Started Docker container {container.name!r}")
    try:
        yield container
    finally:
        _logger.debug(f"Stopping and removing Docker container {container.name!r}")
        container.stop()
        container.remove()
