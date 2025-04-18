from typing import Annotated


import warnings
warnings.warn(f"Type annotations in {__name__} are deprecated. Use `pathlib.Path` instead")


PathStr = Annotated[str, "String representing a path on a file system"]

DirPathStr = Annotated[str, "String representing the path of a directory on a file system"]

FilePathStr = Annotated[str, "String representing the path of a file on a file system"]