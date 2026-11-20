import subprocess
import sys

import pytest

# What a serving process imports: the HTTP app and the command line.
SERVING_MODULES = ["livraison_express.api.main", "livraison_express.cli"]


@pytest.mark.parametrize(
    ("package", "why"),
    [
        # Not installed in the serving image: importing it would stop the API from starting.
        ("mlflow", "an image without the train extra would fail to start"),
        # Installed everywhere, but only jobs reading the ERP need it (factory imports it late).
        ("psycopg", "the API would load a database driver it never uses"),
    ],
)
def test_serving_code_does_not_import(package, why):
    # A fresh interpreter: in this process, other tests may already have imported the package.
    code = (
        "import importlib, sys\n"
        f"for name in {SERVING_MODULES!r}:\n"
        "    importlib.import_module(name)\n"
        f"print('imported:', {package!r} in sys.modules)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert "imported: False" in result.stdout, f"serving code imports {package}: {why}"
