"""
Vercel serverless entry point.
Exposes the FastAPI app for Vercel's Python runtime.
"""

import sys
from pathlib import Path

# Ensure project root is in sys.path so 'src' package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.main import app  # noqa: E402
