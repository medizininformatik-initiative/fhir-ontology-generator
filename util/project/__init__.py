import os.path
from typing import Optional


class Project:
    name: str
    abs_path: str

    def __init__(self, path: str, name: Optional[str] = None):
        self.name = name if name is not None else os.path.basename(path)
        self.abs_path = os.path.abspath(path)
        os.makedirs(self.abs_path, exist_ok=True)

    @staticmethod
    def __create_parent(path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)

    def __truediv__(self, other: str) -> str:
        return os.path.join(self.abs_path, other)

    def input(self, *path: str) -> str:
        path = os.path.join(self / "input", *path)
        self.__create_parent(path)
        return path

    def output(self, *path: str) -> str:
        path = os.path.join(self / "output", *path)
        self.__create_parent(path)
        return path
