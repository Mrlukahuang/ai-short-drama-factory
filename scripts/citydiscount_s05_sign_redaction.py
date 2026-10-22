#!/usr/bin/env python3
"""G4/R4.4: safe LOCAL review copy of REAL s05 Omni with false shop text erased.

Only stationary shop's inner needle-felt sign is obscured. The genuine actor,
coin/shovel, greenery, original audio and source MP4 remain unaltered. No
generated character, reference upload, new fee or release authorization.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import random
import subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageChops, ImageStat

ORIGINAL_SHA="4ed60c4e769ab36e21186733931e89c23d1dcbb776e3274389216a2bb742fc56"
OUTPUT="CityDiscount_s05_REAL_OMNI_BANNER_REDACTED_5s_NOT_FINAL.mp4"
W,H=360,640
BANNER_INNER=(133,196,227,236)

def digest(path:Path)->str:
    h=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for buf in iter(lambda:stream.read(1024*1024),b""):
            h.update(buf)
    return h.hexdigest()

def probe(path:Path)->dict:
    return json.loads(subprocess.check_output([
        "ffprobe","-v","error","-show_streams","-show_format",
        "-of","json",str(path)],text=True))

def check_source(path:Path)->None:
    path=Path(path).absolute()
    if (not path.is_file() or path.suffix!=".mp4" or
        any(x.is_symlink() for x in (path,*path.parents)) or
        digest(path)!=ORIGINAL_SHA):
        raise ValueError("Original s05 SHA or regular local MP4 mismatch")
    data=probe(path)
    video=[x for x in data["streams"] if x["codec_type"]=="video"]
    if (len(video)!=1 or (video[0]["width"],video[0]["height"])!=(W,H)
        or video[0].get("nb_frames")!="120"
        or not 5<=float(data["format"]["duration"])<=5.08):
        raise ValueError("Historic original s05 video dimensions/timing invalid")

def blank_felt_patch(out:Path)->None:
    canvas=Image.new("RGBA",(W,H))
    d=ImageDraw.Draw(canvas)
    # Original shop sign border is intentionally left in the picture.
    d.rounded_rectangle(BANNER_INNER,radius=4,fill=(211,181,144,255))
    rng=random.Random(180527)
    for _ in range(14):
        x,y=rng.randint(137,224),rng.randint(199,233)
        d.line(((x,y),(x+rng.choice((-1,1)),y+1)),
            fill=rng.choice(((234,211,177,8),(178,144,110,6),(249,235,209,9))),width=1)
    canvas.putalpha(canvas.getchannel("A").filter(ImageFilter.GaussianBlur(.75)))
    canvas.save(out)

def frame(path:Path,t:float)->Image.Image:
    raw=subprocess.check_output([
        "ffmpeg","-v","error","-ss",str(t),"-i",str(path),
        "-frames:v","1","-f","image2pipe","-vcodec","png","pipe:1"])
    return Image.open(io.BytesIO(raw)).convert("RGB")

def run(source:Path,out:Path)->dict:
    source=Path(source).absolute()
    check_source(source)
    out=Path(out).absolute()
    if out.exists():
        raise FileExistsError("Source-preserving new review output directory required")
    out.mkdir(parents=True,exist_ok=False)
    patch=out/"TEMP__BLANK_WOOL_SIGN.png"
    blank_felt_patch(patch)
    movie=out/OUTPUT
    try:
        subprocess.run([
            "ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
            "-i",str(source),"-loop","1","-framerate","24","-i",str(patch),
            "-filter_complex","[0:v][1:v]overlay=shortest=1:format=auto,format=yuv420p[v]",
            "-map","[v]","-map","0:a:0?","-frames:v","120",
            "-c:v","libx264","-preset","veryfast","-crf","18","-pix_fmt","yuv420p",
            "-c:a","copy","-movflags","+faststart",str(movie)
        ],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    finally:
        patch.unlink(missing_ok=True)
    media=probe(movie)
    vs=[x for x in media["streams"] if x["codec_type"]=="video"]
    aud=[x for x in media["streams"] if x["codec_type"]=="audio"]
    if (len(vs)!=1 or len(aud)!=1 or vs[0]["codec_name"]!="h264" or
        (vs[0]["width"],vs[0]["height"])!=(W,H) or
        vs[0].get("nb_frames")!="120" or
        not 4.95<=float(media["format"]["duration"])<=5.08):
        raise ValueError("Real footage review copy invalid codec/size/audio/timing")
    before,after=frame(source,2.75),frame(movie,2.75)
    def delta(region):
        return sum(ImageStat.Stat(ImageChops.difference(
            before.crop(region),after.crop(region))).mean)/3
    changed=delta(BANNER_INNER)
    actor_changed=delta((77,286,305,573))
    if changed<12 or actor_changed>9:
        raise ValueError("Required banner edit absent or original sheep drifted")
    comparison=Image.new("RGB",(W*2,H))
    comparison.paste(before,(0,0))
    comparison.paste(after,(W,0))
    comparison.save(out/"s05_BEFORE_AFTER_2_75s.jpg",quality=91)
    receipt={
        "schema":"g4-citydiscount-s05-unlicensed-sign-redaction.v1",
        "original_real_omni_video_sha256":ORIGINAL_SHA,
        "review_copy_sha256":digest(movie),
        "original_preserved_unchanged":True,
        "edit_region_native_360x640":list(BANNER_INNER),
        "edit":"blank felt inner placard covering unverified shop lettering only",
        "real_sheep_footage_retained":True,
        "review_video_width_height":[W,H],
        "review_video_frames":120,
        "review_video_duration_seconds":float(media["format"]["duration"]),
        "audio_is_original_media":True,
        "actor_region_mean_delta":round(actor_changed,3),
        "banner_region_mean_delta":round(changed,3),
        "new_ai_model_calls":0,
        "new_source_image_external_uploads":0,
        "unverified_merchant_sign_removed":True,
        "coin_exact_official_design_approved":False,
        "two_digs_owner_creative_review":"NOT_VERIFIED",
        "commercial_release_approved":False,
        "g4_exit":False,"g5_unfrozen":False
    }
    (out/"receipt.json").write_text(
        json.dumps(receipt,indent=2,ensure_ascii=False,sort_keys=True)+"\n",
        encoding="utf-8")
    return receipt

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    r=run(a.source,a.out)
    print(json.dumps({"original_sha":r["original_real_omni_video_sha256"],
                      "review_sha":r["review_copy_sha256"],
                      "frames":r["review_video_frames"],
                      "actor_delta":r["actor_region_mean_delta"],
                      "new_paid_calls":r["new_ai_model_calls"]}))
