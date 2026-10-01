import functools
import pickle
import shelve
from pathlib import Path
from typing import Callable, Any


def disk_cache(path: str):
    """
    Caches the output of the decorated function to disk using a shelve database (file system-persisted dictionary). The
    cache key is generated based on the function name and its arguments.

    :param path: Cache file location
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = pickle.dumps((func.__name__, args, kwargs)).hex()
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with shelve.open(path) as db:
                if key not in db:
                    db[key] = func(*args, **kwargs)
                return db[key]
        return wrapper
    return decorator


def disk_cache_method(path_gen: Callable[[Any], Path]):
    """
    Caches the output of the decorated function to disk using a shelve database (file system-persisted dictionary). The
    cache key is generated based on the method name and its arguments (including the callee object).

    :param path_gen: Generator for cache file location based on instance
    """
    def decorator(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwargs):
            key = pickle.dumps((method.__name__, args, kwargs)).hex()
            path = path_gen(self)
            path.parent.mkdir(parents=True, exist_ok=True)
            with shelve.open(path) as db:
                if key not in db:
                    db[key] = method(self, *args, **kwargs)
                return db[key]
        return wrapper
    return decorator