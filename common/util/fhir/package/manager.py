import abc
import functools
import json
import logging
import os
import re
import shutil
import subprocess
import tarfile
from collections import defaultdict, OrderedDict
from contextlib import contextmanager
from logging import Logger
from pathlib import Path
from subprocess import CalledProcessError
from typing import (
    Iterator,
    Mapping,
    Any,
    Optional,
    Literal,
    List,
    ContextManager,
    Annotated, Union,
)

import cachetools
import fhir.resources
from fhir.resources.R4B.resource import Resource
from fhir.resources.R4B.structuredefinition import StructureDefinition
from requests import Request
from requests.auth import AuthBase

from common.exceptions import UnsupportedError, NotFoundError
from common.model.fhir.structure_definition import IndexedStructureDefinition
from common.util.codec.json import load_json
from common.util.http.client import BaseClient
from common.util.log.decorators import inject_logger


def _profile_cache_key(*args, **kwargs) -> str:
    if args:
        param = args[1]
    else:
        param = kwargs["profile"]
    if isinstance(param, str):
        return param
    else:
        return param.url


def build_package_index(package_dir: Path) -> Mapping[str, Any]:
    """
    Build the content of an index file for the given package

    :param package_dir: Path to directory of the packages content
    :return: Mapping representing index file content
    """
    files = []
    index = {"index-version": 2, "files": files}
    for file_path in package_dir.glob("**/*.json"):
        bn = os.path.basename(file_path)
        content = load_json(file_path, encoding=["utf-8", "utf-8-sig"], fail=True)
        entry = {
            "filename": bn,
            "resourceType": content.get("resourceType"),
            "id": content.get("id"),
            "url": content.get("url"),
            "version": content.get("version"),
            "kind": content.get("kind"),
            "type": content.get("type"),
            "supplements": content.get("supplements"),
            "content": content.get("content"),
        }
        for k, v in content.items():
            if k not in entry and isinstance(v, str):
                entry[k] = v
        files.append(entry)
    return index


def update_package_index_file(package_dir: Path):
    """
    Generates new index file content and add it to the package content/replaces the old index file

    :param package_dir: Path to directory of the packages content
    """
    index = build_package_index(package_dir)
    with open(
        package_dir / "package" / ".index.json", mode="w+", encoding="utf-8"
    ) as idx_f:
        json.dump(index, idx_f, indent=2)


def _contained_in(dict_a, dict_b) -> bool:
    if not dict_a:
        return True
    elif not dict_b:
        return False
    return all(
        key in dict_b
        and (
            value.match(dict_b[key])
            if isinstance(value, re.Pattern)
            else dict_b[key] == value
        )
        for key, value in dict_a.items()
    )


