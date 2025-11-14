import os


POSTGRES_IMAGE: str = f"postgres:{os.environ.get('POSTGRES_VERSION', 'latest')}" + (
    f"-{os.environ['POSTGRES_BASE_IMAGE']}"
    if "POSTGRES_BASE_IMAGE" in os.environ
    else ""
)
