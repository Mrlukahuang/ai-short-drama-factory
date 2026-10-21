"""G4 CityDiscount selected original-asset 3:4 portrait review boards.

Owner selected s02/s05/s06/s07 in the middle and official Logo at s12.
This makes truthful still visual QA assets, not model-generated moving sheep,
not a full 12-shot final film. It reuses SHA-validated checked-in mascot
and logo pixels, locally, with zero external or paid calls.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import random
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from render_citydiscount_branded_previs import owned_assets, font as font_family

PILOT = ROOT / "config/pilots/citydiscount_coin_hunt_1080x1440_v2.json"
SIZE = (1080, 1440)
CHOICE = ("s02", "s05", "s06", "s07", "s12")
PHASES = {"s02": ("departure",), "s05": ("dig_1", "dig_2", "one_coin"),
          "s06": ("cafe_arrival",),
          "s07": ("dig_1", "dig_2", "one_coin"),
          "s12": ("official_logo",)}
CANONICAL_ROLES = {"s02":"front", "s05":"front",
                   "s06":"three_quarter", "s07":"front", "s12":"front"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source() -> dict:
    obj=json.loads(PILOT.read_text("utf-8"))
    if (obj.get("project")!="CityDiscount"
            or obj.get("revision")!=4
            or obj.get("schema_version")!="g4-citydiscount-first-promo.v2"
            or obj.get("format",{}).get("width")!=1080
            or obj.get("format",{}).get("height")!=1440
            or obj.get("format",{}).get("aspect_ratio")!="3:4"
            or len(obj.get("shots",[]))!=12
            or [x["shot_id"] for x in obj["shots"]]
               !=[f"s{i:02d}" for i in range(1,13)]
            or obj["shots"][-1]["logo_hold_seconds"]<3
            or obj.get("controls",{}).get("real_paid_call_authorized") is not False
            or obj.get("controls",{}).get("publish_approved") is not False):
        raise ValueError("Owner locked 3:4 creative or approval flags changed")
    assert CHOICE==("s02","s05","s06","s07","s12")
    return obj


def felt_background(shot_id: str) -> Image.Image:
    # Lightweight handmade-felt visual layout only; NOT a claimed 3D render.
    palettes={
        "s02":("#e9f3e0","#b8d6c0","#e3c5a2"),
        "s05":("#f3ead3","#c1d6a8","#bf946d"),
        "s06":("#f2e2ce","#c4dcd0","#be9881"),
        "s07":("#ecdcc9","#a8cec4","#d7ad81"),
        "s12":("#e5eddf","#bdd2c9","#e6c497"),
    }
    sky,mid,ground=palettes[shot_id]
    im=Image.new("RGBA",SIZE,sky)
    d=ImageDraw.Draw(im)
    d.ellipse((-100,-220,1200,490),fill="#fbf6ea")
    d.rectangle((0,720,1080,1440),fill=mid)
    d.ellipse((-180,790,1260,1690),fill=ground)
    # Felt skyline, sewing-stitched Sky Tower and simple harbour.
    d.rounded_rectangle((60,380,180,795),radius=26,fill="#b6d3c8")
    d.rounded_rectangle((185,478,300,790),radius=22,fill="#d9b9a6")
    d.rounded_rectangle((800,436,950,806),radius=28,fill="#9ebdba")
    d.rounded_rectangle((958,515,1090,830),radius=18,fill="#d5bba6")
    d.line((661,286,661,768),fill="#a2afb0",width=17)
    d.ellipse((624,408,698,448),fill="#9ab4b5",outline="#e5f1e8",width=11)
    d.ellipse((630,462,694,493),fill="#88b0ad")
    d.line((661,281,661,347),fill="#e6e7da",width=11)
    d.ellipse((650,327,670,344),fill="#d6bd89")
    d.ellipse((-75,747,1300,914),fill="#a4cad0")
    for i in range(8):
        x=90+i*140
        d.line((x,799,x+90,799),fill="#e0eeeb",width=4)
    d.arc((100,677,960,907),180,360,fill="#8daaaa",width=21)
    for x,y in [(95,170),(905,211),(785,132)]:
        d.ellipse((x,y,x+180,y+76),fill="#fff9ed")
        d.ellipse((x+48,y-35,x+135,y+67),fill="#fff9ed")
    if shot_id=="s05":
        for x,col in [(0,"#b5c68e"),(220,"#a5b987"),(440,"#dccf93")]:
            d.rounded_rectangle((x+10,740,x+230,1060),radius=25,fill="#af8e71")
            for yy in [815,960]:
                d.line((x+20,yy,x+210,yy),fill="#efdabc",width=16)
            for j in range(5):
                dx=x+34+j*35
                d.ellipse((dx,780,dx+26,810),fill=col)
    elif shot_id in {"s06","s07"}:
        d.rounded_rectangle((14,540,475,1070),radius=45,fill="#b89b7d",outline="#ead2b5",width=20)
        d.rectangle((45,625,450,720),fill="#e6d1b7")
        d.rounded_rectangle((130,805,355,846),radius=12,fill="#efdfca")
        d.rounded_rectangle((185,737,290,820),radius=16,fill="#f7f2e5")
        d.arc((274,755,324,813),275,80,fill="#f6f3e8",width=13)
        d.rounded_rectangle((430,910,760,944),radius=12,fill="#a4876b")
    # Stylized wool fibers and seam dots. Never alter pixel data of imported logo/sprite.
    rng=random.Random(int(shot_id[-2:]) * 7543)
    fibers=Image.new("RGBA",SIZE,(0,0,0,0))
    f=ImageDraw.Draw(fibers)
    for _ in range(4000):
        x,y=rng.randrange(1080),rng.randrange(1440)
        f.line((x,y,x+rng.choice((-4,-2,3,4)),y+rng.randrange(2,8)),
               fill=rng.choice(((255,250,235,38),(70,66,49,22),(242,225,190,45))),
               width=1)
    im=Image.alpha_composite(im,fibers)
    return im


def paste_original(im:Image.Image,original:Image.Image,*,cx:int,cy:int,max_fraction:float=.205)->dict:
    """Resize the ORIGINAL RGBA pixels as one whole image; never redraw its eyes."""
    alpha=original.getchannel("A")
    bbox=alpha.getbbox()
    if not bbox:
        raise ValueError("Canonical sheep image lacks transparency data")
    crop=original.crop(bbox)
    target_h=round(SIZE[1]*max_fraction)
    scale=min(target_h/crop.height,round(SIZE[0]*.36)/crop.width)
    target=(round(crop.width*scale),round(crop.height*scale))
    resized=crop.resize(target,Image.Resampling.LANCZOS)
    x,y=cx-resized.width//2,cy-resized.height//2
    im.alpha_composite(resized,(x,y))
    if resized.height>round(SIZE[1]*.27):
        raise AssertionError("Mascot too large in portrait frame")
    return {"pixel_height":resized.height,"frame_height_fraction":round(resized.height/SIZE[1],4),
            "identity_pixel_transformation":"RGBA crop transparent border + aspect-preserving Lanczos resize ONLY; eyes not redrawn"}


def marker(d:ImageDraw.ImageDraw,shot:int,title:str,phase:str)->None:
    d.rounded_rectangle((35,27,1045,133),radius=26,fill="#285449")
    d.text((69,41),f"{shot:02d} · {title}",font=font_family(43,bold=True),fill="#fffaf1")
    d.text((71,97),f"1080×1440 / 3:4   •   {phase}   •   LOCAL SOURCE ART",
           font=font_family(19),fill="#e0efda")
    d.rounded_rectangle((38,1303,1042,1425),radius=19,fill="#2b5548")
    d.text((64,1314),"使用仓库原版小羊 PNG；眼睛未重画。此图为静态合成预演。",
           font=font_family(26),fill="#fff7e7")
    d.text((64,1366),"不是 AI 动态镜头 · 没有新付费调用 · 不可直接公开发布",
           font=font_family(22),fill="#d3e5d3")


def render_board(shot_id:str,phase:str,images:dict,logo:Image.Image,
                 script:dict)->tuple[Image.Image,dict]:
    shot=script["shots"][int(shot_id[-2:])-1]
    if shot_id not in CHOICE or phase not in PHASES[shot_id]:
        raise ValueError("Only Owner-selected four shots and official logo finale")
    im=felt_background(shot_id)
    d=ImageDraw.Draw(im)
    # Source sheep uses eye-open front or three-quarter version, not generated substitute.
    mascot={}
    if shot_id!="s12":
        mascot=paste_original(im,images[CANONICAL_ROLES[shot_id]],
                              cx=455 if shot_id=="s02" else 520,
                              cy=973 if shot_id=="s02" else 1010)
        d=ImageDraw.Draw(im)
        if shot_id in {"s02","s05","s07"}:
            d.line((665,965,727,1095),fill="#9c704d",width=20)
            d.ellipse((707,1082,775,1147),fill="#f7cc6b",outline="#edb458",width=7)
        if phase.startswith("dig"):
            n=1 if phase=="dig_1" else 2
            d.ellipse((730,1115,965,1195),fill="#6b4f3d")
            d.text((780,1115),f"第{n}铲",font=font_family(38,bold=True),fill="#ffefd4")
        if phase=="one_coin":
            d.ellipse((741,1069,964,1285),fill="#e4bd61",outline="#fff0ad",width=18)
            d.text((852,1170),"CD",font=font_family(88,bold=True),fill="#806133",anchor="mm")
            # This font is a placeholder, not the approved standalone coin design.
    else:
        # s12 displays ONLY original verified canonical brand logo, no fabricated lettering.
        d.rounded_rectangle((72,393,1008,1082),radius=48,fill="#fdf7ea")
        d=ImageDraw.Draw(im)
        d.text((540,457),"CityDiscount",font=font_family(62,bold=True),
               fill="#285449",anchor="mm")
        exact=logo.copy().convert("RGBA")
        bb=exact.getchannel("A").getbbox()
        if bb:exact=exact.crop(bb)
        scale=min(830/exact.width,330/exact.height)
        exact=exact.resize((round(exact.width*scale),round(exact.height*scale)),Image.Resampling.LANCZOS)
        im.alpha_composite(exact,((1080-exact.width)//2,575))
        d=ImageDraw.Draw(im)
        d.text((540,1005),"关注 CityDiscount",font=font_family(47,bold=True),
               fill="#315b4b",anchor="mm")
        d.text((540,1095),"下次消费前，先来找找折扣。",font=font_family(30),
               fill="#5f6f54",anchor="mm")
    d=ImageDraw.Draw(im)
    marker(d,int(shot_id[-2:]),shot["shot_title_zh"],phase)
    return im,{"shot_id":shot_id,"phase":phase,"size_px":list(im.size),
               "mascot_role":CANONICAL_ROLES[shot_id] if shot_id!="s12" else None,
               "mascot":mascot,"original_logo_used":shot_id=="s12",
               "coin_graphic_status":"unapproved illustration" if phase=="one_coin" else None}


def render(out:Path)->dict:
    if out.exists():
        raise FileExistsError("Review output exists; refuse overwrite")
    obj=source()
    roles,logo,logo_sha=owned_assets()
    if logo_sha!=obj["brand_asset_requirements"]["logo"]["source_sha256"]:
        raise ValueError("Owner official logo source hash differs")
    out.mkdir(parents=True,exist_ok=False)
    frames=[]
    imgs=[]
    for sid in CHOICE:
        for phase in PHASES[sid]:
            im,record=render_board(sid,phase,roles,logo,obj)
            filename=f"{sid}_{phase}_original_mascot_3x4.png"
            path=out/filename
            im.convert("RGB").save(path,optimize=True)
            record["sha256"]=sha(path)
            frames.append(record)
            imgs.append(im.convert("RGB").resize((270,360)))
    sheet=Image.new("RGB",(270*3,360*3),"#e6e5df")
    for i,img in enumerate(imgs):
        sheet.paste(img,((i%3)*270,(i//3)*360))
    sheet.save(out/"citydiscount_priority_5_scenes_contact.jpg",quality=90)
    result={
        "schema":"g4-citydiscount-canonical-3x4-priority-stills.v1",
        "owner_selection":["s02","s05","s06","s07","s12"],
        "owner_current_story_sha256":sha(PILOT),
        "logo_original_sha256":logo_sha,
        "source_png_direct_composite_only":True,
        "no_new_lamb_identity_or_painted_eyes":True,
        "sprite_eyes_not_modified":True,
        "target_pixel_size":[1080,1440],
        "asset_kind":"STATIC review image, NOT a video; no actual 3D character animation",
        "all_generated_images_are_publish_approved":False,
        "canonical_coin_design_approved":False,
        "backgrounds_are_local_stylized_review_drawings":True,
        "new_paid_calls":0,"model_submission_allowed":False,
        "previous_google_video_bill_usd":None,
        "frames":frames,
    }
    (out/"receipt.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),"utf-8")
    return result


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args(argv)
    result=render(args.out)
    print(json.dumps({"output_size":result["target_pixel_size"],
                      "frames":len(result["frames"]),"paid_calls":0}))

if __name__=="__main__":
    main()
