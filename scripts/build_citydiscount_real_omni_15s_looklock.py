#!/usr/bin/env python3
"""G4/R4.4: quality-reference cut from 2 EXISTING REAL original-lamb videos.

No model calls, media uploads, new generated sheep, new city, or new prices.
15 seconds = real s02 5s + locally REDACTED real s05 5s + existing official logo 5s.
Owner identity/camera/commercial approval remains pending.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

EXPECTED={
 "s02":"a8a25ba43e5e8659d9c5528d685c69e8e0f991b990a48bf77c5c2be4fcfef80c",
 "s05":"4ed60c4e769ab36e21186733931e89c23d1dcbb776e3274389216a2bb742fc56",
 "s12":"273516cacbc07d750fd0262de6897ddd3a879ed5e22fa58fd1f5a49e09c6b8c1",
}
CLEAN_S05_SHA="7a4a7e5f261a641dd7035698a5aad3a9a331bf51a70c5ccd7565677a2694a652"
OUTPUT="CityDiscount_REAL_OMNI_LAMB_CLEAN_S05_LOOK_LOCK_15s_NOT_FINAL.mp4"
NONSTRETCHED_FILTER=(
 "[0:v]split=2[original][back];"
 "[back]scale=1080:1920:flags=lanczos,crop=1080:1440:0:240,"
 "gblur=sigma=26[blur];"
 "[original]scale=810:1440:flags=lanczos[keep];"
 "[blur][keep]overlay=(W-w)/2:0,format=yuv420p,fps=24[v]"
)

def digest(file:Path)->str:
    h=hashlib.sha256()
    with Path(file).open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):
            h.update(b)
    return h.hexdigest()

def checked(path:Path,sha:str)->Path:
    path=Path(path).absolute()
    if (path.suffix!=".mp4" or not path.is_file() or
        any(f.is_symlink() for f in (path,*path.parents)) or digest(path)!=sha):
        raise ValueError("Canonical source MP4 missing, symlinked or SHA mismatch")
    return path

def ffprobe(src:Path)->dict:
    return json.loads(subprocess.check_output([
        "ffprobe","-v","error","-show_streams","-show_format",
        "-of","json",str(src)],text=True))

def invoke(cmd:list[str])->None:
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)

def render(s02:Path,s05_clean:Path,s12:Path,out:Path)->dict:
    sources={"s02":checked(s02,EXPECTED["s02"]),
             "s05":checked(s05_clean,CLEAN_S05_SHA),
             "s12":checked(s12,EXPECTED["s12"])}
    for sid,src in sources.items():
        data=ffprobe(src)
        vids=[v for v in data["streams"] if v["codec_type"]=="video"]
        size=(360,640) if sid!="s12" else (1080,1440)
        if (len(vids)!=1 or (vids[0]["width"],vids[0]["height"])!=size or
            not 4.95<=float(data["format"]["duration"])<=5.08):
            raise ValueError("Historical real shot geometry or duration incorrect")
    out=Path(out).absolute()
    if out.exists():
        raise FileExistsError("Refuse to overwrite existing review artifact")
    out.mkdir(parents=True,exist_ok=False)
    for index,sid in enumerate(("s02","s05","s12")):
        cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
             "-i",str(sources[sid]),"-t","5.000","-an"]
        if sid=="s12":
            cmd+=["-vf","fps=24,format=yuv420p"]
        else:
            cmd+=["-filter_complex",NONSTRETCHED_FILTER,"-map","[v]"]
        cmd+=["-r","24","-c:v","libx264","-preset","veryfast",
              "-crf","23","-pix_fmt","yuv420p",
              str(out/f"{index:02d}_{sid}.mp4")]
        invoke(cmd)
    (out/"concat.txt").write_text(
        "".join(f"file '{i:02d}_{sid}.mp4'\n" for i,sid in enumerate(
            ("s02","s05","s12"))),encoding="utf-8")
    movie=out/OUTPUT
    invoke(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
        "-f","concat","-safe","0","-i",str(out/"concat.txt"),
        "-f","lavfi","-t","15","-i","anullsrc=r=48000:cl=stereo",
        "-map","0:v:0","-map","1:a:0","-c:v","copy",
        "-c:a","aac","-b:a","96k","-t","15","-movflags",
        "+faststart",str(movie)])
    data=ffprobe(movie)
    v=[x for x in data["streams"] if x["codec_type"]=="video"]
    a=[x for x in data["streams"] if x["codec_type"]=="audio"]
    if (len(v)!=1 or len(a)!=1 or v[0]["codec_name"]!="h264" or
        a[0]["codec_name"]!="aac" or
        (v[0]["width"],v[0]["height"])!=(1080,1440) or
        not 14.95<=float(data["format"]["duration"])<=15.05):
        raise ValueError("Final 15 second sample not a real H264/AAC portrait MP4")
    receipt={
        "schema":"g4-citydiscount-real-omni-look-lock-15s.v1",
        "ordered_segments":["s02","s05","s12"],
        "historical_original_source_sha256":EXPECTED,
        "actual_movie_source_sha256":{"s02":EXPECTED["s02"],"s05":CLEAN_S05_SHA,"s12":EXPECTED["s12"]},
        "s05_hallucinated_shop_sign_locally_redacted":True,
        "s05_is_same_old_real_omni_not_new_generation":True,
        "s05_original_unedited_sha256":EXPECTED["s05"],
        "s05_two_digs_owner_approved":False,
        "s05_official_cd_coin_design_approved":False,
        "source_kinds":["EXISTING_REAL_OMNI_LAMB",
                        "EXISTING_REAL_OMNI_LAMB",
                        "EXISTING_2D_GLOBE_OWNER_EXACT_LOGO"],
        "original_real_shot_size":[360,640],
        "source_mascot_face_geometry_stretched":False,
        "fit_method":"sharp centered 810x1440, same source blurred background to 1080x1440",
        "output_size":[1080,1440],
        "output_duration_seconds":float(data["format"]["duration"]),
        "shot_count_for_this_sample":3,
        "actual_full_rev5_shots_completed":False,
        "new_real_model_shots_generated":0,
        "new_paid_model_calls":0,
        "approved_for_publication":False,
        "human_identity_style_qa":"NOT_VERIFIED",
        "owner_rights_for_new_source_uploads":"NOT_AUTHORIZED",
        "actual_prior_google_fee_usd":None,
        "audio":"silent technical reference; no rejected robotic TTS / unlicensed music",
        "closing_copy":"都市折扣🌟，您的省钱助手小羊薅薅。",
        "official_logo_source_sha":"19a6202331db9853d384ddabd30fbdf738f139fd8721638eed54fde193011651",
        "movie_sha256":digest(movie)
    }
    (out/"look_lock_receipt.json").write_text(
        json.dumps(receipt,ensure_ascii=False,sort_keys=True,indent=2)+"\n",
        encoding="utf-8")
    return receipt

def main()->None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--s02",type=Path,required=True)
    parser.add_argument("--s05-clean",type=Path,required=True,
                        help="SHA-pinned local redaction of the ORIGINAL real Omni s05; never original unreviewed source")
    parser.add_argument("--s12",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    x=parser.parse_args()
    record=render(x.s02,x.s05_clean,x.s12,x.out)
    print(json.dumps({"sha256":record["movie_sha256"],
                      "duration":record["output_duration_seconds"],
                      "new_paid_calls":0,"not_final":True}))
if __name__=="__main__":
    main()