@inject_logger
class FhirPackageManager(abc.ABC):
    """
    Manages a FHIR package cache and allows for the installation, iteration, etc. of the caches content. This is the
    base class for all package managers
    """

    _logger: Logger
    __cache: OrderedDict[Path, Resource]
    __cache_size: int = 10000

    def __init__(self, package_cache_dir: Path):
        self.__package_cache_dir = package_cache_dir
        self._index = defaultdict(dict)
        self.__cache = OrderedDict()

        if not self.__package_cache_dir.exists():
            raise Exception(f"No FHIR cache directory @ {self.__package_cache_dir}")

    def __add_to_cache(self, key: Path, res: Resource):
        if len(self.__cache) == self.__cache_size and key not in self.__cache:
            self.__cache.popitem()
        self.__cache[key] = res

    def cache_location(self) -> Path:
        """
        Returns the location of the fhir package cache of the FHIR project used by this instance

        :return: `Path` object of the location of the fhir package cache directory
        """
        return self.__package_cache_dir

    def _update_index(self):
        cache_path = self.cache_location()
        for package_path in cache_path.iterdir():
            if not package_path.is_dir():
                continue
            with open(
                package_path / "package" / "package.json", mode="r", encoding="utf-8"
            ) as f:
                package_info = json.load(f)
                name = package_info.get("name")
                name_entry = self._index[name]
                version = package_info.get("version")
                if version not in name_entry:
                    idx_path = package_path / "package" / ".index.json"
                    if not idx_path.exists() or idx_path.is_file():
                        update_package_index_file(package_path)
                    with open(
                        idx_path,
                        mode="r",
                        encoding="utf-8",
                    ) as idx_f:
                        name_entry[version] = (package_info, json.load(idx_f))

    def has_package(self, name: str, version: Optional[str]) -> bool:
        """
        Checks if the package identified by name and version is present in the cache

        :param name: Package name
        :param version: (Optional) package version
        :return: Boolean indicating presence of package
        """
        if version:
            return self._index.get(name, {}).get(version) is not None
        else:
            return self._index.get(name) is not None

    def iterate_cache(
        self,
        package_pattern: Optional[Mapping[str, Any]] = None,
        index_pattern: Optional[Mapping[str, Any]] = None,
        latest_only: bool = True,
        skip_on_fail: bool = False,
    ) -> Iterator[Resource]:
        """
        Iterates over entries of the FHIR projects cache. Results can be filtered on package and index entry level via
        patterns. The patterns structure should mirror their respective file content in the package: entries in the
        patterns are evaluated against the corresponding files content. If the value of a patterns entry is an instance
        of `re.Pattern` then regex matching will be performed against the respective entry of the content

        :param package_pattern: (Optional) pattern to select only packages with matching `package.json` file content
        :param index_pattern: (Optional) pattern to select only package content with matching entry in the `.index.json`
                              file
        :param latest_only: If `True` only content of the latest version of a package is considered
        :param skip_on_fail: IF `True` skips failed entry and continues iteration
        :return: Iterator of all selected resources in the cache
        """
        packages = filter(
            lambda t: _contained_in(package_pattern, t[0]),
            [
                package
                for entry in self._index.values()
                for _, package in (
                    sorted(entry.items(), key=lambda p: p[0], reverse=True)[:1]
                    if latest_only
                    else entry.items()
                )
            ],
        )
        for package_info, index in packages:
            cache_path = self.__package_cache_dir
            package_dir_name = (
                f"{package_info.get('name')}#{package_info.get('version')}"
            )
            for file_entry in index.get("files", []):
                if _contained_in(index_pattern, file_entry):
                    rel_file_path = Path(
                        package_dir_name, "package", file_entry.get("filename")
                    )
                    file_path = cache_path.joinpath(rel_file_path)
                    try:
                        if res := self.__cache.get(rel_file_path):
                            yield res
                            continue
                        json_data = load_json(file_path, fail=True)
                        if (
                            res_type := json_data.get("resourceType")
                        ) == "StructureDefinition":
                            res = IndexedStructureDefinition.validate_python(json_data)
                        else:
                            model_class = fhir.resources.get_fhir_model_class(res_type)
                            res = model_class.model_validate(json_data)
                        self.__add_to_cache(rel_file_path, res)
                        yield res
                    except Exception as exc:
                        msg = f"Failed to load data @ {file_path}"
                        if skip_on_fail:
                            self._logger.warning(f"{msg} => Skipping entry")
                            self._logger.debug("Details:", exc_info=exc)
                        else:
                            raise Exception(
                                f"Failed to load data @ {file_path}"
                            ) from exc

    def find(
        self,
        index_pattern: Mapping[str, Any],
        package_pattern: Optional[Mapping[str, Any]] = None,
        latest_only: bool = True,
    ) -> Optional[Resource]:
        """
        Attempts to find a matching resource in the package cache

        :param index_pattern: Pattern to select only package content with matching entry in the `.index.json` file
        :param package_pattern: (Optional) pattern to select only packages with matching `package.json` file content
        :param latest_only: If `True` only content of the latest version of a package is considered
        :return: First matching resource or `None` if there is no match
        """
        return next(
            self.iterate_cache(package_pattern, index_pattern, latest_only), None
        )

    @cachetools.cached(cache={}, key=_profile_cache_key)
    def dependents_of(
        self,
        profile: str,
        package_pattern: Optional[Mapping[str, Any]] = None,
        direct_only: bool = False,
        latest_only: bool = True,
    ) -> List[StructureDefinition]:
        """
        Searches for profiles that are based on the profile identified by the provided URL and are present in the
        packages manages by the manager instance

        :param profile: URL of the profile to find dependents of
        :param package_pattern: (Optional) pattern to select only packages with matching `package.json` file content
        :param direct_only: If 'True' only direct dependents are returned
        :param latest_only: If `True` only content of the latest version of a package is considered
        :return: List of dependent `StructureDefinition` instances
        """
        index_pattern = {
            "resourceType": "StructureDefinition",
            "baseDefinition": profile,
        }
        if direct_only:
            return [
                p
                for p in self.iterate_cache(package_pattern, index_pattern, latest_only)
            ]
        return [
            p1
            for p in self.iterate_cache(package_pattern, index_pattern, latest_only)
            for p1 in [p, *self.dependents_of(p.url, package_pattern, latest_only)]
        ]

    @cachetools.cached(cache={}, key=_profile_cache_key)
    def dependencies_of(
        self,
        profile: Union[str, StructureDefinition],
        package_pattern: Optional[Mapping[str, Any]] = None,
        latest_only: bool = True,
    ) -> List[StructureDefinition]:
        """
        Searches profiles on which the provided one is based on

        :param profile: URL of the profile or `StructureDefinition` instance to find dependencies of
        :param package_pattern: (Optional) pattern to select only packages with matching `package.json` file content
        :param latest_only: If `True` only content of the latest version of a package is considered
        :return: List of parent `StructureDefinition` instances
        """
        match profile:
            case str():
                index_pattern = {
                    "resourceType": "StructureDefinition",
                    "url": profile,
                }
                if struct_def := self.find(index_pattern, package_pattern, latest_only):
                    base_def = struct_def.baseDefinition
                else:
                    raise NotFoundError(f"Failed to find profile '{profile}' in index")
            case StructureDefinition():
                base_def = profile.baseDefinition
            case _:
                raise ValueError(
                    f"Unsupported type '{type(profile)}' for value of parameter 'profile'"
                )
        if base_def is None:
            # Base profile has been reached
            return []
        index_pattern = {
            "resourceType": "StructureDefinition",
            "url": base_def,
        }
        if struct_def := self.find(index_pattern, package_pattern, latest_only):
            return [
                struct_def,
                *self.dependencies_of(struct_def, package_pattern, latest_only),
            ]
        else:
            raise NotFoundError(f"Failed to find profile '{base_def}' in index")

    def install(self, *packages: str | tuple[str, str], inflate: bool = False):
        """
        Attempts to install all packages represented by the provided package names and (optional) versions

        :param packages: List containing list of package names or tuples of package name and version
        :param inflate: If 'True' the package cache will be inflated after packages are installed
        """
        ...

    def restore(self, inflate: bool = False):
        """
        Restores package content from `package.json` file

        :param inflate: If 'True' the package cache will be inflated after packages are installed
        """
        ...


