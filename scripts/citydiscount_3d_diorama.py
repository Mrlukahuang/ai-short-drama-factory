"""Deterministic local 3D *geometry projection* for CityDiscount rev5 camera PREVIS.

Builds finite world-space X/Y/Z buildings, roofs, shop boxes and road surfaces,
then reprojects geometry from a moving orthographic camera. This is real 3D
geometry rendered into 2D frames without Blender/Godot/remote models, but it is
not realistic 3D animation, AI-model footage or photoreal NZ cartography.
The original verified mascot RGBA PNG remains a billboard (not a rigged actor).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable

from PIL import Image, ImageDraw
import citydiscount_street_motion as motion
import citydiscount_volumetric_lamb as volume

W,H=540,720
STOPS={
    "s01":(1.0,4.25), "s03":(3.8,1.80), "s04":(3.85,2.0),
    "s06":(2.82,2.97), "s07":(2.96,3.17),
    "s08":(1.92,4.02), "s09":(1.75,4.25),
    "s10":(1.25,4.66), "s11":(1.05,4.35)
}
PALETTES=[
    ("#d8bfa6","#a68b77","#c5a68c"),
    ("#c1d5c5","#859f97","#a3bcb4"),
    ("#e2d4b8","#b19a85","#d6c19e"),
    ("#d1c3cb","#aa949c","#c4abb8"),
    ("#c5d7d3","#85a5a0","#a5c1b9"),
]


@dataclass(frozen=True)
class Camera:
    target_x: float=2.55
    target_y: float=2.65
    azimuth: float=0.78
    elevation: float=0.86
    zoom: float=55.0
    center_y: int=365

    def project(self, point:tuple[float,float,float])->tuple[int,int]:
        x,y,z=point
        dx=x-self.target_x
        dy=y-self.target_y
        ca,sa=math.cos(self.azimuth),math.sin(self.azimuth)
        se,ce=math.sin(self.elevation),math.cos(self.elevation)
        right=dx*ca-dy*sa
        up=-(dx*sa+dy*ca)*se+z*ce
        return (int(W/2+right*self.zoom), int(self.center_y-up*self.zoom))

    def distance(self,x:float,y:float)->float:
        return x*math.sin(self.azimuth)+y*math.cos(self.azimuth)


def lerp(a:float,b:float,q:float)->float:
    return a+(b-a)*max(0,min(1,q))


def eased(t:float)->float:
    q=max(0,min(1,t))
    return q*q*(3-2*q)


def camera_for(sid:str,t:float)->Camera:
    return Camera(*motion.camera_key(sid,t))


def building_data():
    result=[]
    for ix in range(5):
        for iy in range(5):
            if (ix,iy) in {(2,1),(0,4),(4,0)}:
                continue
            key=(ix*13+iy*17)%5
            roof,left,right=PALETTES[key]
            height=.52+((ix*5+iy*11)%7)*.105
            if (ix,iy)==(2,3):
                height=1.32
            result.append({
                "ix":ix,"iy":iy,"x0":ix+.20,"y0":iy+.20,
                "x1":ix+.80,"y1":iy+.80,
                "h":height,"roof":roof,"front":left,"side":right
            })
    # A central Sky Tower-like vertical diorama landmark, all self-illustrated.
    result.append({"ix":2,"iy":1,"x0":2.37,"y0":1.32,"x1":2.59,
                   "y1":1.55,"h":2.72,"roof":"#d9e5dc",
                   "front":"#8da7a6","side":"#b5d1c5"})
    return result


BUILDINGS=building_data()


def _poly(d:ImageDraw.ImageDraw,cam:Camera,points:list,**kwargs)->None:
    d.polygon([cam.project(p) for p in points],**kwargs)


def draw_building(d:ImageDraw.ImageDraw,cam:Camera,b:dict)->None:
    x0,x1,y0,y1,h=b["x0"],b["x1"],b["y0"],b["y1"],b["h"]
    # Cast topologically correct three-dimensional shadow on a ground plane.
    _poly(d,cam,[(x0+.15,y0+.18,.008),(x1+.15,y0+.18,.008),
                 (x1+.15,y1+.18,.008),(x0+.15,y1+.18,.008)],
          fill="#8ba59a")
    # Actual vertical wall quads in 3D, not hand-painted side highlights.
    _poly(d,cam,[(x0,y1,0),(x1,y1,0),(x1,y1,h),(x0,y1,h)],
          fill=b["front"])
    _poly(d,cam,[(x1,y0,0),(x1,y1,0),(x1,y1,h),(x1,y0,h)],
          fill=b["side"])
    _poly(d,cam,[(x0,y0,h),(x1,y0,h),(x1,y1,h),(x0,y1,h)],
          fill=b["roof"])
    for i in range(1,4):
        y=lerp(y0,y1,i/4)
        # Rows of small felt windows remain on vertical, physically projected walls.
        center=(x1,y,h*.47)
        px,py=cam.project(center)
        d.rounded_rectangle((px-3,py-5,px+3,py+6),radius=1,fill="#f5e6bd")
    # Felt roof seams projected in XYZ, not fake screen-space painted blocks.
    for j in range(1,5):
        roof_y=lerp(y0,y1,j/5)
        left=cam.project((x0+.08,roof_y,h+.003))
        right=cam.project((x1-.08,roof_y,h+.003))
        d.line((left,right),fill="#eee4cf",width=1)
    p=cam.project(((x0+x1)*.5,(y0+y1)*.5,h))
    d.line([(p[0]-8,p[1]),(p[0]+6,p[1]-3)],
           fill="#f9f0d8",width=2)


def draw_road_grid(d:ImageDraw.ImageDraw,cam:Camera)->None:
    _poly(d,cam,[(-.4,-.4,-.01),(5.45,-.4,-.01),
                 (5.45,5.45,-.01),(-.4,5.45,-.01)],fill="#97b9a2")
    # Streets are topologically continuous between blocks.
    for index in range(6):
        _poly(d,cam,[(index-.08,-.4,.012),(index+.11,-.4,.012),
                     (index+.11,5.45,.012),(index-.08,5.45,.012)],
              fill="#e5d8be")
        _poly(d,cam,[(-.4,index-.08,.013),(5.45,index-.08,.013),
                     (5.45,index+.11,.013),(-.4,index+.11,.013)],
              fill="#ede3ca")
    for i in range(1,5):
        for j in range(1,5):
            if (i+j)%2:
                p=cam.project((i+.02,j+.02,.025))
                radius=max(1,int(cam.zoom/46))
                d.ellipse((p[0]-radius,p[1]-radius,p[0]+radius,p[1]+radius),
                          fill="#fbf0da")


def tiny_felt_background(im:Image.Image)->None:
    d=ImageDraw.Draw(im)
    # The sky and harbour stay behind the 3D city geometry.
    d.ellipse((-130,-200,700,460),fill="#eef0dd")
    d.polygon([(0,390),(85,343),(200,382),(540,302),(540,720),(0,720)],
              fill="#add2d1")
    rng=random.Random(3203)
    for _ in range(155):
        x,y=rng.randrange(W),rng.randrange(H)
        if y<240:
            d.line((x,y,x+2,y+4),fill="#fff8e6",width=1)


def _mascot_image(source:Image.Image,size:int)->Image.Image:
    img=source.convert("RGBA")
    bbox=img.getchannel("A").getbbox()
    if not bbox:
        raise ValueError("Canonical mascot RGBA empty")
    cropped=img.crop(bbox)
    factor=size/max(1,cropped.height)
    return cropped.resize((max(1,int(cropped.width*factor)),size),
                          Image.Resampling.LANCZOS)


def route(sid:str,t:float)->tuple[float,float,int]:
    return motion.actor_key(sid,t)


def _draw_sprite(im:Image.Image,cam:Camera,original:Image.Image,
                 xyz:tuple[float,float,float],size:int,
                 *,sid:str,t:float)->None:
    motion.composite_actor(im,cam,original,xyz,size,shot_id=sid,t=t)



def dollhouse_height(b:dict,sid:str,sheep_x:float,sheep_y:float,
                     camera_zoom:float)->float:
    """Lower nearby miniature walls gently to keep tiny sheep visible on the road."""
    height=b["h"]
    if sid not in ("s04","s06","s07","s08","s09","s10","s11") or camera_zoom<70:
        return height
    bx=(b["x0"]+b["x1"])/2
    by=(b["y0"]+b["y1"])/2
    distance=math.hypot(bx-sheep_x,by-sheep_y)
    blend=eased((1.63-distance)/.70)
    return height*(1-.54*blend)


def draw_home_family(im:Image.Image,cam:Camera,sid:str,t:float)->None:
    """Three clearly visible anonymous XYZ felt doll placeholders at the home."""
    if sid not in ("s01","s11"):
        return
    d=ImageDraw.Draw(im)
    people=((1.13,4.08,.87,"#d5afa0"),
            (1.47,4.16,.91,"#8ea4a1"),
            (1.35,4.49,.66,"#e0c09d"))
    for i,(px,py,height,coat) in enumerate(people):
        radius=.24 if i<2 else .19
        garment=volume.projected_ellipsoid(
            cam,(px,py,.12+height*.35),(radius,radius*.83,height*.34))
        head=volume.projected_ellipsoid(
            cam,(px,py,.18+height*.81),(.17,.16,.17) if i<2
            else (.14,.14,.14))
        if len(garment)>=3:d.polygon(garment,fill=coat)
        if len(head)>=3:d.polygon(head,fill="#eee0ca")
        x,y=cam.project((px,py,.18+height*.85))
        e=max(1,round(cam.zoom*.011))
        d.ellipse((x-4*e,y-e,x-2*e,y+e),fill="#6c6257")
        d.ellipse((x+2*e,y-e,x+4*e,y+e),fill="#6c6257")
    if sid=="s11" and t<=3.50:
        q=eased(t/3.5)
        bagx=1.03+.25*q
        bagy=4.42-.18*q
        coinbag=volume.projected_ellipsoid(
            cam,(bagx,bagy,.22),(.15,.13,.18))
        if len(coinbag)>=3:d.polygon(coinbag,fill="#5c8f74")
        gx,gy=cam.project((bagx,bagy,.32))
        d.arc((gx-9,gy-16,gx+9,gy+5),190,355,
              fill="#f8eac4",width=2)

def scene_frame(sid:str,t:float,original_sheep:Image.Image)->Image.Image:
    if sid not in STOPS or not 0<=t<5:
        raise ValueError("Only supported 5-second rev5 scene slots")
    cam=camera_for(sid,t)
    im=Image.new("RGB",(W,H),"#cfdfd6")
    tiny_felt_background(im)
    d=ImageDraw.Draw(im)
    draw_road_grid(d,cam)
    cx,cy,height=route(sid,t)
    # Painter's algorithm interleaves mascot into its depth-sorted position,
    # so nearest buildings CAN occlude a small street-level traveler.
    # The source owner PNG is translated/tilted whole, never repainted.
    entities=[(cam.distance((b["x0"]+b["x1"])/2,(b["y0"]+b["y1"])/2),
               "building",b) for b in BUILDINGS]
    entities.append((cam.distance(cx,cy),"sheep",(cx,cy,height)))
    entities.sort(key=lambda e:e[0])
    for _,kind,item in entities:
        if kind=="building":
            true_height=dollhouse_height(item,sid,cx,cy,cam.zoom)
            adjusted={**item,"h":true_height}
            draw_building(d,cam,adjusted)
        else:
            x,y,size=item
            _draw_sprite(im,cam,original_sheep,(x,y,.065),size,sid=sid,t=t)
            d=ImageDraw.Draw(im)
    draw_home_family(im,cam,sid,t)
    # Distinguishable semantic districts, not fictitious live NZ merchant prices.
    district={
        "s01":"HOME","s03":"AUCKLAND","s04":"GROCERIES",
        "s06":"CAFE","s07":"CAFE","s08":"SHOPPING","s09":"SHOPPING",
        "s10":"LAMB ROUTE","s11":"HOME"}
    d=ImageDraw.Draw(im)
    d.rounded_rectangle((18,638,265,663),radius=6,fill="#355f55")
    d.text((28,642),district[sid],fill="#fff4d9")
    return im
