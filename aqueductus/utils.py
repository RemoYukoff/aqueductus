import importlib.util
from pathlib import Path
from types import ModuleType


def load_module(file: str) -> ModuleType | None:
    path = Path(file)

    if path.is_file() and path.suffix == ".py":
        module_name = path.stem
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    return None
