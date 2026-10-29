"""i18n parity: no English fallbacks on the main journey (runs node)."""
import shutil
import subprocess

import pytest


@pytest.mark.skipif(not shutil.which("node"),
                    reason="node is required for the parity check")
def test_i18n_parity():
    proc = subprocess.run(
        ["node", "scripts/check_i18n_keys.js"],
        capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
