import json
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import pydantic
from fhir.resources.R4B import get_fhir_model_class
from fhir_core.fhirabstractmodel import FHIRAbstractModel
from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

from dataportal_generator.common.log.functions import get_logger
from dataportal_generator.common.model.fhir.nav_structure_definition import (
    NavStructureDefinition,
)
from dataportal_generator.common.util.json import load_json

_logger = get_logger(__file__)


_INDEX_VERSION = 2


class PackageIndexFileEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    filename: str
    resourceType: str | None = Field(default=None)
    id: str | None = Field(default=None)
    url: str | None = Field(default=None)
    version: str | None = Field(default=None)
    kind: str | None = Field(default=None)
    type: str | None = Field(default=None)
    supplements: str | None = Field(default=None)
    content: str | None = Field(default=None)

    def __ge__(self, other: Any):
        for k, v in other.items():
            if getattr(self, k) != v:
                return False
        return True


def _str_or_none(v: Any) -> str | None:
    if isinstance(v, str):
        return v
    return None


def _build_package_index(package_dir: Path) -> tuple[int, list[PackageIndexFileEntry]]:
    """
    Build the content of an index file for the given package

    :param package_dir: Path to directory of the packages content
    :return: Tuple of index version and list of index file entries
    """
    files = []
    for file_path in package_dir.glob("**/[!.]*.json"):
        filename = str(file_path.relative_to(package_dir))
        if filename == "package.json" or filename.startswith("."):
            continue
        content = load_json(file_path, encoding=["utf-8", "utf-8-sig"], fail=True)
        entry = PackageIndexFileEntry(
            filename=filename,
            resourceType=content.get("resourceType"),
            id=content.get("id"),
            url=content.get("url"),
            version=content.get("version"),
            kind=_str_or_none(content.get("kind")),
            type=_str_or_none(content.get("type")),
            supplements=_str_or_none(content.get("supplements")),
            content=_str_or_none(content.get("content")),
        )
        files.append(entry)
    return 2, files


class FhirPackageMetaData(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    version: str
    dependencies: Mapping[str, str] = Field(default_factory=dict)
    author: str
    description: str | None = Field(default=None) # Ideally should be required as per the spec
    canonical: str | None = Field(default=None)
    url: str | None = Field(default=None)
    type: str | None = Field(default=None)
    jurisdiction: str | None = Field(default=None)
    languages: list[str] = Field(default_factory=list)
    fhirVersions: list[str] = Field(default_factory=list)

    @pydantic.field_validator("jurisdiction", mode="after")
    @classmethod
    def _validate_jurisdiction(cls, value: str) -> str:
        system, code = value.split("#", maxsplit=1)
        if not system or not code:
            raise TypeError("Value of field 'jurisdiction' adhere to pattern {system}#{code}")
        return value


class FhirPackage(FhirPackageMetaData):
    model_config = ConfigDict(frozen=True)

    _path: Path = PrivateAttr()
    _index_version: int
    _index_files: list[PackageIndexFileEntry] = PrivateAttr(default_factory=list)

    @classmethod
    def from_directory(cls, dir_path: Path, update_index_file: bool = False) -> "FhirPackage":
        """
        Construct an instance of this class from the content of the provided directory

        :param dir_path: ``pathlib.Path`` object pointing to the package directory, e.g. the directory containing the
                         `package.json` file
        :param update_index_file: If ``True`` the packages `.index.json` file will be regenerated
        :return: ``FhirPackage`` object
        """
        if not dir_path.is_dir():
            raise FileNotFoundError(dir_path)
        with (dir_path / "package.json").open(mode="rb") as fd:
            package = cls.model_validate_json(fd.read())
        package._path = dir_path
        package.update_package_index(only_if_missing=(not update_index_file))
        return package

    def update_package_index(self, only_if_missing: bool = True):
        """
        Generates new index file content and add it to the package content/replaces the old index file

        :param only_if_missing: If ``True`` (re)generate index file only if it is missing
        """
        index_file = self._path / ".index.json"
        if only_if_missing and index_file.is_file():
            # Check index version
            with index_file.open(mode="r", encoding="utf-8") as idx_f:
                content = json.load(idx_f)
                index_version = content.get("index-version")
                do_update_index = index_version != _INDEX_VERSION
        else:
            do_update_index = True
        if do_update_index:
            self._index_version, self._index_files = _build_package_index(self._path)
            with index_file.open(mode="w+", encoding="utf-8") as idx_f:
                json.dump(
                    {"index-version": self._index_version, "files": [e.model_dump() for e in self._index_files]},
                    idx_f,
                    indent=2,
                )
        else:
            with index_file.open(mode="r", encoding="utf-8") as idx_f:
                content = json.load(idx_f)
                self._index_version = content["index-version"]
                self._index_files = [PackageIndexFileEntry.model_validate(e) for e in content["files"]]

    def iter_files(self, **kwargs) -> Iterator[tuple[PackageIndexFileEntry, Path]]:
        """
        Iterates over the package content and returns the paths to all files whos index entry matches the provided
        keyword arguments

        :return: Iterator of matching index file entry and the file path
        """
        for file_entry in self._index_files:
            if file_entry >= kwargs:
                yield file_entry.model_copy(deep=True), Path(self._path, file_entry.filename)
            
    def iter_raw(self, **kwargs) -> Iterator[tuple[PackageIndexFileEntry , str]]:
        """
        Iterates over the package content and returns the raw content of all files whos index entry matches the provided
        keyword arguments

        :return: Iterator of matching index file entry and file content
        """
        for file_entry,  res_file_path in self.iter_files(**kwargs):
            with res_file_path.open(mode="r", encoding="utf-8") as fd:
                yield file_entry, fd.read()
        
    def iter(self, **kwargs) -> Iterator[tuple[PackageIndexFileEntry, FHIRAbstractModel]]:
        """
        Iterates over the package content and returns all FHIR Resources whos index entry matches the provided keyword
        arguments

        :return: Iterator of matching index file entry and content as ``FHIRAbstractModel`` objects
        """
        for file_entry, content in self.iter_raw(**kwargs):
            model_class = get_fhir_model_class(file_entry["resourceType"])
            yield file_entry, model_class.model_validate_json(content)
                    
    def resource(self, **kwargs) -> FHIRAbstractModel | None:
        """
        Searches for a FHIR Resource in this package. The provided keyword arguments are matched against each package
        files index file entry. The first match is returned

        :return: ``FHIRAbstractModel`` object or ``None`` if there was no match
        """
        if t := next(self.iter(**kwargs), None):
            return t[1]
        else:
            return None

    def struct_def(self, name: str | None, url: str | None) -> NavStructureDefinition | None:
        """
        Searches for a FHIR `StructureDefinition` in this package matching the provided parameters and returns it if it
        exists

        :param name: ``StructureDefinition.name`` value to match against
        :param url: ``StructureDefinition.url`` value to match against
        :return: ``NavStructureDefinition`` object or ``None`` if there was no match
        """
        pattern = None
        if name is not None:
            pattern = {"resourceType": "StructureDefinition", "name": name}
        if url is not None:
            pattern = {"resourceType": "StructureDefinition", "url": url}
        if pattern is None:
            raise ValueError("Either 'name' or 'url' has to be provided")
        for _, content in self.iter_raw(**pattern):
            return NavStructureDefinition.model_validate_json(content)
        return None

    @property
    def path(self) -> Path:
        return self._path