"""Bug 修复提案存储与应用。"""

from app.fix.service import apply_proposal, build_file_change, enrich_changes
from app.fix.store import FixStore, get_fix_store

__all__ = [
    "FixStore",
    "get_fix_store",
    "apply_proposal",
    "build_file_change",
    "enrich_changes",
]
