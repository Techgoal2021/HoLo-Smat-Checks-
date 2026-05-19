import sys
from pathlib import Path

# Add backend directory to sys.path
root_path = Path(__file__).parent.parent
backend_path = root_path / "backend"
sys.path.insert(0, str(backend_path))

# Import the FastAPI app
from main import app
