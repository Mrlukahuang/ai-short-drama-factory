"""CityDiscount Owner-script 60s offline branded ANIMATIC, never publish-ready.

Only source footage s03 was genuinely video-model generated. All other shots
use repo-original PNG mascot/logo as LOCAL still composites with subtle motion.
No model calls, no transmitted images, no synthesized spoken narration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets/citydiscount/v1"
PILOT = ROOT / "config/pilots/citydiscount_first_promo_v1.json"
CITY_PLATE_SHA256 = "b718e6b0a6e5a64db66d74e6b1364326d16671823fca12935e8a3667b101af3f"
W, H = 360, 640
PALETTE = [
    ("#f7ecd9", "#d1ae88"), ("#f5e7cb", "#b5a28a"),
    ("#cae1e2", "#93bec1"), ("#dbe9ce", "#9cba92"),
    ("#e9e2d1", "#b9a688"), ("#f2e6da", "#cca58c"),
    ("#d5e7eb", "#a4c6d2"), ("#e7e0c7", "#bda789"),
    ("#d4e7d6", "#9bbd9d"), ("#e8e3d2", "#b8b9a4"),
    ("#ede2cd", "#afc2a8"), ("#d8e9de", "#a7c2b5"),
]
VIEW_BY_SHOT = {
    2: "happy", 3: "sparkle", 4: "side", 5: "thumbsup",
    6: "wink", 7: "jump", 8: "front", 9: "three_quarter",
    11: "happy", 12: "coin",
}
USED_ROLES = sorted(set(VIEW_BY_SHOT.values()))

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def font(size: int, *, bold: bool = False):
    candidates = [
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/arphic/uming.ttc",
    ]
    for item in candidates:
        if Path(item).is_file():
            return ImageFont.truetype(item, size)
    raise RuntimeError("Noto CJK or equivalent Unicode font unavailable")

def wrap(d, value: str, size: int, width: int) -> list[str]:
    f = font(size)
    lines, line = [], ""
    for ch in value:
        if d.textbbox((0, 0), line+ch, font=f)[2] <= width:
            line += ch
        else:
            if line:
                lines.append(line)
            line = ch
    if line:
        lines.append(line)
    return lines

def owned_assets():
    manifest = json.loads((SRC / "asset_manifest.json").read_text("utf-8"))
    inventory = json.loads((SRC / "character_views_inventory.json").read_text("utf-8"))
    assert manifest["model_submission_allowed"] is False
    assert inventory["model_submission_allowed"] is False
    by_role = {x["role"]: x for x in inventory["images"]}
    assert set(USED_ROLES).issubset(by_role)
    for role in USED_ROLES:
        record = by_role[role]
        if sha(SRC / "character_views" / record["filename"]) != record["source_sha256"]:
            raise RuntimeError("Mascot source PNG SHA mismatch: " + role)
    logo_record = next(x for x in manifest["assets"] if x["asset_id"] == "citydiscount-logo-v1")
    logo_path = SRC / logo_record["relative_file"]
    if sha(logo_path) != logo_record["source_sha256"]:
        raise RuntimeError("Canonical CityDiscount logo source SHA mismatch")
    images = {
        role: Image.open(SRC / "character_views" / by_role[role]["filename"]).convert("RGBA")
        for role in USED_ROLES
    }
    return images, Image.open(logo_path).convert("RGBA"), logo_record["source_sha256"]

def place(im: Image.Image, sprite: Image.Image, x: int, y: int, width: int,
          max_h: int | None = None):
    # Crops only truly transparent pixels, preserving identifiable original art.
    a = sprite.copy().convert("RGBA")
    bbox = a.getchannel("A").getbbox()
    if bbox:
        a = a.crop(bbox)
    scale = width / a.width
    if max_h is not None:
        scale = min(scale, max_h/a.height)
    a = a.resize((max(1,round(a.width*scale)), max(1,round(a.height*scale))),
                 Image.Resampling.LANCZOS)
    im.alpha_composite(a, (int(x-a.width/2), int(y-a.height/2)))

def coin(d, x, y, radius):
    d.ellipse((x-radius,y-radius,x+radius,y+radius),fill="#efc967",outline="#f9e8a4",width=4)
    d.ellipse((x-radius+5,y-radius+5,x+radius-5,y+radius-5),outline="#b88d45",width=2)
    d.text((x,y-1),"CD",font=font(max(11,int(radius*.80)),bold=True),fill="#74552f",anchor="mm")

def family(d, x=180, y=390):
    # APPROVAL-REQUIRED symbolic silhouettes, not confirmed family casting.
    for dx,color,sz in [(-51,"#9dbaa8",1),(17,"#e5ae86",1),(69,"#e4c37e",.7)]:
        xx=x+dx
        d.ellipse((xx-19*sz,y-104*sz,xx+19*sz,y-65*sz),
                  fill="#dfb69b",outline="#ad8f78",width=2)
        d.rounded_rectangle((xx-24*sz,y-67*sz,xx+24*sz,y+18*sz),
                            radius=8,fill=color,outline="#fbf3e5",width=2)

def base(index):
    top,ground=PALETTE[index-1]
    im=Image.new("RGBA",(W,H),top)
    d=ImageDraw.Draw(im)
    d.ellipse((-110,-160,450,280),fill="#f8f3e5")
    for xx,yy in [(69,139),(280,170)]:
        d.ellipse((xx-31,yy-12,xx+25,yy+12),fill="#fff9ed")
        d.ellipse((xx-11,yy-25,xx+30,yy+14),fill="#fff9ed")
    d.ellipse((-55,304,418,530),fill=ground,outline="#ede7d5",width=3)
    for xx,hh in [(12,69),(62,95),(258,83),(310,67)]:
        d.rounded_rectangle((xx,335-hh,xx+39,351),radius=5,fill="#aec7be",outline="#dfe9df",width=3)
    return im

def stage(index, images, logo, shot):
    im=base(index)
    d=ImageDraw.Draw(im)
    if index==1:
        family(d,190,310)
        d.rounded_rectangle((33,378,323,465),radius=15,fill="#c1a181",outline="#eee0cb",width=5)
        d.rectangle((62,394,157,453),fill="#fcf8eb")
        for off,word in enumerate(["买菜","吃饭","出游"]):
            d.text((71,397+off*17),word,font=font(12),fill="#866954")
        d.rounded_rectangle((172,397,303,459),radius=7,fill="#84695c")
        for x,y in [(198,418),(243,418),(283,433)]: coin(d,x,y,15)
    elif index==10:
        family(d,175,314)
        d.ellipse((53,392,310,484),fill="#dfbda0",outline="#f6e0c7",width=5)
        for xx,cc in [(96,"#91b06e"),(166,"#ce8e6d"),(237,"#a9b89c")]:
            d.ellipse((xx-30,415,xx+30,457),fill=cc)
        d.rounded_rectangle((30,475,335,496),radius=6,fill="#b5c49d")
    else:
        if index==4:
            for xx in [20,139,258]:
                d.rounded_rectangle((xx,220,xx+81,392),radius=7,fill="#c59c75",outline="#f7dfba",width=4)
                for yy in [260,321]:d.line((xx+8,yy,xx+73,yy),fill="#8a6d55",width=5)
            d.ellipse((75,272,120,330),fill="#91b46b")
        elif index==5:
            d.rounded_rectangle((42,253,320,377),radius=12,fill="#be9b79")
            d.ellipse((61,261,131,329),fill="#f6f2e4",outline="#dfd6ba",width=5)
            d.arc((119,271,151,321),280,80,fill="#fbf4df",width=5)
            for xx in [86,101,115]:d.arc((xx,218,xx+20,252),160,320,fill="#fff8ed",width=3)
        elif index==6:
            for xx,cc in [(35,"#c6ddd5"),(141,"#e0c8b6"),(245,"#e9deb9")]:
                d.rounded_rectangle((xx,255,xx+81,390),radius=11,fill=cc,outline="#fbf4de",width=3)
            d.ellipse((212,253,292,333),outline="#b29057",width=8)
            d.line((271,319,307,354),fill="#b29057",width=8)
        elif index==7:
            d.rectangle((27,266,342,396),fill="#b9d7db")
            d.arc((34,294,326,375),185,352,fill="#f2e3c1",width=7)
            for xx in [60,112,288]:
                d.polygon([(xx,335),(xx,298),(xx+25,331)],fill="#fff9ee")
        elif index==8:
            for xx,yy,word in [(45,252,"买菜"),(192,252,"美食"),(45,335,"购物"),(192,335,"出游")]:
                d.rounded_rectangle((xx,yy,xx+125,yy+63),radius=10,fill="#f4e8d0",outline="#aa8f73",width=2)
                d.text((xx+63,yy+29),word,font=font(18,bold=True),fill="#665640",anchor="mm")
        elif index==9:
            d.polygon([(24,282),(179,252),(340,287),(322,409),(174,425),(24,396)],
                      fill="#d6e8c6",outline="#93b9a1",width=4)
            for xx,yy in [(68,307),(169,335),(260,307)]:
                d.line((xx,yy,xx,yy+24),fill="#805f49",width=2)
                d.polygon([(xx,yy),(xx+25,yy+4),(xx,yy+11)],fill="#cfac75")
            family(d,245,424)
        elif index==11:
            family(d,151,345)
            d.rounded_rectangle((39,396,319,490),radius=11,fill="#ac8674",outline="#ebd3bd",width=4)
            for xx in [89,151,213]:coin(d,xx,445,22)
        elif index==12:
            d.ellipse((40,210,320,419),fill="#bed0c5")
            for xx,yy in [(80,320),(168,288),(262,340)]:coin(d,xx,yy,20)
    if index in VIEW_BY_SHOT and index != 3:
        # Mascot local still PNG composited, NOT AI moving footage.
        target = (93,367,160) if index in [8,9,11] else (174,351,240)
        if index==12:target=(88,355,160)
        place(im,images[VIEW_BY_SHOT[index]],*target,max_h=260)
    if index == 2:
        # Approved exact logo source: operator still needs release clearance.
        place(im,logo,234,363,76,max_h=76)
        d=ImageDraw.Draw(im)
        d.rounded_rectangle((272,287,293,367),radius=6,fill="#a5794e",outline="#f0d79d",width=3)
        d.ellipse((255,266,305,317),fill="#f4d86f",outline="#e6b652",width=4)
    if index == 8:
        d=ImageDraw.Draw(im)
        d.rounded_rectangle((105,385,306,451),radius=9,fill="#b59a78",outline="#f8efda",width=3)
        place(im,logo,241,419,77,max_h=56)
    if index==12:
        # Exact Owner end-card copy in four semantic lines, visible all 5s;
        # original logo PNG is composited unmodified beneath the CTA.
        d=ImageDraw.Draw(im)
        d.rounded_rectangle((174,210,348,395),radius=12,
                            fill="#fff6e8",outline="#bdad8b",width=3)
        d.text((261,239),"CityDiscount",font=font(17,bold=True),
               fill="#355c4f",anchor="mm")
        d.text((261,265),"替你到处挖折扣",font=font(11),
               fill="#71594a",anchor="mm")
        d.text((261,284),"让生活多一点。",font=font(11),
               fill="#71594a",anchor="mm")
        d.text((261,317),"关注 CityDiscount",font=font(13,bold=True),
               fill="#486e54",anchor="mm")
        d.text((261,344),"下次消费前，",font=font(11),
               fill="#71594a",anchor="mm")
        d.text((261,362),"先来找找折扣。",font=font(11),
               fill="#71594a",anchor="mm")
        place(im,logo,220,448,212,max_h=86)
    # Text panels are a REVIEW layer, not brand final rendering.
    d=ImageDraw.Draw(im,"RGBA")
    d.rounded_rectangle((12,13,348,91),radius=13,fill=(27,61,52,225))
    d.text((24,26),f"{index:02d}  {shot['shot_title_zh']}",font=font(20,bold=True),fill="#fffdf2")
    d.text((24,57),f"{(index-1)*5:02d}–{index*5:02d}s   ·   LOCAL PNG ANIMATIC",font=font(11),fill="#cae5da")
    d.rounded_rectangle((13,491,348,511),radius=5,fill=(109,72,62,222))
    d.text((180,502),"本镜为原图静态合成，不是 AI 动态视频",font=font(11),fill="#fff9ee",anchor="mm")
    d.rounded_rectangle((12,516,348,621),radius=12,fill=(28,53,46,231))
    d.text((23,525),"原文中文旁白（尚未合成真人语音）",font=font(11),fill="#c6e2d7")
    for k,line in enumerate(wrap(d,shot["voiceover_zh"],17,305)[:3]):
        d.text((23,548+k*22),line,font=font(17),fill="#fffaf0")
    d.text((180,631),"G4 / 品牌素材本地预览 / 禁止发布",font=font(10),fill="#477265",anchor="mm")
    # Slight authentic felt noise across painted scene, do not alter source logo/mascot.
    return im

def city_overlay(shot, images):
    im=Image.new("RGBA",(W,H))
    place(im,images[VIEW_BY_SHOT[3]],63,366,125,max_h=190)
    d=ImageDraw.Draw(im,"RGBA")
    d.rounded_rectangle((12,13,348,91),radius=13,fill=(27,61,52,220))
    d.text((24,26),"03  奥克兰藏着宝",font=font(20,bold=True),fill="#fffdf2")
    d.text((24,57),"10–15s · REAL AI CITY + LOCAL PNG MASCOT",font=font(9),fill="#cae5da")
    d.rounded_rectangle((13,491,348,511),radius=5,fill=(40,90,74,230))
    d.text((180,502),"真实AI城市背景 + 本地静态吉祥物叠加",font=font(11),fill="#fff9ee",anchor="mm")
    d.rounded_rectangle((12,516,348,621),radius=12,fill=(28,53,46,231))
    d.text((23,525),"原文中文旁白（尚未合成真人语音）",font=font(11),fill="#c6e2d7")
    for k,line in enumerate(wrap(d,shot["voiceover_zh"],17,305)[:3]):
        d.text((23,548+k*22),line,font=font(17),fill="#fffaf0")
    d.text((180,631),"G4 / 视觉实验 / 禁止发布",font=font(10),fill="#fff7eb",anchor="mm")
    return im

def invoke(args):
    subprocess.run(["ffmpeg","-hide_banner","-loglevel","error","-y",*args],check=True)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--city-plate",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("Real FFmpeg and FFprobe required")
    if not args.city_plate.is_file() or sha(args.city_plate)!=CITY_PLATE_SHA256:
        raise RuntimeError("Real s03 Google Omni video SHA mismatch or missing")
    script=json.loads(PILOT.read_text("utf-8"))
    if (script.get("revision")!=3 or script.get("project")!="CityDiscount"
            or script.get("format",{}).get("shot_count")!=12
            or script.get("format",{}).get("total_duration_seconds")!=60):
        raise RuntimeError("Owner script revision or shot contract changed")
    shots=script["shots"]
    if ([x["shot_id"] for x in shots]!=[f"s{i:02d}" for i in range(1,13)]
            or any(x["duration_seconds"]!=5 for x in shots)):
        raise RuntimeError("Unexpected Owner shot sequence")
    if args.out.exists():
        raise RuntimeError("Output directory already exists; preserve old review cuts")
    args.out.mkdir(parents=True)
    actors,logo,logo_sha=owned_assets()
    parts=[]
    for i,shot in enumerate(shots,1):
        outmp4=args.out/f"part_{i:02d}.mp4"
        if i==3:
            overlay=args.out/"overlay_03.png"
            city_overlay(shot,actors).save(overlay)
            invoke(["-i",str(args.city_plate),"-i",str(overlay),"-filter_complex",
                   "[0:v]trim=duration=5,setpts=PTS-STARTPTS,scale=360:640,fps=24[bg];"
                   "[bg][1:v]overlay=0:0:format=auto,format=yuv420p[v]",
                   "-map","[v]","-an","-t","5","-c:v","libx264","-preset","veryfast",
                   "-crf","24",str(outmp4)])
        else:
            frame=args.out/f"scene_{i:02d}.png"
            stage(i,actors,logo,shot).convert("RGB").save(frame)
            invoke(["-loop","1","-framerate","24","-i",str(frame),"-vf",
                   "scale=370:658,crop=360:640:x=(in_w-out_w)/2:y=(in_h-out_h)/2,format=yuv420p",
                   "-an","-t","5","-r","24","-c:v","libx264",
                   "-preset","veryfast","-crf","25",str(outmp4)])
        parts.append(outmp4)
    # scratch score only, no generated voice; preserve exact narration as readable layer.
    sr=16000
    score=args.out/"scratch_music.wav"
    with wave.open(str(score),"wb") as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(sr)
        # Tiny synthesizer writes chunks to bound memory on CI.
        import array
        notes=[262,330,392,523,440,392,330,294]
        for i in range(60):
            frames=array.array("h")
            for j in range(sr):
                t=j/sr
                f=notes[(i*2+int(t*2))%len(notes)]
                env=max(0.0,1-(t*2)%1)**2
                val=math.sin(2*math.pi*f*t)+.22*math.sin(4*math.pi*f*t)
                frames.append(int(1200*env*val))
            w.writeframes(frames.tobytes())
    concat=args.out/"concat.txt"
    concat.write_text("".join(f"file '{p.resolve()}'\n" for p in parts),"utf-8")
    mp4=args.out/"CityDiscount_60s_real_assets_PREVIS_NOT_FINAL.mp4"
    invoke(["-f","concat","-safe","0","-i",str(concat),"-i",str(score),
            "-map","0:v:0","-map","1:a:0","-t","60","-c:v","copy",
            "-c:a","aac","-b:a","96k","-shortest","-movflags","+faststart",str(mp4)])
    probed=json.loads(subprocess.run(["ffprobe","-v","error","-show_entries",
                 "format=duration,size:stream=codec_name,codec_type,width,height",
                 "-of","json",str(mp4)],capture_output=True,text=True,check=True).stdout)
    if not 59.7 <= float(probed["format"]["duration"]) <= 60.3:
        raise RuntimeError("Rendered video not 60 sec")
    # Local real-source preview; NOT real AI 12-shot film, not publishable.
    receipt={
        "schema":"citydiscount-g4-branded-review-animatic.v1",
        "source_owner_script_sha256":sha(PILOT),
        "real_ai_environment_clip":"s03",
        "real_ai_environment_clip_sha256":CITY_PLATE_SHA256,
        "real_ai_character_motion_shots":[],
        "local_still_source_mascot_shots":[f"s{i:02d}" for i in VIEW_BY_SHOT],
        "offline_still_composite_shots":[f"s{i:02d}" for i in range(1,13) if i!=3],
        "owner_reference_pngs_sent_to_model":0,
        "logo_original_source_sha256":logo_sha,
        "logo_placements":["s02","s08","s12"],
        "s12_complete_brand_copy_visible_seconds":5,
        "s12_owner_end_card_lines":script["storyline"]["end_card_lines"],
        "canonical_coin_artwork_approved":False,
        "family_design_approved":False,
        "owner_review_status":"pending",
        "published":False,
        "g4_exit_approved":False,
        "spoken_chinese_narration_generated":False,
        "scratch_local_instrumental":True,
        "new_external_model_calls":0,
        "known_previous_google_s03_fee_usd":None,
        "video_sha256":sha(mp4),
        "ffprobe":probed,
    }
    (args.out/"receipt.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2),"utf-8")
    # 12-shot contact-sheet, featuring actual mascot + logo source art.
    thumbs=[]
    for i in range(1,13):
        if i==3:
            from PIL import ImageOps
            # Using a proof still from source only for operator contact sheet.
            f=args.out/"s03_contact_raw.jpg"
            invoke(["-ss","2","-i",str(args.city_plate),"-frames:v","1",str(f)])
            baseim=Image.open(f).convert("RGBA")
            baseim.alpha_composite(city_overlay(shots[2],actors))
        else:
            baseim=Image.open(args.out/f"scene_{i:02d}.png").convert("RGBA")
        thumbs.append(baseim.convert("RGB").resize((180,320)))
    sheet=Image.new("RGB",(180*4,320*3),"#f0eee5")
    for k,item in enumerate(thumbs):
        sheet.paste(item,((k%4)*180,(k//4)*320))
    sheet.save(args.out/"CityDiscount_12_shot_real_assets_contact.jpg",quality=90)
    print(json.dumps({"video":mp4.name,"sha256":receipt["video_sha256"],
                      "duration":probed["format"]["duration"],
                      "real_ai_background_shots":1,"new_model_calls":0},ensure_ascii=False))

if __name__=="__main__":
    main()
