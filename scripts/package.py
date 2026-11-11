#!/usr/bin/env python3
"""Package only runtime files; never ship the private D-Bus evaluation bridge."""

from pathlib import Path
import subprocess
import tempfile
import zipfile

root = Path(__file__).resolve().parents[1]
destination = root / "dist/scrollwork@local.shell-extension.zip"
destination.parent.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(
    prefix="scrollwork-package-", dir="/tmp/opencode"
) as temporary:
    schemas = Path(temporary) / "schemas"
    schemas.mkdir()
    source = root / "schemas/org.gnome.shell.extensions.scrollwork.gschema.xml"
    (schemas / source.name).write_bytes(source.read_bytes())
    subprocess.run(["glib-compile-schemas", "--strict", str(schemas)], check=True)
    with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in [
            "extension.js",
            "layout.js",
            "settings.js",
            "rules.js",
            "appearance.js",
            "edges.js",
            "animation.js",
            "keybindings.js",
            "metadata.json",
            "LICENSE",
        ]:
            archive.write(root / name, name)
        for file in sorted(schemas.iterdir()):
            archive.write(file, f"schemas/{file.name}")
print(destination)
