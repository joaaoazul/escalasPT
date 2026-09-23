"""
Vercel entrypoint: the whole FastAPI app as one Python function.

vercel.json rewrites every /api/* request here; the original path is kept,
so FastAPI routes it exactly as it would behind nginx. The code lives in
backend/, which is not a package on the import path, hence the insert.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.main import app  # noqa: E402,F401
