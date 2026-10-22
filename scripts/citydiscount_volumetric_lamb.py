"""G4 CityDiscount local provisional *world-space 3D wool body* for little lamb.

The sheep's torso, neck, ears, wool tufts and four independently moving legs
have actual X/Y/Z geometry and are reprojected by the SAME 3D city camera.
The Owner's SHA-checked original sheep RGBA remains a small 2D facial/reference
texture overlay: this is a hybrid puppet, not an approved rigged 3D character,
and not an AI-generated performance or release-ready face/wardrobe.
"""
from __future__ import annotations

import math
from PIL import Image, ImageDraw

Vec=tuple[float,float,float]
SAMPLE_ANGLES=tuple((math.cos(i*math.tau/32), math.sin(i*math.tau/32))
                    for i in range(32))


def projected_ellipsoid(cam,center:Vec,radii:Vec)->tuple[tuple[int,int],...]:
    """Sample a true world-space volume silhouette; not a flat screen ellipse."""
    cx,cy,cz=center
    rx,ry,rz=radii
    points=[]
    for a,b in SAMPLE_ANGLES:
        for z in (-1.0,-.57,0.0,.57,1.0):
            scale=math.sqrt(max(0.0,1-z*z))
            points.append(cam.project((cx+rx*scale*a,cy+ry*scale*b,cz+rz*z)))
    return tuple(convex_hull(points))


def convex_hull(points:list[tuple[int,int]])->list[tuple[int,int]]:
    """Deterministic monotone 2D hull for projected XYZ wool volumes."""
    vertices=sorted(set(points))
    if len(vertices)<3:return vertices
    def cross(o,a,b):
        return (a[0]-o[0])*(b[1]-o[1])-(a[1]-o[1])*(b[0]-o[0])
    low=[]
    for point in vertices:
        while len(low)>1 and cross(low[-2],low[-1],point)<=0:low.pop()
        low.append(point)
    up=[]
    for point in reversed(vertices):
        while len(up)>1 and cross(up[-2],up[-1],point)<=0:up.pop()
        up.append(point)
    return low[:-1]+up[:-1]


def volumetric_lamb_frame(image:Image.Image,cam,world:Vec,
                          *,t:float,walking:bool)->dict:
    """Draw provisional 3D felt body with 4 moving legs, head and wool lumps.

    Projections change physically with the 3D city camera's azimuth/elevation.
    Returns explicit truth markers to avoid calling this a complete 3D model.
    """
    x,y,z=world
    if not all(math.isfinite(a) for a in world) or not math.isfinite(t):
        raise ValueError("Nonfinite 3D sheep geometry")
    d=ImageDraw.Draw(image)
    stride=math.sin(math.tau*2.3*t) if walking else 0.0
    bob=.055*max(0,math.sin(math.tau*2.3*t)) if walking else 0.0

    # Every limb has a distinct XYZ start/end and gait phase; it doesn't just
    # stretch/translate the flat sheep image across the city map.
    joints=[]
    for ix in (-1,1):
        for iy in (-1,1):
            hip=(x+ix*.26,y+iy*.19,z+.33+bob)
            phase=ix*iy*stride
            foot=(x+ix*.29 + .12*phase,y+iy*.20,z+.06+.11*max(0,phase))
            joints.append((hip,foot))
            ax,ay=cam.project(hip)
            bx,by=cam.project(foot)
            width=max(2,round(cam.zoom*.045))
            d.line((ax,ay,bx,by),fill="#c0ad93",width=width+2)
            d.line((ax,ay,bx,by),fill="#e9dec5",width=width)
            r=max(2,round(cam.zoom*.055))
            d.ellipse((bx-r,by-r//2,bx+r,by+r//2),fill="#968974")
    # Visible cross-section fur masses on a TRUE volumetric back, projected
    # into a convex silhouette that changes with camera angle.
    shell_center=(x,y,z+.43+bob)
    shell_radii=(.43,.32,.40)
    shadow=projected_ellipsoid(cam,shell_center,shell_radii)
    if len(shadow)>=3:d.polygon(shadow,fill="#baa58e")
    body=projected_ellipsoid(cam,(x-.04,y,z+.47+bob),(.39,.30,.35))
    if len(body)>=3:d.polygon(body,fill="#f2e9d7")
    clumps=((-0.24,-.11,.66),(-.25,.15,.68),(-.02,-.19,.76),
            (.08,.15,.78),(.23,-.08,.68),(.24,.13,.64),
            (-.23,.05,.39),(.09,-.25,.47),(.27,.22,.46))
    for n,(dx,dy,dz) in enumerate(clumps):
        p=projected_ellipsoid(cam,(x+dx,y+dy,z+dz+bob),
                              (.14,.14,.135))
        if len(p)>=3:
            d.polygon(p,fill="#fff5e5" if n%3 else "#e8decf")
    # True 3D head/ear volumes. The ORIGINAL Owner face image is later
    # composited, unredrawn, by existing citydiscount_street_motion.py.
    neck=projected_ellipsoid(cam,(x+.26,y-.03,z+.60+bob),(.18,.19,.24))
    face=projected_ellipsoid(cam,(x+.39,y-.03,z+.75+bob),(.20,.18,.20))
    if len(neck)>=3:d.polygon(neck,fill="#e8d9c5")
    if len(face)>=3:d.polygon(face,fill="#f0dcc7")
    for yy in (-.19,.17):
        ear=projected_ellipsoid(cam,(x+.28,y+yy,z+.86+bob),(.10,.09,.075))
        if len(ear)>=3:d.polygon(ear,fill="#d4bcae")
    return {
        "local_xyz_body_geometry":True,
        "four_xyz_jointed_gait_legs":len(joints)==4,
        "canonical_face_is_2d_source_overlay":True,
        "approved_rigged_3d_sheep":False,
        "body_world_position":(x,y,z),
    }
