import os
import sys

# Ensure repository root is on sys.path for Vercel Python serverless runtime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.main import app

# Vercel serverless functions look for `app` ASGI/WSGI callable
