#!/usr/bin/env python3
"""Build both distribution paths and replay installed CLIs outside the checkout."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import venv
import zipfile


ROOT = Path(__file__).resolve().parents[1]
PROBE = """
import hashlib, json, pathlib, sys
import arcana
from jsonschema import Draft202012Validator
from arcana.schemas import SCHEMA_DIR, EXAMPLE_DIR, load_json, load_public_examples
from arcana.bench_runner import build_input_manifest
package = pathlib.Path(arcana.__file__).resolve().parent
assert package.is_relative_to(pathlib.Path(sys.prefix)), str(package)
assert SCHEMA_DIR.is_relative_to(package), str(SCHEMA_DIR)
assert EXAMPLE_DIR.is_relative_to(package), str(EXAMPLE_DIR)
resources = {}
for directory in (SCHEMA_DIR, EXAMPLE_DIR):
    for path in sorted(directory.iterdir()):
        if path.is_file():
            resources[path.relative_to(package / '_data').as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
for path in sorted(SCHEMA_DIR.glob('*.json')):
    Draft202012Validator.check_schema(load_json(path))
examples = load_public_examples()
assert examples
print(json.dumps({'package': str(package), 'resources': resources, 'examples': len(examples),
                  'manifest': [entry.to_mapping() for entry in build_input_manifest()]}, sort_keys=True))
"""


def run(command: list[str], cwd: Path, env: dict[str, str]) -> bytes:
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, timeout=240)
    if result.returncode:
        raise RuntimeError(
            f"package_gate_command_failed ({result.returncode}): {command!r}\n"
            + result.stdout.decode(errors="replace") + result.stderr.decode(errors="replace")
        )
    return result.stdout


def one_wheel(directory: Path) -> Path:
    wheels = sorted(directory.glob("*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"package_gate_wheel_count_invalid: {directory}: {len(wheels)}")
    return wheels[0]


def wheel_contents(path: Path) -> dict[str, bytes]:
    with zipfile.ZipFile(path) as archive:
        if len(archive.namelist()) != len(set(archive.namelist())):
            raise RuntimeError("package_gate_duplicate_wheel_member")
        return {name: archive.read(name) for name in archive.namelist()}


def main() -> int:
    env = {key: value for key, value in os.environ.items()
           if key not in {"PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"}}
    env.update(PYTHONNOUSERSITE="1", PYTHONDONTWRITEBYTECODE="1", PIP_NO_INPUT="1",
               PIP_DISABLE_PIP_VERSION_CHECK="1", PYTHONHASHSEED="1")
    source_env = {**env, "PYTHONPATH": str(ROOT / "src")}
    expected_resources = {
        path.relative_to(ROOT).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for directory in (ROOT / "schemas", ROOT / "examples")
        for path in sorted(directory.iterdir()) if path.is_file()
    }
    with tempfile.TemporaryDirectory(prefix="arcana-package-") as directory:
        scratch = Path(directory)
        outside = scratch / "unrelated-cwd"
        outside.mkdir()
        constraints = scratch / "constraints.txt"
        constraints.write_text("".join(sorted({
            f"{dist.metadata['Name']}=={dist.version}\n"
            for dist in importlib.metadata.distributions()
            if dist.metadata['Name'].lower().replace('_', '-') != "arcana-reference"
        })), encoding="utf-8")
        source_demo = run([sys.executable, "-m", "arcana.demo"], outside, source_env)
        source_report = outside / "source.json"
        run([sys.executable, "-m", "arcana.bench_runner", "--output", str(source_report)],
            outside, source_env)
        expected_report = source_report.read_bytes()
        # The default PEP 517 build builds an sdist, then a wheel FROM that sdist.
        run([sys.executable, "-m", "build", "--outdir", str(scratch / "roundtrip"), str(ROOT)],
            outside, env)
        run([sys.executable, "-m", "build", "--wheel", "--outdir", str(scratch / "direct"), str(ROOT)],
            outside, env)
        direct = one_wheel(scratch / "direct")
        roundtrip = one_wheel(scratch / "roundtrip")
        if wheel_contents(direct) != wheel_contents(roundtrip):
            raise RuntimeError("package_gate_sdist_wheel_content_mismatch")
        results = []
        for label, wheel in (("direct", direct), ("sdist-roundtrip", roundtrip)):
            install = scratch / f"venv-{label}"
            venv.EnvBuilder(with_pip=True).create(install)
            binary = install / ("Scripts" if os.name == "nt" else "bin")
            python = binary / ("python.exe" if os.name == "nt" else "python")
            installed_env = {**env, "PATH": str(binary) + os.pathsep + env.get("PATH", "")}
            run([str(python), "-I", "-m", "pip", "install", "--only-binary=:all:",
                 "--constraint", str(constraints), str(wheel)], outside, installed_env)
            run([str(python), "-I", "-m", "pip", "check"], outside, installed_env)
            probe = json.loads(run([str(python), "-I", "-c", PROBE], outside, installed_env))
            if probe["resources"] != expected_resources:
                raise RuntimeError("package_gate_resource_bytes_mismatch")
            if probe["manifest"] != json.loads(expected_report)["input_manifest"]:
                raise RuntimeError("package_gate_installed_source_manifest_mismatch")
            for seed in ("1", "104729"):
                seeded_env = {**installed_env, "PYTHONHASHSEED": seed}
                demo = binary / ("arcana-demo.exe" if os.name == "nt" else "arcana-demo")
                bench = binary / ("arcana-bench.exe" if os.name == "nt" else "arcana-bench")
                if run([str(demo)], outside, seeded_env) != source_demo:
                    raise RuntimeError("package_gate_demo_mismatch")
                output = outside / f"{label}-{seed}.json"
                run([str(bench), "--output", str(output)], outside, seeded_env)
                if output.read_bytes() != expected_report:
                    raise RuntimeError("package_gate_benchmark_mismatch")
                run([str(bench), "--verify", str(source_report)], outside, seeded_env)
                run([sys.executable, "-m", "arcana.bench_runner", "--verify", str(output)],
                    outside, source_env)
            numerical = Path(probe["package"]) / "_numerics.py"
            numerical.write_bytes(numerical.read_bytes() + b"\n# package gate tamper control\n")
            tampered = subprocess.run([str(bench), "--verify", str(source_report)],
                                     cwd=outside, env=installed_env, capture_output=True, timeout=30)
            if tampered.returncode != 2 or b"benchmark_report_source_manifest_mismatch" not in tampered.stderr:
                raise RuntimeError("package_gate_installed_tamper_not_rejected")
            results.append({"route": label, "status": "PASS", "examples": probe["examples"],
                            "installed_tamper_rejected": True,
                            "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()})
        wheel_metadata = {name: data.decode("utf-8")
                          for name, data in wheel_contents(direct).items()
                          if name.endswith(".dist-info/WHEEL")}
        report = {"status": "PASS", "python": sys.version,
                  "wheel_build_metadata": wheel_metadata,
                  "build_frontend_version": importlib.metadata.version("build"),
                  "benchmark_report_hash": json.loads(expected_report)["report_hash"],
                  "installations": results}
        destination = ROOT / "build" / "package-check.json"
        destination.parent.mkdir(exist_ok=True)
        destination.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="ascii")
        print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
