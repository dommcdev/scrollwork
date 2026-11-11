#!/usr/bin/env python3
"""Run GJS settings-journal tests with process-local settings and temporary state."""

import os
from pathlib import Path
import subprocess
import tempfile

with tempfile.TemporaryDirectory(
    prefix="scrollwork-settings-", dir="/tmp/opencode"
) as root:
    env = dict(os.environ, GSETTINGS_BACKEND="memory", XDG_STATE_HOME=root)
    subprocess.run(
        ["gjs", "-m", str(Path(__file__).with_name("settings.test.js"))],
        env=env,
        check=True,
    )
