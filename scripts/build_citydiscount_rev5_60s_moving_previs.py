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
import citydiscount_3d_diorama as city3d
import citydiscount_city_to_globe_bridge as globe_bridge

W,H,FPS=540,720,12
SOURCE_REV4_SHA="e65d01356dcc977ab40c6cfea2ed479b812b8d16ffae6ccc41bfde8ce430288e"
SOURCE_END_SHA="273516cacbc07d750fd0262de6897ddd3a879ed5e22fa58fd1f5a49e09c6b8c1"
SOURCE_CLEAN_S05_SHA="7a4a7e5f261a641dd7035698a5aad3a9a331bf51a70c5ccd7565677a2694a652"
SOURCE_BRANDED_COIN_REVIEW_SHA="6b5c164834df7fd28b1c20fb917399136b1ac900478efef34c504aee63f8d9f7"
# Branded coin is a locally keyed REVIEW layer from real Omni s05; no new real scene.
SOURCE_REAL_S03_ENV_SHA="b718e6b0a6e5a64db66d74e6b1364326d16671823fca12935e8a3667b101af3f"
# Authenticated source is a REVIEW COPY of the same old Gemini Omni s05, not a new shot.
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
    d.text((24,678),"3D几何街区 · 小羊2D原版图像预演",
           font=boards.font_family(16),fill="#f9f4db")


def movie_frame(sid:str,t:float,context:dict)->Image.Image:
    """Real 3D X/Y/Z procedural diorama projection, not AI-generated city footage.

    Sheep is still the original SHA-verified 2D owner PNG billboard in this
    finite physical geometry. Dynamic camera changes actual building projection,
    window parallax and mascot occlusion; NOT a rigged 3D animated sheep.
    """
    im=city3d.scene_frame(sid,t,context["front"])
    title={
        "s01":"微缩立体毛毡家园",
        "s03":"3D奥克兰城市俯瞰 · 下降推向街区",
        "s04":"立体屋顶之间 Zoom in 到超市街道",
        "s06":"小羊穿过立体街区 · 咖啡站",
        "s07":"立体咖啡街角 · 挖金币",
        "s08":"建筑之间穿街 · 购物区",
        "s09":"立体购物街 · 第三枚金币",
        "s10":"穿越屋群 · 镜头立体拉远",
        "s11":"家庭交付 · 从立体城市拉远到地球",
    }[sid]
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


def extract_clean_s05(source:Path,target:Path)->None:
    """Retain all real original s05 pixels without stretching native 9:16.

    The clean clip is 360x640. All 60s concatenated segments need matching
    1080x1440 3:4, so center the original at sharp 810x1440 and blur the
    same old footage behind it to fill 135px on each side. No new model
    visuals, logo, retailer name or character geometry invented here.
    """
    vf=(
        "[0:v]split=2[original][background];"
        "[background]scale=1080:1920:flags=lanczos,"
        "crop=1080:1440:0:240,gblur=sigma=26[blurred];"
        "[original]scale=810:1440:flags=lanczos[sharp];"
        "[blurred][sharp]overlay=(W-w)/2:0,format=yuv420p,fps=24[v]"
    )
    call(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
          "-i",str(source),"-filter_complex",vf,"-map","[v]",
          "-t","5.000","-an","-r","24","-c:v","libx264",
          "-preset","ultrafast","-crf","30","-pix_fmt","yuv420p",str(target)])


