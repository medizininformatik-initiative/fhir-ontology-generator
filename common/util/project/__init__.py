import abc
import os.path
from functools import cached_property
from pathlib import Path
from typing import Optional, Annotated, Mapping, Type, TypeVar

import dotenv
import yaml
from pydantic import BaseModel, Field, ValidationError, computed_field
from yaml import Loader

from common.util.fhir.package.manager import (
    FhirPackageManager,
    GitHubPackageManager,
    FirelyPackageManager,
    RepositoryPackageManager,
)
from common.util.log.functions import get_class_logger
from common.constants.project import PROJECT_ROOT
from common.config.project import ProjectConfig


class ProjectDir(BaseModel):
    path: Annotated[
        Path,
        Field(
            strict=True,
            frozen=True,
            init=True,
            description="Path object pointing to the root " "directory of the project",
        ),
    ]

    def __init__(self, path: str | Path, /, **kwargs):
        _path = Path(path).resolve()
        _path.mkdir(parents=True, exist_ok=True)
        super().__init__(path=_path, **kwargs)

    def __truediv__(self, other: str) -> Path:
        return self.path / other

    def mkdirs(self, *rel_path: str) -> Path:
        path = self.path / os.sep.join(rel_path)
        path.mkdir(parents=True, exist_ok=True)
        return path


D = TypeVar("D", bound="ProjectDir")


def _sub_dir(name: str, _path: Path, _cls: Type[D] = ProjectDir) -> D:
    return _cls(_path / name)


class IODir(ProjectDir, abc.ABC):
    def __init__(self, path: Path, /, **kwargs):
        super().__init__(path, **kwargs)

    @computed_field
    @property
    def availability(self) -> ProjectDir:
        return _sub_dir("availability", self.path)

    @computed_field
    @property
    def dse(self) -> ProjectDir:
        return _sub_dir("data_selection_extraction", self.path)

    @computed_field
    @property
    def cso(self) -> ProjectDir:
        return _sub_dir("cohort_selection_ontology", self.path)

    @computed_field
    @property
    def terminology(self) -> ProjectDir:
        return _sub_dir("terminology", self.path)

    @computed_field
    @property
    def translation(self) -> ProjectDir:
        return _sub_dir("translation", self.path)

    @computed_field
    @property
    def elastic(self) -> ProjectDir:
        return _sub_dir("elastic", self.path)


class InputDir(IODir):
    pass


class OutputDir(IODir):
    def __init__(self, path: Path, /, **kwargs):
        super().__init__(path, **kwargs)

    @computed_field
    @property
    def generated_ontology(self) -> ProjectDir:
        return _sub_dir("merged_ontology", self.path)


class Project(ProjectDir):
    """
    Utility class representing the project context. Instances provide safe access to the directory structure of a given
    project, its location on the filesystem, and environment variables.
    """

    __logger = get_class_logger("Project")

    name: Annotated[
        str,
        Field(
            strict=True,
            frozen=True,
            init=False,
            description="Name of the project, i.e. the name of its root directory in the projects directory",
        ),
    ]
    env: Annotated[
        Mapping[str, str],
        Field(
            frozen=True,
            init=False,
            description="Environment variables in the scope of the project",
        ),
    ]
    config: Annotated[ProjectConfig, Field(frozen=True, default=ProjectConfig())]

    name: Annotated[Optional[str], Field(init_var=True)] = None
    path: Annotated[Optional[str | Path], Field(init_var=True)] = None

    @classmethod
    def any_of(
        cls, name: Optional[str] = None, path: Optional[str | Path] = None
    ) -> (str, Path, Mapping[str, str], ProjectConfig):
        if not name and not path:
            raise ValidationError(
                "At least one parameter has to be provided with a value other than 'None'"
            )
        # name & path
        if name is None:
            name = os.path.basename(path)
        else:
            if path is None:
                path = Path(str(os.path.join(PROJECT_ROOT, "projects", name)))
        if isinstance(path, str):
            path = Path(path)
        # env
        dotenv.load_dotenv()
        env = os.environ
        # config
        project_config = None
        for fp in path.iterdir():
            if fp.is_file() and fp.stem == "config" and fp.suffix in {".yaml", ".yml"}:
                with fp.open(mode="r", encoding="utf-8") as config_f:
                    project_config = yaml.load(config_f, Loader=Loader)
                    break
        if not project_config:
            project_config = ProjectConfig()
        return name, path, env, project_config

    def __init__(self, name: Optional[str] = None, path: Optional[str | Path] = None):
        _name, _path, _env, _conf = self.any_of(name, path)
        super().__init__(_path, name=_name, env=_env, config=_conf)
        if not os.path.exists(self.path):
            self.__logger.warning(
                f"No project '{self.name}' exists @ {self.path}. Operating on it will likely result "
                f"in failure"
            )

    @staticmethod
    def __create_dirs(path: Path):
        os.makedirs(path, exist_ok=True)

    @computed_field
    @property
    def input(self) -> InputDir:
        return _sub_dir("input", self.path, InputDir)

    @computed_field
    @property
    def output(self) -> OutputDir:
        return _sub_dir("output", self.path, OutputDir)

    @cached_property
    def package_manager(self) -> FhirPackageManager:
        manager_conf = self.config.fhir_packages.manager
        params = manager_conf.params
        if "package_dir" not in params:
            params = params.copy()
            params["package_dir"] = self.path
        match manager_conf.type:
            case "firely":
                return FirelyPackageManager(**params)
            case "repository":
                return RepositoryPackageManager(**params)
            case "github":
                return GitHubPackageManager(**params)
            case _:
                raise ValueError(
                    f"Unsupported FHIR package manager type '{manager_conf.type}'"
                )