@inject_logger
class FirelyPackageManager(FhirPackageManager):
    """
    Implementation of the `FhirPackageManager` class relying on the Firely Terminal to manage its package
    cache
    """

    _logger: Logger

    MIN_SUPPORTED_VERSION: str = "3.3.0"
    PUBLIC_FHIR_PACKAGE_SERVER_URL: str = "https://packages.fhir.org/"

    @classmethod
    def __handle_exception(
        cls,
        msg: str,
        cause: Exception,
        level: Literal["warning", "error", "exception"] = "exception",
    ):
        match cause:
            case CalledProcessError() as cpe:
                info = f"{msg}. Reason: {cpe.output.decode('utf-8')}"
            case _ as exc:
                info = f"{msg}. Reason: {str(exc)}"
        match level:
            case "warning":
                cls._logger.warning(info)
            case "error":
                cls._logger.warning(info, exc_info=cause)
            case "exception":
                raise Exception(info) from cause

    @contextmanager
    def __use_public_source(self):
        output = subprocess.check_output(["fhir", "source"]).decode("utf-8")
        prev_server_url = re.search(r"(?<=^Package server: )\S+", output).group(0)
        subprocess.check_output(["fhir", "source", self.PUBLIC_FHIR_PACKAGE_SERVER_URL])
        try:
            yield
        finally:
            subprocess.check_output(["fhir", "source", prev_server_url])

    def __init__(
        self,
        package_dir: Path,
        local: bool = False,
        fhir_spec: str = "R4",
        reinit: bool = False,
    ):
        if not shutil.which("fhir"):
            raise Exception("Tool 'firely.terminal' does not seem to be installed")

        self.__local = local
        self.__package_dir = package_dir
        self.__index = defaultdict(dict)

        version = re.match(
            r"(Firely Terminal\s+)(?P<version>\d+\.\d+.\d+)",
            subprocess.check_output(["fhir", "--version"]).decode("utf-8"),
        ).group("version")
        if version < self.MIN_SUPPORTED_VERSION:
            raise Exception(
                f"Installed 'firely.terminal' tool version is not supported [installed: '{version}', required: '>={self.MIN_SUPPORTED_VERSION}']"
            )

        try:
            with self.__use_public_source():
                if reinit and self.__package_dir.exists():
                    shutil.rmtree(self.__package_dir)
                self.__package_dir.mkdir(parents=True, exist_ok=True)
                exists = False
                if (
                    not (self.__package_dir / "package.json").exists()
                    or not (self.__package_dir / "fhirpkg.lock.json").exists()
                    or reinit
                ):
                    self._logger.debug(
                        f"Initializing FHIR project @ {self.__package_dir}"
                    )
                    subprocess.check_output(["fhir", "init"], cwd=self.__package_dir)
                else:
                    self._logger.debug(
                        f"FHIR project @ {self.__package_dir} already exists"
                    )
                    exists = True

                subprocess.check_output(
                    ["fhir", "cache", "use-local" if local else "use-global"],
                    cwd=self.__package_dir,
                )
                subprocess.check_output(
                    ["fhir", "spec", fhir_spec, "--project"], cwd=self.__package_dir
                )

                if exists:
                    subprocess.check_output(["fhir", "restore"], cwd=self.__package_dir)

                super().__init__(self.cache_location())
        except Exception as exc:
            self.__handle_exception(
                f"Failed to setup FHIR project @ {self.__package_dir}", exc
            )
        self._update_index()

    def cache_location(self) -> Path:
        """
        Returns the location of the fhir package cache of the FHIR project used by this instance

        :return: `Path` object of the location of the fhir package cache directory
        """
        return Path(
            subprocess.check_output(
                ["fhir", "cache", "location", "--path"], cwd=self.__package_dir
            )
            .decode("utf-8")
            .rstrip()
        )

    def install(self, *packages: str | tuple[str, str], inflate: bool = False):
        with self.__use_public_source():
            for p in packages:
                match p:
                    case (name, version):
                        name_and_version = f"{name}@{version}"
                    case _:
                        name_and_version = p
                try:
                    self._logger.info(f"Installing package {name_and_version}")
                    subprocess.check_output(
                        ["fhir", "install", name_and_version], cwd=self.__package_dir
                    )
                except Exception as exc:
                    self.__handle_exception(
                        f"Failed to install package {name_and_version}", exc
                    )
            if inflate:
                subprocess.check_output(
                    ["fhir", "inflate-cache"], cwd=self.__package_dir
                )
            self._update_index()

    def restore(self, inflate: bool = False):
        raise UnsupportedError("Method not yet implemented")


