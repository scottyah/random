"""Tests for containerized/orchestrated operation.

These guard the failure modes that only show up under Docker or Kubernetes:
config arriving from read-only mounts, exit codes the Job controller reads,
and probe semantics.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from campscout.cli import build_parser, main
from campscout.config import load_config

PROJECT = Path(__file__).resolve().parent.parent


class TestConfigPaths(unittest.TestCase):
    """Config must be loadable from arbitrary paths, i.e. mounted volumes."""

    def test_campgrounds_path_is_overridable(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom = Path(tmp) / "campgrounds.yaml"
            custom.write_text(
                yaml.safe_dump(
                    {
                        "campgrounds": [
                            {"key": "mounted", "name": "Mounted Beach", "facility_id": "42"}
                        ]
                    }
                ),
                encoding="utf-8",
            )
            config = load_config(
                config_path=Path(tmp) / "nope.yaml", campgrounds_path=custom
            )
            self.assertEqual([c.key for c in config.campgrounds], ["mounted"])
            self.assertEqual(config.campground("mounted").facility_id, "42")

    def test_cli_exposes_both_path_flags(self):
        parser = build_parser()
        args = parser.parse_args(
            ["--config", "/etc/x/config.yaml", "--campgrounds", "/etc/x/cg.yaml", "status"]
        )
        self.assertEqual(str(args.config), "/etc/x/config.yaml")
        self.assertEqual(str(args.campgrounds), "/etc/x/cg.yaml")

    def test_env_vars_supply_paths(self):
        import os

        parser = build_parser  # rebuild after env is set, defaults bind at build time
        os.environ["CAMPSCOUT_CONFIG"] = "/env/config.yaml"
        os.environ["CAMPSCOUT_CAMPGROUNDS"] = "/env/cg.yaml"
        try:
            args = parser().parse_args(["status"])
            self.assertEqual(str(args.config), "/env/config.yaml")
            self.assertEqual(str(args.campgrounds), "/env/cg.yaml")
        finally:
            del os.environ["CAMPSCOUT_CONFIG"]
            del os.environ["CAMPSCOUT_CAMPGROUNDS"]

    def test_state_path_is_configurable_for_a_mounted_volume(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.yaml"
            cfg.write_text(
                yaml.safe_dump({"paths": {"state": "/var/lib/campscout/state.json"}}),
                encoding="utf-8",
            )
            config = load_config(config_path=cfg)
            self.assertEqual(str(config.state_path), "/var/lib/campscout/state.json")


class TestExitCodes(unittest.TestCase):
    """A Job controller only sees the exit code, so it has to be truthful."""

    def _run(self, argv: list[str], config_body: dict, campgrounds: dict) -> int:
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.yaml"
            cg = Path(tmp) / "campgrounds.yaml"
            config_body.setdefault("paths", {})["state"] = str(Path(tmp) / "state.json")
            cfg.write_text(yaml.safe_dump(config_body), encoding="utf-8")
            cg.write_text(yaml.safe_dump(campgrounds), encoding="utf-8")
            return main(["--config", str(cfg), "--campgrounds", str(cg), *argv])

    def test_scan_fails_loudly_when_no_facility_ids(self):
        # The most likely k8s misconfiguration: CHANGEME left in the ConfigMap.
        # This must NOT look like a successful "nothing available" run.
        code = self._run(
            ["scan", "--dry-run"],
            {"search": {"windows": [{"label": "w", "nights": 2, "weekdays": [4]}]}},
            {"campgrounds": [{"key": "x", "name": "X"}]},  # no facility_id
        )
        self.assertEqual(code, 1)

    def test_status_check_is_stale_when_never_run(self):
        code = self._run(
            ["status", "--check"],
            {},
            {"campgrounds": [{"key": "x", "name": "X", "facility_id": "1"}]},
        )
        self.assertEqual(code, 1)

    def test_status_check_ignores_missing_scheduler(self):
        """A healthy Deployment has no cron; --check must not fail on that."""
        import time

        from campscout.state import AlertState

        with tempfile.TemporaryDirectory() as tmp:
            state_path = Path(tmp) / "state.json"
            state = AlertState(state_path)
            state.record_run(ok=True, pairs_found=0, sites_checked=170, now=time.time())
            state.save()

            cfg = Path(tmp) / "config.yaml"
            cfg.write_text(
                yaml.safe_dump({"paths": {"state": str(state_path)}, "stale_after_hours": 3}),
                encoding="utf-8",
            )
            cg = Path(tmp) / "campgrounds.yaml"
            cg.write_text(
                yaml.safe_dump({"campgrounds": [{"key": "x", "name": "X", "facility_id": "1"}]}),
                encoding="utf-8",
            )
            # Plain status fails (nothing scheduled); --check passes (scans fresh).
            self.assertEqual(
                main(["--config", str(cfg), "--campgrounds", str(cg), "status", "--check"]), 0
            )
            self.assertEqual(
                main(["--config", str(cfg), "--campgrounds", str(cg), "status"]), 1
            )


class TestManifests(unittest.TestCase):
    def test_k8s_yaml_parses(self):
        docs = list(yaml.safe_load_all((PROJECT / "k8s.yaml").read_text(encoding="utf-8")))
        docs = [d for d in docs if d]
        kinds = [d["kind"] for d in docs]
        self.assertIn("CronJob", kinds)
        self.assertIn("PersistentVolumeClaim", kinds)
        self.assertIn("ConfigMap", kinds)
        self.assertIn("Secret", kinds)

    def test_embedded_configmap_yaml_is_valid_and_loadable(self):
        docs = [
            d
            for d in yaml.safe_load_all((PROJECT / "k8s.yaml").read_text(encoding="utf-8"))
            if d and d.get("kind") == "ConfigMap"
        ]
        data = docs[0]["data"]
        # The embedded documents must survive a real load, not just parse.
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / "config.yaml"
            cg = Path(tmp) / "campgrounds.yaml"
            cfg.write_text(data["config.yaml"], encoding="utf-8")
            cg.write_text(data["campgrounds.yaml"], encoding="utf-8")
            config = load_config(config_path=cfg, campgrounds_path=cg)

        keys = {c.key for c in config.campgrounds}
        self.assertEqual(keys, {"san_elijo", "south_carlsbad"})
        self.assertTrue(config.windows)
        self.assertEqual(str(config.state_path), "/var/lib/campscout/state.json")

    def test_configmap_state_path_matches_the_mounted_volume(self):
        """A mismatch here silently loses state on every run."""
        docs = [
            d
            for d in yaml.safe_load_all((PROJECT / "k8s.yaml").read_text(encoding="utf-8"))
            if d
        ]
        cm = next(d for d in docs if d["kind"] == "ConfigMap")
        cron = next(d for d in docs if d["kind"] == "CronJob")

        config_yaml = yaml.safe_load(cm["data"]["config.yaml"])
        state_path = config_yaml["paths"]["state"]

        container = cron["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]
        mounts = {m["name"]: m["mountPath"] for m in container["volumeMounts"]}
        self.assertTrue(
            state_path.startswith(mounts["state"]),
            f"state path {state_path} is not under the mounted volume {mounts['state']}",
        )

    def test_cronjob_is_hardened_and_non_overlapping(self):
        cron = next(
            d
            for d in yaml.safe_load_all((PROJECT / "k8s.yaml").read_text(encoding="utf-8"))
            if d and d.get("kind") == "CronJob"
        )
        spec = cron["spec"]
        # Concurrent runs would race the RWO state volume.
        self.assertEqual(spec["concurrencyPolicy"], "Forbid")

        pod = spec["jobTemplate"]["spec"]["template"]["spec"]
        self.assertTrue(pod["securityContext"]["runAsNonRoot"])
        container = pod["containers"][0]
        self.assertTrue(container["securityContext"]["readOnlyRootFilesystem"])
        self.assertFalse(container["securityContext"]["allowPrivilegeEscalation"])
        self.assertEqual(container["securityContext"]["capabilities"]["drop"], ["ALL"])
        # readOnlyRootFilesystem requires somewhere to write scratch files.
        self.assertIn("/tmp", [m["mountPath"] for m in container["volumeMounts"]])

    def test_dockerfile_runs_as_non_root(self):
        text = (PROJECT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn("USER 10001", text)
        self.assertIn("ca-certificates", text)  # all API traffic is HTTPS

    def test_dockerignore_excludes_secrets_and_state(self):
        text = (PROJECT / ".dockerignore").read_text(encoding="utf-8")
        for entry in ("config.yaml", "data/state.json", ".env"):
            self.assertIn(entry, text, f"{entry} must not be baked into the image")


if __name__ == "__main__":
    unittest.main(verbosity=2)
