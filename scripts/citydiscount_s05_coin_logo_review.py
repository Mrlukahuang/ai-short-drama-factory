#!/usr/bin/env python3
"""G4/R4.4: REAL old Omni s05 + local CityDiscount CD glyph on coin (REVIEW).

No new model calls or media uploads. Preserve historically real, SHA-pinned
clean-sign s05 footage. CD lettering is cropped from existing SHA-pinned OFFICIAL
logo endcard video, NOT independently verified original logo PNG.
The coin's manually interpolated movements are a visual PROOF, not verified
planar tracking or Owner brand approval. Never publish as final.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
from pathlib import Path

from PIL import Image, ImageFilter

W,H,FPS,N=360,640,24,120
CLEAN_SHA="7a4a7e5f261a641dd7035698a5aad3a9a331bf51a70c5ccd7565677a2694a652"
END_SHA="273516cacbc07d750fd0262de6897ddd3a879ed5e22fa58fd1f5a49e09c6b8c1"
OUTPUT="CityDiscount_s05_REAL_OMNI_CLEAN_SIGN_CD_COIN_LOCAL_REVIEW_NOT_FINAL.mp4"
# Native time, x, y, local CD glyph opacity. Not planar/optical tracking.
COIN_KEYS=((3.10,181,545,0.0),(3.25,190,541,.95),
           (3.60,189,551,1.),(4.20,190,554,1.),
           (4.29,184,552,.95),(4.37,191,501,.28),
           (4.44,192,470,.20),(4.53,189,459,.40),
           (4.65,185,450,.95),(4.80,188,445,1.),
           (5.00,188,445,1.))


def sha(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for blob in iter(lambda:f.read(1<<20),b""):
            h.update(blob)
    return h.hexdigest()


def canonical(path:Path,expected:str)->Path:
    path=path.absolute()
    if (path.suffix!=".mp4" or not path.is_file()
        or any(part.is_symlink() for part in (path,*path.parents))
        or sha(path)!=expected):
        raise ValueError("Only exact SHA-verified old video source is permitted")
    return path


def ffprobe(path:Path)->dict:
    return json.loads(subprocess.check_output(
        ["ffprobe","-v","error","-show_streams","-show_format","-of","json",str(path)],
        text=True))


def coin_position(t:float)->tuple[float,float,float]:
    if t<COIN_KEYS[0][0]:
        return 0.,0.,0.
    for a,b in zip(COIN_KEYS,COIN_KEYS[1:]):
        if a[0]<=t<=b[0]:
            k=(t-a[0])/(b[0]-a[0])
            return tuple(a[j]*(1-k)+b[j]*k for j in (1,2,3))
    return COIN_KEYS[-1][1:]


def official_glyph(endcard:Path)->Image.Image:
    # All visible glyph pixels come from the source-identical logo movie.
    raw=subprocess.check_output([
        "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
        "-ss","4.4","-i",str(endcard),"-frames:v","1",
        "-f","image2pipe","-vcodec","png","pipe:1"])
    video_card=Image.open(io.BytesIO(raw)).convert("RGB")
    if video_card.size!=(1080,1440):
        raise ValueError("Historic official endcard geometry changed")
    roi=video_card.crop((483,547,600,606))
    mask=Image.new("L",roi.size,0)
    for y in range(roi.height):
        for x in range(roi.width):
            r,g,b=roi.getpixel((x,y))
            if r<110 and g<135 and b<110 and g>=r+5:
                mask.putpixel((x,y),255)
    bbox=mask.getbbox()
    if not bbox:
        raise ValueError("No authentic CD logo strokes in endcard")
    alpha=mask.crop(bbox).filter(ImageFilter.GaussianBlur(.45))
    if alpha.width<50 or alpha.height<15:
        raise ValueError("Unexpected branded glyph geometry")
    glyph=Image.new("RGBA",alpha.size,(16,90,53,0))
    glyph.putalpha(alpha)
    return glyph


def render(s05:Path,endcard:Path,out:Path)->dict:
    s05=canonical(s05,CLEAN_SHA)
    endcard=canonical(endcard,END_SHA)
    video=ffprobe(s05)
    streams=[x for x in video["streams"] if x["codec_type"]=="video"]
    if (len(streams)!=1 or
        (streams[0]["width"],streams[0]["height"])!=(W,H) or
        streams[0].get("nb_frames")!="120" or
        not 4.95<=float(video["format"]["duration"])<=5.08):
        raise ValueError("Original sanitized REAL Omni s05 timing/size changed")
    out=out.absolute()
    if out.exists():
        raise FileExistsError("Never overwrite prior media review artifacts")
    out.mkdir(parents=True)
    glyph=official_glyph(endcard)
    source_bytes=subprocess.check_output([
        "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
        "-i",str(s05),"-f","rawvideo","-pix_fmt","rgb24","pipe:1"])
    framesize=W*H*3
    if len(source_bytes)!=N*framesize:
        raise ValueError("Exactly 120 source video frames required")
    movie=out/OUTPUT
    ff=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
        "-f","rawvideo","-pix_fmt","rgb24","-s","360x640","-r","24",
        "-i","pipe:0","-i",str(s05),"-map","0:v:0","-map","1:a:0?",
        "-frames:v","120","-c:v","libx264","-preset","veryfast",
        "-crf","18","-pix_fmt","yuv420p","-c:a","copy",
        "-movflags","+faststart",str(movie)]
    p=subprocess.Popen(ff,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for i in range(N):
            im=Image.frombytes("RGB",(W,H),source_bytes[i*framesize:(i+1)*framesize]).convert("RGBA")
            x,y,opacity=coin_position(i/FPS)
            if opacity>=.03:
                width=29
                height=max(8,round(width*glyph.height/glyph.width))
                tiny=glyph.resize((width,height),Image.Resampling.LANCZOS)
                tiny.putalpha(tiny.getchannel("A").point(
                    lambda a:round(a*opacity*.91)))
                im.alpha_composite(tiny,(round(x-width/2),round(y-height/2)))
            p.stdin.write(im.convert("RGB").tobytes())
        p.stdin.close()
        errors=p.stderr.read()
        if p.wait()!=0:
            raise RuntimeError("FFmpeg clip render failed: "+errors.decode()[-1500:])
    except BaseException:
        p.kill()
        p.wait()
        raise
    meta=ffprobe(movie)
    vs=[x for x in meta["streams"] if x["codec_type"]=="video"]
    audio=[x for x in meta["streams"] if x["codec_type"]=="audio"]
    if (len(vs)!=1 or len(audio)!=1 or
        (vs[0]["width"],vs[0]["height"])!=(W,H) or
        vs[0].get("codec_name")!="h264" or
        vs[0].get("nb_frames")!="120" or
        not 4.95<=float(meta["format"]["duration"])<=5.08):
        raise ValueError("Branded local real preview failed frame/audio contract")
    record={
        "schema":"g4-citydiscount-real-s05-coin-letter-review.v1",
        "source_clean_s05_sha256":CLEAN_SHA,
        "original_real_omni_s05_unchanged":True,
        "source_endcard_sha256":END_SHA,
        "lettering_source":"extracted dark-green CD glyph from original official VIDEO endcard, original Logo PNG NOT individually reviewed",
        "coin_geometry":"manually interpolated temporary keyframes, not planar/automatic tracking",
        "output_sha256":sha(movie),
        "frames":120,"seconds":float(meta["format"]["duration"]),
        "geometry":[W,H],
        "original_audio_copied":True,
        "new_model_calls":0,"new_image_external_transfers":0,
        "human_2_digs_qa_pass":False,
        "coin_final_owner_brand_qa_pass":False,
        "new_real_scene_generated":False,
        "full_60s_film_uses_this_new_coin_version":False,
        "publish_approved":False,"g4_exit":False,"g5_authorized":False
    }
    (out/"coin_review_receipt.json").write_text(
        json.dumps(record,ensure_ascii=False,indent=2,sort_keys=True)+"\n",
        encoding="utf-8")
    # Real decoded frames, not synthetic tests or source GIF.
    from PIL import ImageDraw
    samples=(3.25,3.75,4.25,4.45,4.75)
    board=Image.new("RGB",(W*len(samples),H+36),"#f5f0e6")
    draw=ImageDraw.Draw(board)
    for j,t in enumerate(samples):
        raw=subprocess.check_output(["ffmpeg","-v","error","-ss",str(t),
            "-i",str(movie),"-frames:v","1","-f","image2pipe","-vcodec","png","pipe:1"])
        frame=Image.open(io.BytesIO(raw)).convert("RGB")
        board.paste(frame,(j*W,0))
        draw.text((j*W+8,H+10),f"Actual s05 {t:.2f}s | CD local overlay",
                  fill="#24523d")
    board.save(out/"s05_real_coins_5_frames_review.png")
    return record


if __name__=="__main__":
    cli=argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--s05-clean",required=True,type=Path)
    cli.add_argument("--official-endcard",required=True,type=Path)
    cli.add_argument("--out",required=True,type=Path)
    args=cli.parse_args()
    r=render(args.s05_clean,args.official_endcard,args.out)
    print(json.dumps({k:r[k] for k in (
        "output_sha256","frames","seconds","new_model_calls","publish_approved")}))
