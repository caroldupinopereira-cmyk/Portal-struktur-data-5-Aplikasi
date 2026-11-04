"""Refresh edited sidebar helpers in an already running portal process."""
import importlib
from pathlib import Path
import sys


def refresh_sidebar_module():
    # Python keeps imported helpers in sys.modules between Streamlit reruns.
    # Reload only after an edit; leave sessions and application data untouched.
    module = sys.modules.get("portal.sidebar")
    if module is None:
        return
    modified = Path(module.__file__).stat().st_mtime_ns
    if getattr(module, "SOURCE_VERSION", None) != modified:
        importlib.reload(module)
