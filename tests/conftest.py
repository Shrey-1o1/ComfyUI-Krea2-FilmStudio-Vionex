from __future__ import annotations

from pathlib import Path
import importlib.util
import sys


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
COMFY_ROOT = Path(r"S:\AI\ComfyUI\ComfyUI")

for path in (COMFY_ROOT, PACKAGE_ROOT.parent):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

if "Krea2OneNode" not in sys.modules:
    spec = importlib.util.spec_from_file_location(
        "Krea2OneNode",
        PACKAGE_ROOT / "__init__.py",
        submodule_search_locations=[str(PACKAGE_ROOT)],
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load KREA 2 One Node package from {PACKAGE_ROOT}")
    package = importlib.util.module_from_spec(spec)
    sys.modules["Krea2OneNode"] = package
    spec.loader.exec_module(package)
