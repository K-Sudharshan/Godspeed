"""
AuditTrail AP — Top-level application entrypoint.
Exposes the FastAPI instance from main (backend.app.main) for buildpacks
detecting app:app default location.
"""
from main import app

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "0.0.0.0")
    uvicorn.run("app:app", host=host, port=port, reload=False)