def extract_real_s03_city_zoom(source:Path,target:Path)->None:
    """Invert an ALREADY GENERATED real felt-Auckland city crane-out.

    Historical real s03 contains NO sheep or face. Reverse order converts
    real wool-town camera pullback to a push-in toward Sky Tower/city blocks,
    but does NOT produce a physically verified s03→s04 unbroken model shot.
    Native 9:16 is fitted in a sharp centered 810x1440 lane with same-video
    blurred sides, not stretched into 3:4.
    """
    vf=(
        "[0:v]trim=duration=5,setpts=PTS-STARTPTS,reverse,"
        "split=2[original][background];"
        "[background]scale=1080:1920:flags=lanczos,"
        "crop=1080:1440:0:240,gblur=sigma=26[blurred];"
        "[original]scale=810:1440:flags=lanczos[sharp];"
        "[blurred][sharp]overlay=(W-w)/2:0,format=yuv420p,fps=24[v]"
    )
    call(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
          "-i",str(source),"-filter_complex",vf,"-map","[v]",
          "-frames:v","120","-an","-r","24",
          "-c:v","libx264","-preset","ultrafast","-crf","30",
          "-pix_fmt","yuv420p",str(target)])


def extract_real_s04_same_plate_digital_push(s03_segment:Path,target:Path)->None:
    """Optional visual-comparison alternative to abrupt wool→cube-map cut.

    The s04 five seconds are a local zoompan of the EXACT last encoded frame
    of the historical real city s03. They are NOT new AI or camera-parallax,
    contain NO new lamb performance, and MUST NOT be called a true 3D shot.
    Original s03 is verified upstream against its historical SHA.
    """
    still=target.with_suffix(".s03-last.png")
    try:
        # Decode all existing s03 frames and persist the *actual last* one.
        # FFmpeg's image2 "-update 1" is robust to source timestamp/count
        # differences; using select(n=119) sometimes yields zero images on GH.
        call(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
              "-i",str(s03_segment),"-vsync","0","-update","1",
              str(still)])
        if not still.is_file() or still.stat().st_size<1000:
            raise ValueError("Unable to extract genuine last s03 frame")
        # At t=0 the crop matches the last s03 frame; slowly push into
        # precisely the same miniature wool blocks. Moderate <=1.5x.
        vf=(
            "zoompan=z='min(1+on*0.0042,1.5)':"
            "x='(iw-iw/zoom)*0.55':y='(ih-ih/zoom)*0.70':"
            "d=120:s=1080x1440:fps=24,format=yuv420p"
        )
        call(["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
              "-loop","1","-framerate","24","-i",str(still),
              "-vf",vf,"-frames:v","120","-an",
              "-c:v","libx264","-preset","ultrafast",
              "-crf","30","-pix_fmt","yuv420p",str(target)])
    finally:
        still.unlink(missing_ok=True)


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


