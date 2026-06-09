from __future__ import annotations

import json
import os
import subprocess
import sys
from io import StringIO
from pathlib import Path

from arcana.demo import CERTIFICATE_ARTIFACT_LABEL, CONTEXT_ARTIFACT_LABEL, main
from arcana.errors import ReasonCode, SchemaVersion
from arcana.schemas import validate_document


ROOT = Path(__file__).resolve().parents[1]


def test_demo_cli_main_emits_valid_json_artifacts() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(["--scenario", "synthetic_prompt_injection"], stdout=stdout, stderr=stderr)

    assert exit_code == 0
    assert stderr.getvalue() == ""
    payload = json.loads(stdout.getvalue())
    context_document = payload["artifacts"][CONTEXT_ARTIFACT_LABEL]
    certificate_document = payload["artifacts"][CERTIFICATE_ARTIFACT_LABEL]
    validate_document(context_document, SchemaVersion.CONTEXT_V02)
    validate_document(certificate_document, SchemaVersion.CERTIFICATE_V02)
    assert certificate_document["calibration_profile"]["certification_status"] == "non_certifiable"


def test_demo_cli_rejects_unsupported_scenario_with_reason_code() -> None:
    stdout = StringIO()
    stderr = StringIO()

    exit_code = main(["--scenario", "unsupported"], stdout=stdout, stderr=stderr)

    assert exit_code == 2
    assert stdout.getvalue() == ""
    payload = json.loads(stderr.getvalue())
    assert payload["error"]["reason_code"] == ReasonCode.DENY_MODEL_INPUT_INVALID.value
    assert payload["error"]["issue_code"] == "demo_scenario_unsupported"


def test_python_module_demo_entrypoint_runs() -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")

    completed = subprocess.run(
        [sys.executable, "-m", "arcana.demo", "--scenario", "synthetic_prompt_injection"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert CONTEXT_ARTIFACT_LABEL in payload["artifacts"]
    assert CERTIFICATE_ARTIFACT_LABEL in payload["artifacts"]
