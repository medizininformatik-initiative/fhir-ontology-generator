import os.path
from pathlib import Path
from typing import Optional, Annotated, Any, Mapping

import dotenv
from pydantic import BaseModel, Field, model_validator, ValidationError

from common.util.log.functions import get_class_logger
from common.constants.project import PROJECT_ROOT


class Project(BaseModel):
    """
    Utility class representing the project context. Instances provide safe access to the directory structure of a given
    project, its location on the filesystem, and environment variables.
    """
    __logger = get_class_logger("Project")

    name: Annotated[str, Field(strict=True, frozen=True, init=False, description="Name of the project, i.e. the name "
                                                                                 "of its root directory in the "
                                                                                 "projects directory")]
    path: Annotated[Path, Field(strict=True, frozen=True, init=False, description="Path object pointing to the root "
                                                                                  "directory of the project")]
    env: Annotated[Mapping[str, str], Field(frozen=True, init=False, description="Environment variables"
                                                                                              "in the scope of the "
                                                                                              "project")]

    name: Annotated[Optional[str], Field(init_var=True)] = None
    path: Annotated[Optional[str | Path], Field(init_var=True)] = None

    @model_validator(mode='before')
    @classmethod
    def any_of(cls, data: Any) -> Any:
        if not any(k in cls.model_fields and data[k] is not None for k in data.keys()):
            raise ValidationError("At least one parameter has to be provided with a value other than 'None'")
        # name & path
        if data.get('name') is None:
            data['name'] = os.path.basename(data['path'])
        else:
            if data.get('path') is None:
                data['path'] = Path(str(os.path.join(PROJECT_ROOT, "projects", data['name'])))
        # env
        dotenv.load_dotenv()
        data['env'] = os.environ
        return data

    def __init__(self, name: Optional[str] = None, path: Optional[str | Path] = None):
        super().__init__(name=name, path=Path(path).resolve() if path is not None else None)
        if not os.path.exists(self.path):
            self.__logger.warning(f"No project '{self.name}' exists @ {self.path}. Operating on it will likely result "
                                  f"in failure")

    @staticmethod
    def __create_dirs(path: Path):
        os.makedirs(path, exist_ok=True)

    def __truediv__(self, other: str) -> Path:
        return self.path / other

    def input(self, *rel_path: str) -> Path:
        """
        Returns a Path object representing the absolute path obtained by appending `rel_path` to the absolute path of
        the projects input directory
        :param rel_path: List of dir name strings
        :returns: Path object representing the combined path
        """
        path = self / os.path.join("input", *rel_path)
        self.__create_dirs(path)
        return path

    def output(self, *rel_path: str) -> Path:
        """
        Returns a Path object representing the absolute path obtained by appending `rel_path` to the absolute path of
        the projects output directory
        :param rel_path: List of dir name strings
        :returns: Path object representing the combined path
        """
        path = self / os.path.join("output", *rel_path)
        self.__create_dirs(path)
        return path
