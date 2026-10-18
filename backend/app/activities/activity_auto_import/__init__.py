"""
Scheduled auto import of activity files.

Each user can enable a schedule that scans their own folder,
``<FILES_DIR>/auto_import/<username>/``, and imports any new
.fit/.gpx/.tcx/.gz files into their account, the same way the
manual bulk import does.

Exports:
    - Utils: run_due_auto_imports, run_user_auto_import
"""

from .utils import run_due_auto_imports, run_user_auto_import

__all__ = [
    "run_due_auto_imports",
    "run_user_auto_import",
]
