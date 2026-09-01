"""Filesystem anchors that never depend on the caller's working directory.

`pnpm dev:ai` runs uvicorn from `apps/ai` while scripts and tests run from the
repository root. A relative store path therefore used to resolve to two
different files, and a corpus that forks by working directory is not a corpus.
"""

from pathlib import Path

_PACKAGE_ROOT = Path(__file__).resolve().parent.parent


def _ancestor_containing(marker: str) -> Path | None:
    return next((parent for parent in _PACKAGE_ROOT.parents if (parent / marker).exists()), None)


# The service owns its own data directory, so the anchor is the Python
# application, not whichever shell happened to start it.
APPLICATION_ROOT = _ancestor_containing("pyproject.toml") or _PACKAGE_ROOT
REPOSITORY_ROOT = _ancestor_containing("pnpm-workspace.yaml") or APPLICATION_ROOT
CONTRACTS_ROOT = REPOSITORY_ROOT / "contracts"


def resolve_application_path(configured: str) -> Path:
    """Anchor a configured relative path to the service that reads it."""
    path = Path(configured).expanduser()
    return path if path.is_absolute() else APPLICATION_ROOT / path
