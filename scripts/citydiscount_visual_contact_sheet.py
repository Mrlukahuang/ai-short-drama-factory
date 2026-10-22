#!/usr/bin/env python3
"""FFmpeg-backed 12-shot contact-sheet and honest human review checklist.

Never asserts visual/character quality from a successful CI render. Contact
sheet derives from actual final encoded MP4 (rather than synthetic independent
source frames). Includes the real s02/s05 and all local XYZ world shots.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path
from PIL import Image,ImageDraw

SIZE=(270,360)
TIMES=tuple(2.5+5*i for i in range(12))


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for buf in iter(lambda:f.read(1024*1024),b""):
            h.update(buf)
    return h.hexdigest()


def collect(video:Path,receipt:Path,target:Path)->dict:
    if target.exists():raise FileExistsError("Cannot overwrite visual QC artifact")
    if not video.is_file() or video.suffix!=".mp4" or not receipt.is_file():
        raise ValueError("Actual MP4/receipt must exist")
    src=json.loads(receipt.read_text("utf-8"))
    if (sha(video)!=src.get("film_sha256") or src.get("shot_count")!=12 or
        src.get("resolution")!=[1080,1440] or
        not 59.9<=src.get("duration_seconds",0)<=60.2 or
        src.get("publish_approved") is not False):
        raise ValueError("Refuse detached or release-approved source")
    board=Image.new("RGB",(6*270,2*386),"#f3f0e7")
    drawer=ImageDraw.Draw(board)
    row=[]
    for idx,t in enumerate(TIMES):
        result=subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
            "-ss",str(t),"-i",str(video),"-frames:v","1",
            "-f","image2pipe","-vcodec","png","pipe:1"
        ],capture_output=True,check=True)
        frame=Image.open(io.BytesIO(result.stdout)).convert("RGB")
        frame=frame.resize(SIZE,Image.Resampling.LANCZOS)
        x=(idx%6)*270;y=(idx//6)*386
        board.paste(frame,(x,y))
        drawer.text((x+12,y+365),f"s{idx+1:02}  |  {t:04.1f} sec",
                    fill="#28554a")
        row.append({"shot_id":f"s{idx+1:02}","sample_sec":t})
    target.parent.mkdir(parents=True,exist_ok=True)
    board.save(target)
    review={
        "schema":"g4-citydiscount-rev5-visual-contact-sheet.v1",
        "sha_pinned_mp4":src["film_sha256"],
        "contact_sheet_sha256":sha(target),
        "sampled_real_output_frames":row,
        "actual_video_complete":True,
        "visual_quality_pass":None,
        "owner_character_design_pass":None,
        "camera_3d_realism_pass":None,
        "family_handoff_story_pass":None,
        "approved_for_release":False,
        "actual_ai_generated_lamb_motion_shots":src["existing_real_AI_lamb_shots"],
        "additional_paid_provider_calls":0,
        "visual_review_notes":"Diorama volume is procedurally projected; sheep uses locally drawn XYZ body and owner cropped face. No automatic aesthetic approvals."
    }
    (target.parent/"visual_review.json").write_text(
        json.dumps(review,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8")
    return review


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--video",type=Path,required=True)
    cli.add_argument("--receipt",type=Path,required=True)
    cli.add_argument("--out",type=Path,required=True)
    args=cli.parse_args()
    answer=collect(args.video,args.receipt,args.out)
    print(json.dumps({"contact_sheet_sha256":answer["contact_sheet_sha256"],
                      "visual_quality_pass":answer["visual_quality_pass"]}))
