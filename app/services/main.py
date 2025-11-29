# python
# File: `app/services/__init__.py`
# (leave empty or include a harmless comment)
# Example content:
#    # package marker

# File: `app/services/main.py`
from importlib import import_module

def _load_app():
    """
    Import the real FastAPI app from `app.main`.
    Any import-time errors will surface when this module is imported,
    so you'll see full traceback when running the test import or uvicorn.
    """
    mod = import_module("app.main")
    return getattr(mod, "app")

# Expose the ASGI app object so uvicorn can import `app.services.main:app`
app = _load_app()