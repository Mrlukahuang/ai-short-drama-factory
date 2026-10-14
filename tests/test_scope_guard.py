import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "scope_guard", Path(__file__).resolve().parents[1] / "scripts" / "scope_guard.py"
)
sg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sg)

GOOD_BODY = "Stage: G1\nReq: R1.1\nAMEND check: 是"


def test_frozen_path_blocked_without_label():
    errors = sg.check(["src/drama_factory/storage/txlab_v2.py"], GOOD_BODY, set())
    assert errors and "冻结路径" in errors[0]


def test_frozen_path_allowed_with_owner_label():
    assert sg.check(["src/drama_factory/jobs/tts_intents.py"], GOOD_BODY, {"amend-approved"}) == []


def test_normal_path_with_good_body_passes():
    assert sg.check(["src/drama_factory/providers/kling_video.py"], GOOD_BODY, set()) == []


def test_missing_stage_and_req_rejected():
    errors = sg.check(["README.md"], "What changed? stuff", set())
    assert len(errors) == 2


def test_template_placeholders_are_not_enough():
    errors = sg.check(["README.md"], "Stage: G\nReq: R\n", set())
    assert len(errors) == 2


def test_empty_body_skips_body_check_for_pushes():
    assert sg.check(["README.md"], "", set()) == []


def test_unfrozen_storage_files_still_editable():
    assert sg.frozen_hits(["src/drama_factory/storage/artifacts.py"]) == []


def test_governance_file_requires_owner_label():
    errors = sg.check(["AMEND.md"], GOOD_BODY, set())
    assert errors and "治理文件" in errors[0]
    assert sg.check(["docs/GUARDRAILS.md"], GOOD_BODY, {"amend-approved"}) == []


def test_handoff_files_are_not_governance():
    assert sg.check(["docs/handoff/CURRENT.md", "docs/handoff/LOG.md"], GOOD_BODY, set()) == []
