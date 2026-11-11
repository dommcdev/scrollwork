#!/usr/bin/env python3
"""Launcher isolation and mount-order regressions, without launching a desktop."""

import argparse
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "scrollwork_launcher", Path(__file__).resolve().parents[1] / "scripts/try.py"
)
launcher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(launcher)


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(
            prefix="scrollwork-launcher-", dir="/tmp/opencode"
        )
        self.root = Path(self.directory.name)
        self.profile = self.root / "profile"
        (self.profile / "state").mkdir(parents=True)
        self.host_runtime = self.root / "host-runtime"
        self.host_runtime.mkdir()
        (self.host_runtime / "wayland-test").touch()

    def tearDown(self):
        self.directory.cleanup()

    def invoke(self, smoke=False):
        with (
            patch.object(launcher, "BASE", self.root),
            patch.object(launcher, "PROFILE", self.profile),
            patch.object(launcher, "RUNTIME", self.root / "saved-runtime"),
            patch.object(launcher, "doctor"),
            patch.object(launcher, "prepare") as prepare,
            patch.dict(
                os.environ,
                {
                    "XDG_RUNTIME_DIR": str(self.host_runtime),
                    "WAYLAND_DISPLAY": "wayland-test",
                    "OPENAI_API_KEY": "not-a-real-key",
                    "OPENCODE_SERVER_PASSWORD": "not-a-real-password",
                },
            ),
            patch.object(
                launcher.subprocess,
                "run",
                return_value=subprocess.CompletedProcess([], 0),
            ) as run,
        ):
            launcher.outer(argparse.Namespace(smoke_test=smoke, size="1600x900"))
            return run.call_args, prepare.call_args

    def test_root_mount_precedes_private_proc(self):
        call, _ = self.invoke()
        command = call.args[0]
        self.assertLess(command.index("--dev-bind"), command.index("--proc"))
        self.assertIn("--unshare-pid", command)
        self.assertIn("--die-with-parent", command)

    def test_saved_runtime_is_used_and_temporary_build_tree_is_hidden(self):
        call, _ = self.invoke()
        command = call.args[0]
        self.assertIn(str(self.root / "saved-runtime"), command)
        self.assertIn(launcher.EMBEDDED_PREFIX, command)
        self.assertEqual(command[command.index("--tmpfs") + 1], "/tmp/opencode")
        self.assertIn("/usr/lib/mutter-51", command)

    def test_secrets_and_host_profile_are_not_inherited(self):
        call, _ = self.invoke()
        env = call.kwargs["env"]
        self.assertNotIn("OPENAI_API_KEY", env)
        self.assertNotIn("OPENCODE_SERVER_PASSWORD", env)
        self.assertNotIn("DBUS_SESSION_BUS_ADDRESS", env)
        self.assertEqual(env["HOME"], str(self.profile / "home"))
        self.assertEqual(env["GSETTINGS_BACKEND"], "keyfile")
        self.assertEqual(env["GSK_RENDERER"], "cairo")
        self.assertEqual(
            env["WAYLAND_DISPLAY"], str(self.host_runtime / "wayland-test")
        )
        self.assertNotEqual(env["XDG_RUNTIME_DIR"], str(self.host_runtime))

    def test_normal_launch_does_not_enable_test_probe(self):
        call, prepare = self.invoke()
        self.assertNotIn("--smoke-test", call.args[0])
        self.assertEqual(prepare.args, (False,))

    def test_smoke_launch_is_explicit(self):
        call, prepare = self.invoke(smoke=True)
        self.assertIn("--smoke-test", call.args[0])
        self.assertEqual(prepare.args, (True,))


if __name__ == "__main__":
    unittest.main()
