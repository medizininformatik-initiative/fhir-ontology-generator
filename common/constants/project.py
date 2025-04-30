import os.path


PROJECT_ROOT = os.path.join("/", *os.path.abspath(__file__).split(os.sep)[:-3])
GLOBAL_CONFIG_FILE = os.path.join(PROJECT_ROOT, "pyproject.toml")