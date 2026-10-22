#!/usr/bin/env python3
"""G4/R4.4: 5s local-only 2D felt-globe to ORIGINAL Logo END-CARD preview.

This is NOT evidence of a genuine 3D globe, real sheep/world zoom animation,
completed rev5 episode, approved licensed audio, or publishing permission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render_citydiscount_3x4_priority_boards import owned_assets, font_family

TREATMENT = ROOT / "config/pilots/citydiscount_camera_treatment_rev5.json"
OLD_STORY = ROOT / "config/pilots/citydiscount_coin_hunt_1080x1440_v2.json"
WIDTH, HEIGHT, FPS, FRAMES = 1080, 1440, 24, 120
TAGLINE = "都市折扣🌟，您的省钱助手小羊薅薅。"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load() -> tuple[dict, Image.Image, str]:
    plan = json.loads(TREATMENT.read_text("utf-8"))
    story = json.loads(OLD_STORY.read_text("utf-8"))
    assert plan["creative_revision"] == 5 and plan["source_story_revision"] == 4
    assert story["revision"] == 4
    assert plan["output"] == {
        "width": WIDTH, "height": HEIGHT, "aspect_ratio": "3:4",
        "fps": FPS, "total_duration_ms": 60000,
        "shots": 12, "shot_duration_ms": 5000,
    }
    assert plan["endcard"]["closing_copy"] == TAGLINE
    assert plan["endcard"]["line1"] == "都市折扣🌟"
    assert plan["endcard"]["line2"] == "您的省钱助手小羊薅薅"
    assert plan["endcard"]["logo_full_reveal_ms"] == 56600
    assert plan["endcard"]["logo_hold_until_ms"] == 60000
    assert (plan["endcard"]["logo_hold_until_ms"]
            - plan["endcard"]["logo_full_reveal_ms"]) >= 3000
    assert (plan["no_new_paid_calls"] == 0 and
            plan["locked"]["publish_approved"] is False)
    assert not plan["real_camera_transition_success"]
    _, logo, logo_hash = owned_assets()  # verifies unchanged owner-provided PNGs
    assert logo_hash == story["brand_asset_requirements"]["logo"]["source_sha256"]
    assert plan["endcard"]["logo_unmodified_original"] is True
    assert plan["endcard"]["logo_source"] == "assets/citydiscount/v1/citydiscount_logo_v1.png"
    assert logo.mode in ("RGBA", "RGB")
    return plan, logo, logo_hash


def original_logo(original: Image.Image) -> Image.Image:
    source = original.copy().convert("RGBA")
    bb = source.getchannel("A").getbbox()
    if bb is None:
        raise ValueError("Owner source logo has no visible pixels")
    source = source.crop(bb)
    factor = min(850 / source.width, 290 / source.height)
    return source.resize(
        (max(1, round(source.width * factor)),
         max(1, round(source.height * factor))), Image.Resampling.LANCZOS
    )


def felt_globe(d: ImageDraw.ImageDraw, t: float) -> None:
    """Pure local illustrative 2D shape, never a purported 3D generation."""
    shrink = max(0.36, 1.0 - 0.55 * min(t / 1.6, 1))
    radius = int(338 * shrink)
    cy = int(560 - 80 * min(t / 1.6, 1))
    cx = 540
    box = (cx-radius, cy-radius, cx+radius, cy+radius)
    fade = max(0, min(1, (1.6-t) / .55))
    if fade <= 0:
        return
    sea = "#a7ccce"
    land = "#82a994"
    d.ellipse(box, fill=sea, outline="#e9f4e5", width=max(4, int(13*shrink)))
    # Curves move across the 2D globe to suggest a revolving felt sphere.
    for index in range(-3, 4):
        phase = ((t * 0.65 + index / 4.0) % 1)
        x = cx + int(math.cos((phase-.5)*math.pi)*radius*.7)
        a = max(18, int(radius * abs(math.sin((phase-.5)*math.pi))*.5))
        d.arc((x-a, cy-radius, x+a, cy+radius), 90, 270,
              fill="#d0e2d0", width=max(2, int(5*shrink)))
    for latitude in (-.45, 0, .45):
        y = cy + int(radius * latitude)
        chord = radius * math.sqrt(1-latitude*latitude)
        d.arc((cx-int(chord), y-int(radius*.18),
               cx+int(chord), y+int(radius*.18)), 0, 180,
              fill="#dfebe1", width=max(2, int(4*shrink)))
    # Abstract woolland islands inside the globe (not real cartographic claims).
    angle = t*2.5
    for j in range(6):
        a = angle + j*1.33
        dx = int(math.sin(a)*radius*.65)
        dy = int(math.cos(a*1.4)*radius*.45)
        r = max(9, int(radius*.12 * (.6+.4*math.cos(a)**2)))
        d.ellipse((cx+dx-r,cy+dy-r//2,cx+dx+r,cy+dy+r//2),fill=land)
    # Dotted wool felt stitch at the rim
    for n in range(32):
        a = 2*math.pi*n/32
        x = cx + int((radius-14*shrink)*math.sin(a))
        y = cy + int((radius-14*shrink)*math.cos(a))
        d.ellipse((x-2,y-2,x+2,y+2),fill="#edf2df")


def star_points(cx: int, cy: int, outer: int = 26, inner: int = 12):
    points = []
    for j in range(10):
        r = outer if j % 2 == 0 else inner
        angle = -math.pi/2 + j*math.pi/5
        points.append((cx + int(r*math.cos(angle)),
                       cy + int(r*math.sin(angle))))
    return points


def frame(t: float, logo: Image.Image, plan: dict) -> Image.Image:
    if not 0 <= t < 5:
        raise ValueError("5 second local visual sample only")
    image = Image.new("RGB", (WIDTH, HEIGHT), "#dce6d9")
    d = ImageDraw.Draw(image)
    d.rectangle((0,1050,WIDTH,HEIGHT), fill="#c5d4c6")
    d.ellipse((-350,-250,1430,900), fill="#ebf1e0")
    d.ellipse((-400,1150,1500,1760), fill="#bbcbb9")
    d.rounded_rectangle((76,150,1004,1310), radius=60,
                        outline="#f6f2dd", width=7)
    felt_globe(d,t)
    # Keep the EXACT brand source; simulate only a 2D dissolve, not a generative logo redraw.
    start, full = 1.05, 1.6
    opacity = max(0, min(1, (t-start)/(full-start)))
    if opacity > 0:
        src = original_logo(logo)
        mask = src.getchannel("A").point(lambda p: int(p*opacity))
        x, y = (WIDTH-src.width)//2, 430
        image.paste(src, (x,y), mask)
    if t >= full:
        d = ImageDraw.Draw(image)
        d.text((523,840), "都市折扣", anchor="mm",
               fill="#245648", font=font_family(76, bold=True))
        d.polygon(star_points(745,840,36,15),fill="#f9c757")
        d.text((540,957), "您的省钱助手小羊薅薅",anchor="mm",
               fill="#315b4b", font=font_family(50,bold=True))
        d.text((540,1130), "CityDiscount", anchor="mm",
               fill="#667d68", font=font_family(40))
    return image


def render(out: Path) -> dict:
    if out.exists():
        raise FileExistsError("Provide a fresh output directory")
    plan, source_logo, logo_hash = load()
    out.mkdir(parents=True, exist_ok=False)
    clip = out / "CityDiscount_rev5_felt_globe_into_official_logo_5s_PREVIS_NOT_FINAL.mp4"
    command = ["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
               "-f","rawvideo","-pixel_format","rgb24","-video_size","1080x1440",
               "-framerate","24","-i","pipe:0",
               "-f","lavfi","-t","5","-i","anullsrc=r=48000:cl=stereo",
               "-map","0:v:0","-map","1:a:0",
               "-t","5","-c:v","libx264","-preset","ultrafast","-crf","30",
               "-pix_fmt","yuv420p","-c:a","aac","-b:a","96k",str(clip)]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
    try:
        for n in range(FRAMES):
            process.stdin.write(frame(n/FPS, source_logo, plan).tobytes())
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("Offline FFmpeg failed to encode actual end-card")
    except BaseException:
        process.kill()
        process.wait()
        raise
    probe = json.loads(subprocess.check_output(
        ["ffprobe","-v","error","-show_format","-show_streams",
         "-of","json",str(clip)],text=True))
    if (not any(x.get("codec_type")=="video" and
                (x.get("width"),x.get("height"))==(WIDTH,HEIGHT) and
                x.get("codec_name")=="h264" for x in probe["streams"])
            or not any(x.get("codec_type")=="audio" and
                       x.get("codec_name")=="aac" for x in probe["streams"])
            or not 4.95 <= float(probe["format"]["duration"]) <= 5.10):
        raise ValueError("Not an actual 5s 1080x1440 technical MP4")
    receipt = {
        "schema":"g4-cd-rev5-globe-logo-local-previs.v1",
        "camera_treatment_sha256":sha(TREATMENT),
        "source_rev4_story_sha256":sha(OLD_STORY),
        "source_logo_sha256":logo_hash,
        "closing_copy":TAGLINE,
        "logo_full_reveal_at_second":1.6,
        "logo_hold_seconds":3.4,
        "source_logo_original_pixels_unchanged":True,
        "actual_video_sha256":sha(clip),
        "actual_video_seconds":float(probe["format"]["duration"]),
        "output_pixels":[WIDTH,HEIGHT],
        "type":"locally illustrated TWO-D globe dissolve; NOT generated 3D Earth",
        "genuine_city_to_street_zoom_verified":False,
        "genuine_city_to_globe_zoom_verified":False,
        "all_rev5_60s_footage_finished":False,
        "audio":"silent technical placeholder, no VO",
        "new_model_calls":0,
        "publish_approved":False,
        "g4_exited":False
    }
    (out/"receipt.json").write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8")
    return receipt


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    done=render(args.out)
    print(json.dumps({
        k:done[k] for k in ("actual_video_sha256",
                           "closing_copy","new_model_calls",
                           "all_rev5_60s_footage_finished")},ensure_ascii=False))


if __name__=="__main__":
    main()
