#!/usr/bin/env python3
"""One actual 60s rev5 INTERNAL moving storyboard from two pinned legacy MP4s.

Unlike final 3D AI animation, camera moves and missing shots here are explicitly
local 2D illustrations with the original SHA-checked character, never fake real
Google results. s02 and s05 are unchanged-footage extracts of #233 preview.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
import render_citydiscount_3x4_priority_boards as boards
import render_citydiscount_rev5_globe_logo_previs as endcard

W,H,FPS=540,720,12
SOURCE_REV4_SHA="e65d01356dcc977ab40c6cfea2ed479b812b8d16ffae6ccc41bfde8ce430288e"
SOURCE_END_SHA="273516cacbc07d750fd0262de6897ddd3a879ed5e22fa58fd1f5a49e09c6b8c1"
REAL_IDS=("s02","s05")
DRAWN_IDS=("s01","s03","s04","s06","s07","s08","s09","s10","s11")
TARGET="CityDiscount_rev5_60s_CINEMATIC_CAMERA_PREVIS_NOT_FINAL.mp4"


def sha(file:Path)->str:
    h=hashlib.sha256()
    with file.open("rb") as f:
        for b in iter(lambda:f.read(1048576),b""):
            h.update(b)
    return h.hexdigest()


def valid_input(file:Path, expected:str)->Path:
    p=Path(file).absolute()
    if (p.suffix!=".mp4" or not p.is_file()
        or any(q.is_symlink() for q in (p,*p.parents))
        or sha(p)!=expected):
        raise ValueError("Pinned prior actual MP4 source not available or SHA changed")
    return p


def call(cmd:list[str])->None:
    subprocess.run(cmd,check=True,stdout=subprocess.DEVNULL)


def mini_map()->Image.Image:
    im=Image.new("RGB",(W,H),"#c7ddcb"); d=ImageDraw.Draw(im)
    d.polygon([(0,45),(145,20),(235,130),(165,260),(0,265)],fill="#98cbd6")
    d.polygon([(390,0),(540,0),(540,170),(475,225)],fill="#91bed4")
    d.line([(0,262),(110,255),(235,135),(365,140),(540,230)],fill="#fcf2d8",width=40,joint="curve")
    d.line([(20,700),(130,560),(240,448),(350,320),(540,270)],fill="#f4e8d7",width=47,joint="curve")
    d.line([(75,0),(128,165),(215,320),(365,430),(540,488)],fill="#f5e7cd",width=39,joint="curve")
    d.line([(0,500),(195,500),(370,573),(540,632)],fill="#f4ebd9",width=38,joint="curve")
    for idx,(x,y) in enumerate([(56,315),(145,350),(320,179),(370,240),(400,510),
                                (78,545),(264,583),(445,660),(188,210),(306,665),(472,353)]):
        col=("#cfbda0","#a5c3ad","#d7bba8")[idx%3]
        d.rounded_rectangle((x-37,y-39,x+38,y+36),radius=9,fill="#6b9084")
        d.rounded_rectangle((x-42,y-51,x+30,y+23),radius=9,fill=col,outline="#fcf4d8",width=4)
        d.line((x-42,y-51,x-32,y-61),fill="#fdf1dd",width=4)
    d.ellipse((316,286,407,377),fill="#a2d4a0",outline="#faf3dc",width=8)
    d.ellipse((340,310,382,352),fill="#e4bf77")
    d.line((215,135,215,29),fill="#688e89",width=9)
    d.ellipse((194,69,237,89),fill="#a9a5ae")
    d.line((210,31,219,7),fill="#d9f0e5",width=4)
    d.arc((-80,155,300,332),180,350,fill="#789b9c",width=10)
    return im


def street(kind:str)->Image.Image:
    source={"home":"s02","supermarket":"s05","cafe":"s06",
            "shopping":"s07","family":"s02"}[kind]
    # Existing 2D felt illustration, not actual 3D geography or paid visual asset.
    im=boards.felt_background(source).convert("RGB").resize((W,H),Image.Resampling.LANCZOS)
    d=ImageDraw.Draw(im)
    if kind=="home":
        d.rounded_rectangle((85,400,475,636),radius=28,fill="#f5e7c9",outline="#b7a389",width=8)
        d.rectangle((260,434,330,532),fill="#9fbfc8")
        d.rounded_rectangle((130,500,250,580),radius=12,fill="#d6b794")
    elif kind in ("supermarket","shopping"):
        for x in (40,155,360):
            d.rounded_rectangle((x,375,x+117,550),radius=13,fill="#b19375")
            d.rectangle((x+20,410,x+97,432),fill="#e4d3ae")
        if kind=="shopping":
            for x in (87,225,424):
                d.rounded_rectangle((x,430,x+80,490),radius=9,fill="#f0d5ae")
    elif kind=="cafe":
        d.rounded_rectangle((60,350,300,475),radius=13,fill="#ddc4a1",outline="#ac886d",width=8)
        d.arc((75,285,225,390),195,330,fill="#f1ede0",width=9)
    return im


def family(im:Image.Image,t:float=0.0)->None:
    d=ImageDraw.Draw(im)
    positions=[(155,508,40,"#c49c80"),(335,515,40,"#b5a38d"),(260,554,30,"#d8ad92")]
    for x,y,r,col in positions:
        d.ellipse((x-r,y-r,x+r,y+r),fill="#e9d2b8")
        d.ellipse((x-r+6,y-r-9,x+r-6,y+r-14),fill=col)
        d.ellipse((x-r-8,y+24,x+r+8,y+110),fill=col)
    d.ellipse((230,610,308,648),fill="#dfb65a",outline="#fbe1a3",width=4)


def sheep_layer(source:Image.Image,size:int)->Image.Image:
    alpha=source.getchannel("A");bb=alpha.getbbox()
    sprite=source.crop(bb)
    s=size/max(1,sprite.height)
    return sprite.resize((max(1,int(sprite.width*s)),size),Image.Resampling.LANCZOS)


def paste_sheep(im:Image.Image,source:Image.Image,x:float,y:float,height:int=124)->None:
    sprite=sheep_layer(source,height)
    overlay=im.convert("RGBA")
    overlay.alpha_composite(sprite,(int(x-sprite.width/2),int(y-sprite.height/2)))
    im.paste(overlay.convert("RGB"))


def zoom(im:Image.Image,z:float,px:float=.64,py:float=.48)->Image.Image:
    # A 2D crop/pan simulation ONLY, not a physical Google camera travel.
    cropw=int(W/z);croph=int(H/z)
    x=max(0,min(W-cropw,int(px*W-cropw/2)))
    y=max(0,min(H-croph,int(py*H-croph/2)))
    return im.crop((x,y,x+cropw,y+croph)).resize((W,H),Image.Resampling.BICUBIC)


def ease(t:float)->float:
    t=max(0.0,min(1.0,t))
    return t*t*(3-2*t)


def blend(a:Image.Image,b:Image.Image,q:float)->Image.Image:
    return Image.blend(a,b,ease(q))


def label(im:Image.Image,sid:str,txt:str)->None:
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((10,12,530,62),radius=10,fill="#2b5248")
    d.text((18,20),f"{sid.upper()}  {txt}",
           font=boards.font_family(19,bold=True),fill="#fff9e8")
    d.rounded_rectangle((14,670,526,708),radius=8,fill="#294d46")
    d.text((24,678),"2D 动态分镜预演 · 非真实 AI 动画",
           font=boards.font_family(16),fill="#f9f4db")


def movie_frame(sid:str,t:float,context:dict)->Image.Image:
    base=context["map"]
    front=context["front"]
    if sid=="s03":
        # Starting aerial, dolly/zoom all the way toward SAME supermarket block.
        im=zoom(base,1.0+0.72*ease(t/5),px=.64,py=.49)
        paste_sheep(im,front,415-120*t/5,450-40*t/5,43)
        title="奥克兰俯瞰 · 镜头推向街区"
    elif sid=="s04":
        # Continue from exact previous map position and zoom ratio; dissolve into street.
        z=1.72+2.08*ease(t/4)
        city=zoom(base,z,px=.64,py=.49)
        ground=context["supermarket"].copy()
        paste_sheep(ground,front,160+120*ease(t/5),550,112)
        im=blend(city,ground,max(0,(t-3)/2))
        title="Zoom in · 从街区俯瞰到地面"
    elif sid=="s10":
        # Zoom OUT, shrinking the animated source-character across an anchored city.
        im=zoom(base,2.8-1.65*ease(t/5),px=.62,py=.55)
        paste_sheep(im,front,250+100*ease(t/5),515-110*ease(t/5),
                    int(128-80*ease(t/5)))
        title="镜头拉远 · 小羊穿越毛毡街区"
    elif sid=="s11":
        # 0-3.5 family handoff, then slowly ascend to the SAME aerial map.
        ground=context["family"].copy()
        family(ground,t)
        paste_sheep(ground,front,205+100*ease(t/3.5),570,108)
        city=zoom(base,2.15-1.25*ease(max(0,t-3.5)/1.5),px=.64,py=.51)
        im=blend(ground,city,max(0,(t-3.3)/1.7))
        title="交给家人 · Zoom out 拉远看整座城市"
    elif sid=="s01":
        im=context["home"].copy()
        family(im,t)
        title="奥克兰小家庭的心愿"
    elif sid=="s06":
        im=zoom(context["cafe"],1.2-.15*ease(t/5),px=.50,py=.55)
        paste_sheep(im,front,145+190*ease(t/5),566,110)
        title="咖啡街区 · 跟随小羊"
    elif sid=="s07":
        im=zoom(context["cafe"],1.12+.18*ease(t/5),px=.57,py=.56)
        paste_sheep(im,front,260,535+10*math.sin(t*4),111)
        d=ImageDraw.Draw(im)
        d.ellipse((345,585,391,628),fill="#ddba5b",outline="#f6d88b",width=3)
        title="咖啡角落挖金币 · 示意动作"
    elif sid=="s08":
        im=zoom(context["shopping"],1.2-.18*ease(t/5),px=.53,py=.52)
        paste_sheep(im,front,150+190*ease(t/5),560,112)
        title="购物街 · 追随小羊穿街"
    elif sid=="s09":
        im=zoom(context["shopping"],1.34-.19*ease(t/5),px=.55,py=.55)
        paste_sheep(im,front,285+35*ease(t/5),567,111)
        d=ImageDraw.Draw(im)
        d.ellipse((370,596,405,627),fill="#e0bb54",outline="#fbe0a2",width=3)
        title="第三枚金币 · 慢慢拉远"
    else:
        raise ValueError("Unexpected storyboard ID")
    label(im,sid,title)
    return im


def encode_drawn(sid:str,target:Path,context:dict)->None:
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
         "-f","rawvideo","-pixel_format","rgb24",
         "-video_size",f"{W}x{H}","-framerate",str(FPS),
         "-i","pipe:0","-vf","scale=1080:1440:flags=lanczos,fps=24",
         "-an","-t","5","-r","24","-c:v","libx264",
         "-preset","ultrafast","-crf","30","-pix_fmt","yuv420p",str(target)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL)
    try:
        for n in range(FPS*5):
            proc.stdin.write(movie_frame(sid,n/FPS,context).tobytes())
        proc.stdin.close()
        if proc.wait()!=0:
            raise RuntimeError("FFmpeg rendering of local animated storyboard failed")
    except BaseException:
        proc.kill();proc.wait();raise


def extract(source:Path,target:Path,start:float=0.0)->None:
    call(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
          "-ss",str(start),"-i",str(source),"-t","5","-an",
          "-vf","fps=24,format=yuv420p",
          "-r","24","-c:v","libx264","-preset","ultrafast","-crf","30",str(target)])


def scratch_audio(target:Path)->None:
    """Locally synthesized *TEMP* music/SFX guide. No vendor audio or licensed samples."""
    sr=24000
    notes=(262,330,392,330,294,349,440,349)
    with wave.open(str(target),"wb") as out:
        out.setnchannels(1);out.setsampwidth(2);out.setframerate(sr)
        for second in range(60):
            samples=bytearray()
            for j in range(sr):
                t=second+j/sr
                beat=t*1.75;phase=beat%1
                hz=notes[int(beat//2)%len(notes)]
                env=math.exp(-5*phase)
                music=0.10*env*(math.sin(2*math.pi*hz*t)+.24*math.sin(2*math.pi*2*hz*t))
                pulse=.10*math.exp(-38*phase)*math.sin(2*math.pi*90*t)
                coin=0.0
                for cue in (23.3,33.3,43.3,56.6):
                    u=t-cue
                    if 0<=u<.43:
                        coin+=.13*math.exp(-8*u)*math.sin(2*math.pi*(900-150*u)*u)
                v=max(-1,min(1,music+pulse+coin))
                samples.extend(struct.pack("<h",int(v*32767)))
            out.writeframes(bytes(samples))


def make_cut(*,rev4:Path,end:Path,out:Path)->dict:
    rev4=valid_input(rev4,SOURCE_REV4_SHA)
    end=valid_input(end,SOURCE_END_SHA)
    plan,logo,logo_hash=endcard.load()
    assert plan["endcard"]["closing_copy"]==endcard.TAGLINE
    assert (plan["output"]["total_duration_ms"],plan["output"]["shots"])==(60000,12)
    if out.exists():
        raise FileExistsError("Refuse to overwrite any prior review cut")
    _,roles_logo,_=boards.owned_assets()
    roles,_,_=boards.owned_assets()
    front=roles["front"].convert("RGBA")
    out.mkdir(parents=True,exist_ok=False)
    seg=out/"segments";seg.mkdir()
    context={"map":mini_map(),"front":front}
    for kind in ("home","supermarket","cafe","shopping","family"):
        context[kind]=street(kind)
    provenance=[]
    for i in range(1,13):
        sid=f"s{i:02}"
        target=seg/(sid+".mp4")
        if sid in REAL_IDS:
            extract(rev4,target,start=(i-1)*5)
            kind="EXISTING_REAL_OMNI_CHARACTER_MP4_FROM_SHA_PINNED_REV4"
        elif sid=="s12":
            extract(end,target)
            kind="EXISTING_2D_FELT_GLOBE_TO_SOURCE_LOGO_ENDCARD"
        else:
            encode_drawn(sid,target,context)
            kind="LOCAL_2D_CAMERA_MOVE_NOT_AI_FOOTAGE"
        provenance.append({"shot_id":sid,"kind":kind,"segment_sha256":sha(target),
                           "genuine_new_camera_dolly_verified":False})
    concat=seg/"concat.txt"
    concat.write_text("".join(f"file 's{i:02}.mp4'\n" for i in range(1,13)))
    audio=out/"temporary-original-music-sfx-guide.wav"
    scratch_audio(audio)
    film=out/TARGET
    call(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
          "-f","concat","-safe","0","-i",str(concat),"-i",str(audio),
          "-map","0:v:0","-map","1:a:0","-t","60",
          "-c:v","copy","-c:a","aac","-b:a","96k","-movflags","+faststart",str(film)])
    probe=json.loads(subprocess.check_output([
        "ffprobe","-v","error","-show_streams","-show_format","-of","json",str(film)],
        text=True))
    duration=float(probe["format"]["duration"])
    video=[x for x in probe["streams"] if x.get("codec_type")=="video"]
    sound=[x for x in probe["streams"] if x.get("codec_type")=="audio"]
    if (len(video)!=1 or (video[0].get("width"),video[0].get("height"))!=(1080,1440)
        or video[0].get("codec_name")!="h264"
        or len(sound)!=1 or sound[0].get("codec_name")!="aac"
        or not 59.9<=duration<=60.2):
        raise ValueError("Rev5 output is not real 60s portrait H264/AAC")
    receipt={
        "schema":"g4-citydiscount-rev5-moving-camera-60s-previs.v1",
        "film_sha256":sha(film),"duration_seconds":duration,
        "resolution":[1080,1440],"shot_count":12,"frame_rate_target":24,
        "camera_treatment_rev5_sha256":sha(endcard.TREATMENT),
        "reused_rev4_mp4_sha256":SOURCE_REV4_SHA,
        "reused_rev5_endcard_mp4_sha256":SOURCE_END_SHA,
        "source_logo_sha256":logo_hash,
        "closing_copy":endcard.TAGLINE,
        "existing_real_AI_lamb_shots":["s02","s05"],
        "historical_city_plate_rev4_unused_in_this_2d_aerial_treatment":True,
        "scene_camera_2d_animated":["s03","s04","s06","s07","s08","s09","s10","s11"],
        "genuine_aerial_to_street_3D_camera_pass":False,
        "genuine_sheep_travel_world_zoom_pass":False,
        "true_complete_12shot_AI_film":False,
        "original_unlicensed_audio_source":False,
        "audio":"locally synthesized temporary original notes + placeholder dig/coin beat, NO natural human Chinese voice",
        "no_new_paid_model_calls":True,"vendor_previous_fee_usd":None,
        "human_content_QA":"not_run","publish_approved":False,"g4_exit":False,
        "g5_authorized":False,"release":"BLOCKED_TECHNICAL_CAMERA_PREVIS_ONLY",
        "provenance":provenance
    }
    (out/"receipt.json").write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    return receipt


def main()->None:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--rev4",type=Path,required=True)
    p.add_argument("--end",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=make_cut(rev4=a.rev4,end=a.end,out=a.out)
    print(json.dumps({k:result[k] for k in
           ("film_sha256","duration_seconds","closing_copy",
            "existing_real_AI_lamb_shots","true_complete_12shot_AI_film")},
           ensure_ascii=False))


if __name__=="__main__":
    main()
