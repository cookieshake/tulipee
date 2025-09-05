import importlib
import logging
import pkgutil
from types import ModuleType
from typing import Iterable, List, Optional


log = logging.getLogger("tulipee.discovery")


def iter_submodules(package_name: str) -> Iterable[str]:
    try:
        pkg = importlib.import_module(package_name)
    except Exception as e:
        log.error("Failed to import package %s: %s", package_name, e)
        return []
    if not hasattr(pkg, "__path__"):
        # Not a package (single module); return itself
        return [package_name]
    results: List[str] = []
    for mod in pkgutil.iter_modules(pkg.__path__):
        results.append(f"{package_name}.{mod.name}")
    # Include the package itself so __init__-level handlers also register
    results.insert(0, package_name)
    return results


def import_all_handlers(package_name: str = "tulipee.handlers", modules: Optional[List[str]] = None) -> None:
    """Import all handler modules so their @route decorators register routes.

    - If modules is provided, import exactly those modules.
    - Otherwise, import the package itself and all immediate submodules.
    """
    module_names = modules if modules is not None else list(iter_submodules(package_name))
    for name in module_names:
        try:
            importlib.import_module(name)
            log.debug("Imported handler module: %s", name)
        except Exception as e:
            log.error("Failed to import handler module %s: %s", name, e)

