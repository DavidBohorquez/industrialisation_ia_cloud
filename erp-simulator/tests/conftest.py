import sys
from pathlib import Path

# The Dockerfile copies the simulator's modules flat into /app (`from config import ...`):
# make them importable the same way here.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "erp_simulator"))
