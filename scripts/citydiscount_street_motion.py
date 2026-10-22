"""CityDiscount G4 local 3D city camera keys + original-sprite walk-cycle.

Shared routes move between exact street coordinates instead of crossing 3D
building lots. Sprite remains the original Owner PNG: translate/tilt only, never
paint a new face or falsely claim it is a fully rigged 3D character.
"""
from __future__ import annotations

import math
from PIL import Image, ImageDraw


def smooth(q:float)->float:
    q=max(0.0,min(1.0,q))
    return q*q*(3-2*q)


def mix(a:float,b:float,q:float)->float:
    return a+(b-a)*smooth(q)


# (target_x,target_y,azimuth,elevation,pixels_per_world_unit,center_y)
AERIAL=(2.55,2.65,.78,1.18,43,380)
FIRST_BLOCK=(3.52,2.25,.82,.78,91,380)
MARKET=(3.94,2.67,.90,.61,110,414)
CAFE=(3.04,3.05,1.02,.69,108,410)
CAFE_NEAR=(3.00,3.06,1.02,.67,116,412)
SHOP=(2.00,3.86,.86,.65,108,412)
SHOP_NEAR=(2.00,4.08,.84,.65,114,414)
FAMILY=(1.20,4.45,.80,.64,90,410)
WHOLE_CITY=(2.60,2.65,.78,1.15,42,370)


def interpolate_camera(a:tuple,b:tuple,q:float)->tuple:
    if len(a)!=6 or len(b)!=6:
        raise ValueError("Camera needs six world-space parameters")
    return tuple(mix(x,y,q) for x,y in zip(a,b))


def camera_key(shot_id:str,t:float)->tuple:
    if not 0<=t<=5:
        raise ValueError("Invalid local shot time")
    q=t/5
    joins={
        "s03":(AERIAL,FIRST_BLOCK),
        "s04":(FIRST_BLOCK,MARKET),
        "s06":(MARKET,CAFE),
        "s07":(CAFE,CAFE_NEAR),
        "s08":(CAFE_NEAR,SHOP),
        "s09":(SHOP,SHOP_NEAR),
        "s10":(SHOP_NEAR,FAMILY),
    }
    if shot_id in joins:
        a,b=joins[shot_id]
        return interpolate_camera(a,b,q)
    if shot_id=="s11":
        return interpolate_camera(FAMILY,WHOLE_CITY,(t-3.35)/1.65)
    return (1.25,4.15,.82,.64,120,415)


# Travel on the integer road centerlines. Every leg has constant X or Y,
# not a diagonal shortcut through an extruded shop or residential building.
PATHS={
    "s01":((1.0,4.30),),
    "s03":((4.0,1.0),(4.0,2.0)),
    "s04":((4.0,2.0),(4.0,3.0)),
    "s06":((4.0,3.0),(3.0,3.0)),
    "s07":((3.0,3.0),),
    "s08":((3.0,3.0),(2.0,3.0),(2.0,4.0)),
    "s09":((2.0,4.0),),
    "s10":((2.0,4.0),(1.0,4.0),(1.0,4.60)),
    "s11":((1.0,4.60),(1.0,4.30)),
}


def world_path(shot_id:str,t:float)->tuple[float,float]:
    if shot_id not in PATHS or not 0<=t<=5:
        raise ValueError("Unknown local 3D shot or time")
    nodes=PATHS[shot_id]
    if len(nodes)==1:
        return nodes[0]
    lengths=[math.dist(a,b) for a,b in zip(nodes[:-1],nodes[1:])]
    remaining=smooth(t/5)*sum(lengths)
    for (a,b),length in zip(zip(nodes[:-1],nodes[1:]),lengths):
        if remaining<=length or b==nodes[-1]:
            u=min(1,remaining/length) if length>0 else 1
            return (a[0]+(b[0]-a[0])*u,a[1]+(b[1]-a[1])*u)
        remaining-=length
    return nodes[-1]


def within_road(x:float,y:float)->bool:
    return min(abs(x-round(x)),abs(y-round(y))) <= .115


def actor_key(shot_id:str,t:float)->tuple[float,float,int]:
    x,y=world_path(shot_id,t)
    world_camera=camera_key(shot_id,t)
    # 3D camera distance determines screen footprint, no detached screen glide.
    height=round(max(24,min(123,world_camera[4]*.97)))
    return x,y,height


def pose(shot_id:str,t:float)->dict:
    active=shot_id in ("s03","s04","s06","s08","s10","s11")
    if shot_id=="s11" and t>=3.5:
        active=False
    phase=2*math.pi*2.3*t
    dig=shot_id in ("s07","s09")
    return {
        "walking":active,
        "bob_height":.042*max(0,math.sin(phase)) if active else 0.0,
        "tilt_degrees":2.7*math.sin(phase) if active
                       else (1.8*math.sin(phase*.8) if dig else 0.0),
        "left_foot_forward":math.sin(phase)>0,
        "dig_stroke":1 if dig and .8<=t<1.3 else 2 if dig and 2.05<=t<2.55 else 0,
        "coin_visible":bool(dig and t>=2.85),
    }


def composite_actor(image:Image.Image,cam,source:Image.Image,
                    xyz:tuple[float,float,float],height:int,
                    *,shot_id:str,t:float)->None:
    p=pose(shot_id,t)
    x,y,z=xyz
    px,py=cam.project((x,y,z))
    drawer=ImageDraw.Draw(image)
    width=max(4,round(height*.31))
    drawer.ellipse((px-width,py-6,px+width,py+4),fill="#809d8c")
    if p["walking"]:
        stride=max(2,round(cam.zoom*.045))
        for step in (-1,1):
            xx=px+step*stride
            yy=py-(4 if (step==1)==p["left_foot_forward"] else 0)
            drawer.ellipse((xx-4,yy-3,xx+4,yy+3),
                           fill="#d7c2a3",outline="#957f68",width=1)
    raw=source.convert("RGBA")
    bbox=raw.getchannel("A").getbbox()
    if not bbox:
        raise ValueError("Original owner PNG has no opaque pixels")
    original=raw.crop(bbox)
    w=max(1,round(original.width*height/original.height))
    actor=original.resize((w,height),Image.Resampling.LANCZOS)
    if abs(p["tilt_degrees"])>.10:
        actor=actor.rotate(p["tilt_degrees"],
                           resample=Image.Resampling.BICUBIC,expand=True)
    _,raised=cam.project((x,y,z+p["bob_height"]))
    offset=5 if p["dig_stroke"] else 0
    image.paste(actor,(round(px-actor.width/2),
                       round(raised-actor.height*.88+offset)),actor.getchannel("A"))
    d=ImageDraw.Draw(image)
    if p["dig_stroke"]:
        d.line((px+height*.20,py-height*.58,
                px+height*.38,py-4),fill="#93714a",width=3)
        d.ellipse((px+height*.32,py-5,px+height*.44,py+2),
                  fill="#e0c499")
    if p["coin_visible"]:
        cx,cy=cam.project((x+.20,y+.04,.046))
        radius=max(3,round(cam.zoom*.07))
        d.ellipse((cx-radius,cy-radius,cx+radius,cy+radius),
                  fill="#e4b858",outline="#ffebaf",width=2)
    # No model-generated logo/CD lettering; symbol is unapproved still illustration.