@inject_logger
class RepositoryPackageManager(FhirPackageManager):
    """
    Implementation of the `FhirPackageManager` class that uses a remote repository as its source for FHIR packages. It
    leverages the Firely Terminal to perform package inflation
    """

    _logger: Logger

    def __init__(
        self,
        package_dir: Path,
        repo_url: str,
        auth: Optional[AuthBase] = None,
        reinit: bool = False,
    ):
        if not shutil.which("fhir"):
            logging.warning(
                "Tool 'firely.terminal' was not found. Package inflation will not be available"
            )
            self.__can_inflate = False
        else:
            self.__can_inflate = True

        package_cache_dir = package_dir / ".fhir-package-cache"
        if reinit:
            shutil.rmtree(package_dir)
        package_cache_dir.mkdir(parents=True, exist_ok=True)

        self.__package_dir = package_dir
        self.__repo_url = repo_url
        self.__client = BaseClient(repo_url, auth)
        self.__inflated = set()
        self.__inflated_file_path = package_cache_dir / ".inflated"
        super().__init__(package_cache_dir)

    def inflate_cache(self, force: bool = False):
        if not force and not self.__inflated:
            if self.__inflated_file_path.exists():
                with self.__inflated_file_path.open(mode="r", encoding="utf-8") as f:
                    self.__inflated = set(json.load(f))

        packages = {
            f"{name}#{version}"
            for name, versions in self._index.items()
            for version in versions.keys()
        }
        if force or self.__inflated != packages:
            self._logger.info("Inflating package cache")
            subprocess.check_output(["fhir", "inflate-cache"], cwd=self.__package_dir)

            with self.__inflated_file_path.open(mode="w", encoding="utf-8") as f:
                self.__inflated = packages
                json.dump(list(packages), f)

    def _request_package(
        self,
        package_name: Optional[str] = None,
        package_path: Optional[str] = None,
        full_url: Optional[str] = None,
    ) -> ContextManager[Request]:
        """
        Overwrite if special handling is required
        """
        package_path = package_path if package_path else ""
        package_path = (
            f"{package_path}/{package_name}.tgz" if package_name else package_path
        )
        return self.__client.get(
            context_path=package_path if package_path else None,
            full_url=full_url if full_url else None,
            headers={
                "Accept": "*/*",
                "Accept-Encoding": "gzip, deflate, br",
            },
            stream=True,
        )

    def install(self, *packages: tuple[str, str], inflate: bool = False):
        if inflate and not self.__can_inflate:
            raise ValueError(
                "Package inflation is not possible due to missing tool 'firely.terminal'"
            )
        tmp_dir = self.cache_location() / ".tmp"
        tmp_dir.mkdir(exist_ok=True)
        try:
            for p in packages:
                match p:
                    case (name, version):
                        name_and_version = f"{name}-{version}"
                    case _:
                        raise UnsupportedError(
                            f"A package version has to be provided in this implementation"
                        )
                try:
                    self._logger.info(f"Installing package {name_and_version}")
                    with self._request_package(name_and_version) as response:
                        package_tgz = tmp_dir / "package.tgz"
                        package_tgz.touch(mode=0o666)
                        with package_tgz.open(mode="wb") as tgz_file:
                            for chunk in response.iter_content(chunk_size=128):
                                tgz_file.write(chunk)
                        tmp_package_dir = tmp_dir / f"{p[0]}#{p[1]}"
                        tmp_package_dir.mkdir(exist_ok=True)
                        with tarfile.open(package_tgz, mode="r:*") as tgz_file:
                            tgz_file.extractall(tmp_package_dir)
                        package_tgz.unlink(missing_ok=True)
                        pkg_info = load_json(
                            tmp_package_dir / "package" / "package.json"
                        )
                        name = pkg_info.get("name")
                        version = pkg_info.get("version")
                        package_dir = self.cache_location() / f"{name}#{version}"
                        shutil.copytree(tmp_package_dir, package_dir)
                        shutil.rmtree(tmp_package_dir)
                except Exception as exc:
                    raise Exception(
                        f"Failed to install package {name_and_version}"
                    ) from exc
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        self._update_index()
        if inflate:
            self.inflate_cache()

    def restore(self, inflate: bool = False):
        self._update_index()
        package_fp = self.__package_dir / "package.json"
        if not package_fp.exists():
            raise FileNotFoundError(
                f"Missing package file @ {package_fp} defining FHIR package dependencies"
            )
        package_info = load_json(package_fp, fail=True)
        packages = [(k, v) for k, v in package_info.get("dependencies", {}).items()]
        packages = list(filter(lambda p: not self.has_package(p[0], p[1]), packages))
        if packages:
            self._logger.info(
                f"Restoring (missing) package dependencies {', '.join(map(lambda t: t[0] + '@' + t[1], packages))}"
            )
            self.install(*packages, inflate=inflate)
        else:
            self._logger.info("All dependencies are already present")
            if inflate:
                self.inflate_cache()
        self._update_index()


