import os.path

GLOBAL_CONFIG_FILE = os.path.join("/", *os.path.abspath(__file__).split(os.sep)[:-3], "pyproject.toml")