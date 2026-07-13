from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_COMMIT = "e34482bc46a5efbab13bf15cd7f63da52cea612c"
PINNED_ACTION_RE = re.compile(
    r"^\s*(?:-\s+)?uses:\s+"
    r"(?P<action>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)"
    r"@(?P<sha>[0-9a-f]{40})"
    r"(?:\s+#\s+[^\r\n]+)?$"
)


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="ascii")


def test_ci_workflow_is_present_and_read_only() -> None:
    text = _workflow_text()

    assert "pull_request_target" not in text
    assert "permissions:\n  contents: read\n" in text
    assert "persist-credentials: false" in text
    assert "runs-on: ubuntu-24.04" in text
    assert "timeout-minutes:" in text
    assert "secrets." not in text
    assert "upload-artifact" not in text
    assert "cache:" not in text


def test_ci_workflow_uses_only_exactly_pinned_official_actions() -> None:
    uses_lines = [line for line in _workflow_text().splitlines() if "uses:" in line]
    assert uses_lines

    actions: set[str] = set()
    for line in uses_lines:
        match = PINNED_ACTION_RE.fullmatch(line)
        assert match is not None, f"action reference is not pinned to a full SHA: {line}"
        actions.add(match.group("action"))

    assert actions == {"actions/checkout", "actions/setup-python"}


def test_ci_workflow_covers_public_gates_and_determinism() -> None:
    text = _workflow_text()
    required_commands = [
        "python -m compileall -q src tests tools",
        "make check PYTHON=python",
        "make test PYTHON=python",
        "make demo PYTHON=python",
        "PYTHONHASHSEED=1",
        "PYTHONHASHSEED=104729",
        "cmp build/ci/bench-seed-1.json build/ci/bench-seed-104729.json",
        "cmp build/ci/demo-seed-1.json build/ci/demo-seed-104729.json",
        "make paper-check PYTHON=python",
        "make paper PYTHON=python",
    ]

    for command in required_commands:
        assert command in text


def test_ci_workflow_binds_release_replay_and_paper_hashes() -> None:
    text = _workflow_text()

    assert text.count(RELEASE_COMMIT) >= 4
    assert "replay_target:" in text
    assert "v0.1.0" in text
    assert "e0f8af62d0f267d22baa5bcefe6d5dda3a097ccc60de794b759fe03159923244" in text
    assert "60b13a0826ae7ad9ce34b4a2df06bff2cfcfa6dda8a915477c0cbb84e1a4a902" in text
    assert "7a467329544a5de883252335a311dc25458da0c5558280f72a6c17a33ae15ebe" in text
    assert "d8ee043ccbcb35331dc4e0b6a57fe94bbdec1893f9f175367c861d8f20474eab" in text
    assert "508386177cf942a45077439508c090f2507af2258b376f64a8a9a62542dbdf4c" in text
    assert "fc5a769a9599c3063f459d479365f88fb5cbd746cad2083b4d30d5906dd5930d" in text
    assert 'if [[ "$REPLAY_TARGET" == "v0.1.0" ]]' in text
