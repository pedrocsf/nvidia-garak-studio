
from __future__ import annotations

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")

import uvicorn  # noqa: E402


if __name__ == "__main__":
    reload = "--no-reload" not in sys.argv
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=reload)
