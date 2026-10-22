"""Locally bridge the final XYZ felt city shot into existing Owner-logo globe MP4.

The last city frame is shrunk into the illustration-globe as a short
city-on-sphere image transition. It is not a continuous planetary 3D camera
model, realistic Earth or owner-approved finished motion picture. From t=.9s
onward the original SHA-pinned endcard frames are untouched except for local
resize and H264 encoding, retaining 3.4 seconds of canonical Logo hold.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw

W,H,FPS=540,720,12
LENGTH=5.0


def ease(t:float)->float:
    x=max(0,min(1,t))
    return x*x*(3-2*x)


def bridge_frame(city:Image.Image,earth:Image.Image,t:float)->Image.Image:
    """At t=0, exact last scene; after .9s, exact globe source frame."""
    if not 0<=t<5:
        raise ValueError("Endcard preview duration must remain five seconds")
    if city.size!=(W,H) or earth.size!=(W,H):
        raise ValueError("Only canonical portrait intermediate dimensions")
    if t<=0:
        return city.copy()
    if t>=.9:
        return earth.copy()
    q=ease(t/.9)
    # Start with a radius larger than ANY canvas corner: the FIRST several
    # frames are spatially continuous, not a sudden circular wipe.
    radius=round(575-(575-170)*q)
    opacity=255*(1-q)
    overlay=Image.new("RGBA",(W,H),(0,0,0,0))
    # Scale down city as the globe comes into view. Before first half of blend,
    # preserve prior footage's original framing exactly.
    factor=min(1.0,radius/420)
    if factor<1:
        mini=city.resize((max(1,round(W*factor)),max(1,round(H*factor))),
                         Image.Resampling.LANCZOS)
        paste_x=round((W-mini.width)*.5)
        paste_y=round(280-mini.height*.45)
        overlay.paste(mini,(paste_x,paste_y))
    else:
        overlay.paste(city,(0,0))
    mask=Image.new("L",(W,H),0)
    circle=ImageDraw.Draw(mask)
    circle.ellipse((270-radius,280-radius,270+radius,280+radius),fill=255)
    # Use both the ellipse boundary and a smooth alpha falloff for gentle move.
    alpha=mask.point(lambda a:round(a*opacity/255))
    overlay.putalpha(alpha)
    base=earth.convert("RGBA")
    base.alpha_composite(overlay)
    return base.convert("RGB")


def decode_existing(original:Path)->list[Image.Image]:
    data=subprocess.check_output([
        "ffmpeg","-hide_banner","-loglevel","error","-nostdin",
        "-i",str(original),"-t","5","-vf","fps=12,scale=540:720",
        "-f","rawvideo","-pix_fmt","rgb24","pipe:1"])
    frame_bytes=W*H*3
    if len(data)!=FPS*5*frame_bytes:
        raise ValueError("Previous SHA-pinned endcard missing exact 5s frames")
    return [Image.frombytes("RGB",(W,H),data[i*frame_bytes:(i+1)*frame_bytes])
            for i in range(FPS*5)]


def encode(city:Image.Image,original:Path,out:Path)->dict:
    if out.exists():
        raise FileExistsError("Fresh bridge output expected")
    originals=decode_existing(original)
    cmd=["ffmpeg","-hide_banner","-loglevel","error","-nostdin","-y",
         "-f","rawvideo","-pixel_format","rgb24","-video_size","540x720",
         "-framerate","12","-i","pipe:0","-vf",
         "scale=1080:1440:flags=lanczos,fps=24",
         "-t","5","-r","24","-an","-c:v","libx264",
         "-preset","ultrafast","-crf","30","-pix_fmt","yuv420p",str(out)]
    process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL)
    try:
        for i,earth in enumerate(originals):
            process.stdin.write(bridge_frame(city,earth,i/FPS).tobytes())
        process.stdin.close()
        if process.wait()!=0:
            raise RuntimeError("City→globe local FFmpeg encoding failed")
    except BaseException:
        process.kill()
        process.wait()
        raise
    return {
        "world_space_city_origin":True,
        "city_to_globe_compositing_seconds":.9,
        "genuine_planetary_3d_cinematic_camera":False,
        "source_endcard_unchanged_after_seconds":.9,
        "owner_logo_reveal_seconds_in_s12":1.6,
        "logo_hold_seconds":3.4,
    }
