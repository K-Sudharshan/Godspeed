"""
AuditTrail AP — Top-level application entrypoint.
Exposes the FastAPI instance from backend.app.main for deployment platforms
and buildpacks detecting default root entrypoints (main:app).
"""
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from backend.app.main import app

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=False)
