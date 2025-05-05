from pathlib import Path


PROJECT_ROOT = Path(*Path(__file__).resolve().parts[:-3])
GLOBAL_CONFIG_FILE = PROJECT_ROOT / "pyproject.toml"