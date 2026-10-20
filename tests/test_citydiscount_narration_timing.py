"""Owner 12-line Mandarin timing with no online TTS or external model costs."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import render_citydiscount_narration_timing as voice


def test_owner_shot_voice_exact_original_lines():
    p = voice.verified_owner_script(ROOT / "config/pilots/citydiscount_first_promo_v1.json")
    assert p["storyline"]["title_zh"] == "把奥克兰的好折扣，挖到你身边"
    assert [s["shot_id"] for s in p["shots"]] == [
        f"s{i:02d}" for i in range(1, 13)
    ]
    assert [s["duration_seconds"] for s in p["shots"]] == [5] * 12
    assert [s["voiceover_zh"] for s in p["shots"]] == [
        "在奥克兰，想把日子过丰富，钱包却总得算一算。",
        "找折扣这件事，交给 CityDiscount。",
        "我们跑遍城市，寻找藏在日常里的好优惠。",
        "一篮新鲜，找找更划算的买法。",
        "一顿好吃，也值得替你多找一找。",
        "发现优惠，再把条件看清楚。",
        "连周末的小快乐，也一起找。",
        "东找一点，西找一点，再替你整理好。",
        "把城市各处的好折扣，带到你身边。",
        "该买的买，想吃的吃，周末也能出去走走。",
        "省下来的，留给下一份小幸福。",
        "CityDiscount，替你到处挖折扣，让生活多一点。",
    ]


@pytest.mark.parametrize("invalid", [
    ("revision", 2), ("project", "other")
])
def test_preflight_blocks_wrong_script(tmp_path, invalid):
    source = json.loads(
        (ROOT / "config/pilots/citydiscount_first_promo_v1.json").read_text("utf-8")
    )
    source[invalid[0]] = invalid[1]
    p = tmp_path / "pilot.json"
    p.write_text(json.dumps(source, ensure_ascii=False), "utf-8")
    with pytest.raises(ValueError, match="script"):
        voice.verified_owner_script(p)


def test_preflight_does_not_claim_premium_voice_or_paid_calls(tmp_path, monkeypatch):
    # Plain Python matrix does not install ffmpeg/espeak. Simulate binary
    # presence ONLY to reach early source SHA verification; actual FFmpeg
    # and all 12 WAVs run separately in the specialty workflow.
    monkeypatch.setattr(voice.shutil, "which", lambda p: "/usr/bin/true")
    local = tmp_path / "unverified.mp4"
    local.write_bytes(b"not a real source")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        voice.render(
            pilot=ROOT / "config/pilots/citydiscount_first_promo_v1.json",
            animatic=local, out=tmp_path / "never",
            expected_animatic_sha256="9e993dd0772ad4e2fb503fc7e35027b50c9e822f2d7eadc1d853896ba516ed09",
        )
    assert not (tmp_path / "never").exists()