def make_cut(*,rev4:Path,end:Path,out:Path,s05_clean:Path|None=None,s03_city:Path|None=None,s04_same_real_plate:bool=False,s05_cd_coin:Path|None=None)->dict:
    rev4=valid_input(rev4,SOURCE_REV4_SHA)
    end=valid_input(end,SOURCE_END_SHA)
    if s05_clean is not None:
        s05_clean=valid_input(s05_clean,SOURCE_CLEAN_S05_SHA)
    if s05_cd_coin is not None:
        if s05_clean is None:
            raise ValueError("CD coin review needs SHA-verified sanitized real s05 lineage")
        s05_cd_coin=valid_input(s05_cd_coin,SOURCE_BRANDED_COIN_REVIEW_SHA)
    if s03_city is not None:
        s03_city=valid_input(s03_city,SOURCE_REAL_S03_ENV_SHA)
    if s04_same_real_plate and s03_city is None:
        raise ValueError('s04 real-frame continuation requires exact SHA-pinned historical s03 real city source')
    plan,logo,logo_hash=endcard.load()
    assert plan["endcard"]["closing_copy"]==endcard.TAGLINE
    assert (plan["output"]["total_duration_ms"],plan["output"]["shots"])==(60000,12)
    if out.exists():
        raise FileExistsError("Refuse to overwrite any prior review cut")
    roles,_,_=boards.owned_assets()
    front=roles["front"].convert("RGBA")
    out.mkdir(parents=True,exist_ok=False)
    seg=out/"segments";seg.mkdir()
    context={"front":front} # Real X/Y/Z geometry comes from city3d, not flat maps
    provenance=[]
    globe_receipt=None
    for i in range(1,13):
        sid=f"s{i:02}"
        target=seg/(sid+".mp4")
        if sid=="s04" and s04_same_real_plate:
            # s03.mp4 has just been rendered and is the actual genuine wool city.
            extract_real_s04_same_plate_digital_push(seg/"s03.mp4",target)
            kind="LOCAL_ZOOMPAN_OF_HISTORICAL_REAL_OMNI_CITY_S03_FRAME_NOT_NEW_REAL_SHOT"
        elif sid=="s03" and s03_city is not None:
            extract_real_s03_city_zoom(s03_city,target)
            kind="EXISTING_REAL_OMNI_AUCKLAND_ENVIRONMENT_REVERSE_CAMERA_NOT_CHARACTER"
        elif sid=="s05" and s05_cd_coin is not None:
            # Exact SHA-pinned real s05, with already-sanitized shop sign AND
            # a MANUAL approximate CD glyph coin overlay. Owner QA pending.
            extract_clean_s05(s05_cd_coin,target)
            kind="EXISTING_REAL_OMNI_S05_CLEAN_SHOP_LOCAL_CD_COIN_REVIEW_NOT_APPROVED"
        elif sid=="s05" and s05_clean is not None:
            # Old unbranded clean-sign variant remains the DEFAULT.
            extract_clean_s05(s05_clean,target)
            kind="EXISTING_REAL_OMNI_S05_BRAND_SIGN_REDACTED_LOCAL_REVIEW"
        elif sid in REAL_IDS:
            extract(rev4,target,start=(i-1)*5)
            kind="EXISTING_REAL_OMNI_CHARACTER_MP4_FROM_SHA_PINNED_REV4"
        elif sid=="s12":
            # Connect the actual LAST frame of the moving XYZ city to the globe
            # rather than cutting abruptly from streets to an unrelated sphere.
            city_last=movie_frame("s11",(5*FPS-1)/FPS,context)
            globe_receipt=globe_bridge.encode(city_last,end,target)
            kind="CITY_XYZ_TO_EXISTING_FELT_GLOBE_OFFICIAL_LOGO_BLEND"
        else:
            encode_drawn(sid,target,context)
            kind="LOCAL_PROCEDURAL_XYZ_CITY_CAMERA_NOT_REAL_AI_FOOTAGE"
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
        "s05_original_real_omni_sha256":"4ed60c4e769ab36e21186733931e89c23d1dcbb776e3274389216a2bb742fc56",
        "s05_redacted_review_input_sha256":SOURCE_CLEAN_S05_SHA if s05_clean else None,
        "s05_cd_coin_local_review_sha256":SOURCE_BRANDED_COIN_REVIEW_SHA if s05_cd_coin else None,
        "s05_coin_from_existing_official_endcard_glyph":s05_cd_coin is not None,
        "s05_coin_local_manual_tracking_not_owner_approved":s05_cd_coin is not None,
        "s05_coin_review_inserted_into_this_60s_cut":s05_cd_coin is not None,
        "s05_official_brand_glyph_source_full_logo_png_independently_verified":False,
        "s05_shop_sign_hallucination_removed_in_cut":s05_clean is not None,
        "s05_native_9by16_reframed_without_stretch":s05_clean is not None,
        "s05_clean_reuses_existing_omni_not_new_ai":True,
        "s05_original_audio_replaced_by_temporary_mix":True,
        "s05_coin_exact_design_approved":False,
        "s05_two_digs_owner_verified":False,
        "historical_city_plate_rev4_unused_in_this_2d_aerial_treatment":True,
        "s03_genuine_existing_omni_environment_in_60s":s03_city is not None,
        "s03_real_source_sha256":SOURCE_REAL_S03_ENV_SHA if s03_city else None,
        "s03_original_camera_crane_out_retimed_in_reverse":s03_city is not None,
        "s03_native_9by16_nonstretched_reframe":s03_city is not None,
        "s03_has_original_mascot_performance":False,
        "s03_s04_unbroken_real_world_camera_verified":False,
        "s04_same_original_real_city_frame_followup":s04_same_real_plate,
        "s04_last_s03_frame_local_digital_push_only":s04_same_real_plate,
        "s04_genuine_new_ai_character_performance":False,
        "s04_genuine_3d_parallax_camera_motion":False,
        "s04_sharp_zoompanning_limited_to_1point5x":s04_same_real_plate,
        "s04_original_program_city_unmodified_in_default_cut":not s04_same_real_plate,
        "real_model_generated_shots_added_in_this_run":0,
        "scene_camera_3d_geometry_previs":([sid for sid in ("s01","s03","s04","s06","s07","s08","s09","s10","s11")
            if not (sid=="s03" and s03_city) and not (sid=="s04" and s04_same_real_plate)]),
        "hybrid_lamb_projected_3d_wool_body_and_four_gait_legs":True,
        "family_cast_is_provisional_xyz_wool_placeholder":True,
        "near_actor_dollhouse_roof_cutaway_rendered":True,
        "visual_aesthetic_owner_approval":None,
        "owner_source_face_rgba_unmodified_except_crop_resize_tilt":True,
        "hybrid_lamb_owner_3d_identity_approval":False,
        "city_xyz_to_felt_globe_source_bridge":globe_receipt,
        "planetary_full_3d_camera_animation_pass":False,
        "procedural_3d_scene_rendered":True,
        "street_routes_use_continuous_xyz_grid":True,
        "camera_keys_match_across_non_paid_cuts":True,
        "sheep_bounded_2d_gait_bob_and_footstep_pass":True,
        "sheep_is_original_billboard_not_3d_rigged":True,
        "sheep_actor_is_billed_3d_rigged":False,
        "original_sheep_2d_billboard_in_xyz_city":True,
        "genuine_aerial_to_street_3D_camera_pass":False, # No approved real NZ-world/cinematic capture
        "genuine_sheep_travel_world_zoom_pass":False,
        "true_complete_12shot_AI_film":False,
        "original_unlicensed_audio_source":False,
        "audio":"locally synthesized temporary original notes + placeholder dig/coin beat, NO natural human Chinese voice",
        "diorama_renderer":"projected physical XYZ cuboids, changing azimuth/elevation/zoom, billboard small original sheep and painter-depth occlusion",
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
    p.add_argument("--s04-same-real-plate",action="store_true",
                   help="OPTIONAL separate internal A/B: digital push from exact last s03 genuine wool-city frame, NO new lamb or real 3D movement")
    p.add_argument("--s03-city",type=Path,
                   help="Historical RAW real Omni Auckland s03 city-only source; reverses original pullback into approach without generating a lamb")
    p.add_argument("--s05-cd-coin",type=Path,
                   help="OPTIONAL exact SHA real Omni s05 with manually tracked CD coin preview, requires --s05-clean; never approves brand or overwrites default")
    p.add_argument("--s05-clean",type=Path,
                   help="Optional SHA-pinned local sign-redacted REAL Omni s05 5s MP4; never substitutes synthetic media")
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    result=make_cut(rev4=a.rev4,end=a.end,out=a.out,
                    s05_clean=a.s05_clean,s03_city=a.s03_city,
                    s04_same_real_plate=a.s04_same_real_plate,
                    s05_cd_coin=a.s05_cd_coin)
    print(json.dumps({k:result[k] for k in
           ("film_sha256","duration_seconds","closing_copy",
            "existing_real_AI_lamb_shots","true_complete_12shot_AI_film")},
           ensure_ascii=False))


if __name__=="__main__":
    main()
