import subprocess
import sys

# What a serving process imports: the HTTP app and the command line.
SERVING_MODULES = ["livraison_express.api.main", "livraison_express.cli"]


def test_serving_code_does_not_import_mlflow():
    # A fresh interpreter: in this process, other tests may already have imported mlflow.
    code = (
        "import importlib, sys\n"
        f"for name in {SERVING_MODULES!r}:\n"
        "    importlib.import_module(name)\n"
        "print('mlflow imported:', 'mlflow' in sys.modules)\n"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    assert "mlflow imported: False" in result.stdout, (
        "serving code imports mlflow: an image without the train extra would fail to start"
    )