class GitHubPackageManager(RepositoryPackageManager):
    """
    Variant of the `RepositoryPackageManager` class that uses `GitHub` repositories as its source
    """

    def __init__(
        self,
        package_dir: Path,
        org: str,
        repo: str,
        ref: Optional[str] = None,
        path: str = "package-tarballs",
        auth: Optional[AuthBase] = None,
        reinit: bool = False,
    ):
        super().__init__(
            package_dir,
            f"https://github.com/{org}/{repo}/contents/{path}",
            auth=auth,
            reinit=reinit,
        )
        self.__org = org
        self.__repo = repo
        self.__ref = ref
        self.__path = path
        self.__contents_client = BaseClient(
            f"https://api.github.com/repos/{org}/{repo}/contents", auth
        )

    @functools.cached_property
    def __package_files(
        self,
    ) -> Mapping[
        Annotated[str, "Package archive name"], Annotated[str, "Download URL"]
    ]:
        try:
            data = self.__contents_client.get(
                self.__path,
                headers={"Accept": "application/json"},
                query_params={"ref": self.__ref} if self.__ref else None,
            ).json()
            return {e["name"]: e["download_url"] for e in data}
        except Exception as exc:
            raise Exception(
                f"Failed to retrieve information about FHIR packages hosted in the repository "
                f"[repo='{self.__org}/{self.__repo}', ref={self.__ref}, path={self.__path}]",
            ) from exc

    def _request_package(self, package_name: str = None, *_) -> ContextManager[Request]:
        fuzzy_matches = list(
            filter(
                lambda e: e[0].startswith(package_name),
                [
                    (os.path.splitext(p)[0], l)
                    for (p, l) in self.__package_files.items()
                ],
            )
        )
        exact_match = next(
            filter(
                lambda e: e[0] == package_name,
                fuzzy_matches,
            ),
            None,
        )
        if exact_match:
            return super()._request_package(full_url=exact_match[1])
        else:
            closest_match = sorted(fuzzy_matches, reverse=True)[0]
            self._logger.debug(
                f"Failed to find exact match => Requesting closest match '{closest_match[0]}'"
            )
            return super()._request_package(full_url=closest_match[1])
