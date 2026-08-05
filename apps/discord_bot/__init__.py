import sys
from pathlib import Path

# Bootstrapping sys.path for monorepo packages under packages/*
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

_packages_dir = _repo_root / "packages"
if _packages_dir.exists():
    for _pkg in _packages_dir.iterdir():
        if _pkg.is_dir() and str(_pkg) not in sys.path:
            sys.path.insert(0, str(_pkg))
