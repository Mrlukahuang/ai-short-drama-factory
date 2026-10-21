"""G4/R4.4: ONE owner-triggered REAL Omni s02 lamb-run, not a full episode.

First successful public city plate used 9:16 and no references. This job uses
the real image+text SDK bridge and original canonical sheep PNG, verified by SHA.
The paid path is only available by an explicit manual GitHub workflow dispatch
after cost, transfer, Google retention and invoice acknowledgments. No retries.
"""
from __future__ import annotations

import argparse
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import time

from PIL import Image

from drama_factory.pipeline.omni_media_envelope import prepare_offline_omni_envelope
from drama_factory.pipeline.visual_media_admission import (
    PLAN_SCHEMA, digest_json, issue_operator_grant,
)
from drama_factory.providers.google_omni_video import (
    GoogleOmniVideoProvider, VideoCallDisabled,
)

ROOT = Path(__file__).resolve().parents[1]
PILOT = ROOT / "config/pilots/citydiscount_coin_hunt_1080x1440_v2.json"
ASSETS = ROOT / "assets/citydiscount/v1"
INVENTORY = ASSETS / "character_views_inventory.json"
MODEL = "gemini-omni-1.1-flash"
SHOT = "s02"
MAX_RESERVE_USD = Decimal("2.00")
MAX_NZ_DAY_USD = Decimal("5.00")
PREVIEW = "PREVIEW_ONLY"
PAID = "GENERATE_ONE_S02_PAID_WITH_OWNER_IMAGE"

# The English prompt avoids unverified prices, branding hallucinations and
# rights-uncleared logo transmission. Exact logo remains post-production only.
PROMPT = (
    "ONE single continuous 5-second 9:16 animated video; warm handcrafted "
    "needle-felted miniature Auckland, New Zealand. In a wide portrait city "
    "view, the EXACT SMALL CityDiscount sheep from the supplied image reference "
    "runs joyfully on its tiny feet along the cobblestone wool-felt street, "
    "carrying a tiny felt shovel and a small shoulder satchel. Keep the "
    "character identity perfectly consistent with the image reference: "
    "the same BIG ROUND BRIGHT EYES, recognizable face, wool texture, body, "
    "palette and proportions; DO NOT make the eyes smaller or invent a "
    "different lamb. The little lamb stays only 15–22% of frame height, "
    "never above 27%. Background: softly recognizable felt Sky Tower, "
    "Auckland waterfront, marina with felt sailboats, fluffy trees and "
    "all buildings, people, props, streets and clouds made of stitched wool. "
    "Camera smoothly tracks behind and then 3/4 front beside the running sheep. "
    "Clear two or three little hops and visible forward displacement: "
    "the sheep REALLY RUNS, not a static postcard or still with camera pan. "
    "Feel-good stop-motion fairy-tale adventure, smooth continuous physical "
    "character movement with soft felt footstep and gentle plucked-music sounds. "
    "NO readable signs, logos, CD words, pricing, actual merchant claims, "
    "fake gold coins, cutaways, hard camera cuts or subtitles. "
    "No speech, no synthetic Mandarin narration."
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _money(text: str) -> Decimal:
    try:
        x = Decimal(text)
    except (ValueError, TypeError, InvalidOperation) as exc:
        raise VideoCallDisabled("Declared NZ-day USD spend invalid") from exc
    if not x.is_finite() or x < 0:
        raise VideoCallDisabled("Declared NZ-day USD spend invalid")
    return x


def _preflight(*, spent_today_usd: str, paid: bool, confirmation: str,
               rights_confirmed: bool, google_transfer_confirmed: bool,
               google_terms_accepted: bool, invoice_verified: bool) -> tuple[dict,dict]:
    spent = _money(spent_today_usd)
    if spent + MAX_RESERVE_USD > MAX_NZ_DAY_USD:
        raise VideoCallDisabled("USD 2 reserve exceeds remaining USD 5 NZ-day budget")
    if confirmation not in {PREVIEW,PAID}:
        raise VideoCallDisabled("Unrecognized explicit single-shot intent")
    if paid and confirmation != PAID:
        raise VideoCallDisabled("Owner did not select paid s02 option")
    if not paid and confirmation != PREVIEW:
        raise VideoCallDisabled("Preview must use PREVIEW_ONLY")
    if paid and not all((rights_confirmed, google_transfer_confirmed,
                         google_terms_accepted, invoice_verified)):
        raise VideoCallDisabled(
            "Paid mode requires verified invoice and independent owner rights/"
            "Google transfer/provider-retention approvals"
        )
    raw=PILOT.read_bytes()
    doc=json.loads(raw.decode("utf-8"))
    if (doc.get("project")!="CityDiscount" or doc.get("revision")!=4
            or doc.get("format",{}).get("width")!=1080
            or doc.get("format",{}).get("height")!=1440
            or doc.get("format",{}).get("aspect_ratio")!="3:4"
            or doc.get("format",{}).get("shot_count")!=12
            or doc.get("shots",[{},{}])[1].get("shot_id")!="s02"
            or doc["shots"][1].get("storybeat")!="mission"
            or doc.get("controls",{}).get("publish_approved") is not False
            or doc.get("controls",{}).get("g4_exit_approved") is not False):
        raise VideoCallDisabled("Owner s02 creative, 3:4 or release boundary changed")
    return doc, {
        "schema":"g4-citydiscount-s02-real-omni-once.v1",
        "shot_id":"s02","owner_story_sha256":_sha(raw),
        "original_subject":"canonical_owned_citydiscount_sheep_png_front",
        "output_target_px":[1080,1440],"output_ratio":"3:4",
        "model_request_ratio":"9:16",
        "model_request_resolution":"360p",
        "native_3_4_model_output":False,
        "reframe_method":"aspect-preserving fore; blurred full-bleed side extension",
        "not_native_1080p_model":True,
        "max_run_usd_operator_reserve":str(MAX_RESERVE_USD),
        "nz_day_before_run_operator_declared_usd":str(spent),
        "google_hard_invoice_cap":False,
        "prior_invoice_reconciled_by_operator":invoice_verified,
        "provider_billing_unverified":True,
        "actual_fee_usd":None,
        "model_calls":0,"output_media":"not_generated",
        "source_pngs_transmitted":0,
        "rights_owner_assertion":rights_confirmed,
        "google_image_transfer_owner_approved":google_transfer_confirmed,
        "google_provider_retention_terms_accepted":google_terms_accepted,
        "publication_approved":False,"g4_exit_approved":False,
        "model":MODEL,"prompt_sha256":_sha(PROMPT.encode("utf-8")),
        "source_video_real_model":False,
        "no_automatic_retry":True,
    }


def _canonical_png() -> tuple[bytes,dict]:
    inventory=json.loads(INVENTORY.read_text("utf-8"))
    record=next((x for x in inventory.get("images",[])
                 if x.get("role")=="front"),None)
    if record is None:
        raise VideoCallDisabled("Canonical sheep front inventory missing")
    path=ASSETS/"character_views"/record["filename"]
    if path.is_symlink() or not path.is_file():
        raise VideoCallDisabled("Canonical sheep source unavailable")
    source=path.read_bytes()
    if _sha(source)!=record["source_sha256"]:
        raise VideoCallDisabled("Original sheep PNG source bytes changed")
    # Normalize RGBA to PNG RGB without changing facial geometry.
    with Image.open(io.BytesIO(source)) as im:
        if im.format!="PNG" or im.mode!="RGBA":
            raise VideoCallDisabled("Original canonical sheep must be RGBA PNG")
        im.load()
        rgba=im.copy()
    # Preserve the ENTIRE canonical original image, no face reconstruction.
    bbox=rgba.getchannel("A").getbbox()
    if bbox is None:
        raise VideoCallDisabled("Original sheep is empty")
    crop=rgba.crop(bbox)
    crop.thumbnail((768,768),Image.Resampling.LANCZOS)
    white=Image.new("RGBA",crop.size,"#f9f1e4")
    white.alpha_composite(crop)
    data=io.BytesIO()
    white.convert("RGB").save(data,format="PNG",optimize=True)
    payload=data.getvalue()
    if len(payload)>2_000_000:
        raise VideoCallDisabled("Prepared character PNG exceeds inline policy")
    return payload,{
        "role":"front",
        "original_png_sha256":record["source_sha256"],
        "sanitized_rgb_sha256":_sha(payload),
        "sanitized_pixel_dimensions":list(crop.size),
        "eyes_retouched":False,
        "identity_artwork_regenerated":False,
    }


def prepare_one_shot(*, spent_today_usd: str, paid: bool, confirmation: str,
                     rights_confirmed: bool, google_transfer_confirmed: bool,
                     google_terms_accepted: bool, invoice_verified: bool):
    script,receipt=_preflight(
        spent_today_usd=spent_today_usd,paid=paid,confirmation=confirmation,
        rights_confirmed=rights_confirmed,
        google_transfer_confirmed=google_transfer_confirmed,
        google_terms_accepted=google_terms_accepted,
        invoice_verified=invoice_verified)
    rgb,origin=_canonical_png()
    receipt["original_mascot"]=origin
    # Existing FND-02 accepts independent per-shot HMAC grants and validates
    # PNG bytes. A manual paid workflow dispatch is the operator action; the
    # signing key is ephemeral to this exact process, never logged or saved.
    ref={
        "role":"actor",
        "image":{
            "series_id":script["campaign_id"],"kind":"actor",
            "asset_id":"citydiscount-original-mascot-v1",
            "asset_version":origin["original_png_sha256"][:16],
            "view":"front","png_sha256":origin["sanitized_rgb_sha256"],
        },
    }
    plan={
        "schema":PLAN_SCHEMA,
        "series_id":script["campaign_id"],
        "model_submission_allowed":False,
        "provider_reference_applied":False,
        "shots":[{"shot_id":SHOT,"selected_references":[ref]}],
    }
    plan["plan_sha256"]=digest_json(plan)
    if not paid:
        return None,receipt
    from tempfile import TemporaryDirectory
    from pathlib import Path
    from drama_factory.pipeline.omni_media_envelope import OfflineOmniEnvelope
    # The signed operator grant, serialized reference and image bytes are
    # transient. No image data are persisted in JSON/logs/artifacts.
    key=secrets.token_bytes(48)
    expiry=int(time.time())+360
    grant=issue_operator_grant(
        plan,SHOT,[origin["sanitized_rgb_sha256"]],
        reviewer="manual-github-operator-s02",
        expiry_epoch=expiry,signing_key=key)
    with TemporaryDirectory() as tmp:
        path=Path(tmp)/"canonical_rgb_reference.png"
        path.write_bytes(rgb)
        envelope=prepare_offline_omni_envelope(
            plan,SHOT,original_prompt=PROMPT,
            reference_paths=[path],operator_grant=grant,
            verification_key=key,now_epoch=int(time.time()))
    receipt["request_fingerprint_sha256"]=envelope.receipt["request_fingerprint_sha256"]
    return envelope,receipt


def _ffprobe(path:Path)->dict:
    try:
        p=subprocess.run(["ffprobe","-v","error","-show_entries",
                          "format=duration,size:stream=codec_type,codec_name,width,height",
                          "-of","json",str(path)],check=True,
                         stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        return json.loads(p.stdout)
    except (OSError,ValueError,subprocess.CalledProcessError) as exc:
        raise VideoCallDisabled("FFprobe video validation failed") from exc


def _reframe_3_4(original:Path,output:Path)->dict:
    # 9:16 model -> 3:4 deliverable; blurred full-frame SIDE extension while
    # subject foreground remains unstretched. Exactly 1080x1440 H.264/AAC.
    filters=(
        "[0:v]split=2[base][subject];"
        "[base]scale=1080:1440:force_original_aspect_ratio=increase,"
        "crop=1080:1440,boxblur=30:5[bg];"
        "[subject]scale=1080:1440:force_original_aspect_ratio=decrease[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2:shortest=1,"
        "fps=24,format=yuv420p[v]"
    )
    args=["ffmpeg","-hide_banner","-loglevel","error","-y",
          "-i",str(original),"-filter_complex",filters,"-map","[v]",
          "-map","0:a:0?","-c:v","libx264","-preset","veryfast",
          "-crf","23","-c:a","aac","-b:a","128k",
          "-t","5","-movflags","+faststart",str(output)]
    try:
        subprocess.run(args,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    except (OSError,subprocess.CalledProcessError) as exc:
        raise VideoCallDisabled("Safe 3:4 FFmpeg reframe failed") from exc
    info=_ffprobe(output)
    if not (4.7<=float(info["format"]["duration"])<=5.2
            and any(s.get("codec_type")=="video"
                    and s.get("width")==1080 and s.get("height")==1440
                    for s in info["streams"])):
        raise VideoCallDisabled("True 1080x1440 3:4 output not verified")
    return info


def run_s02(*,output_dir:Path,spent_today_usd:str,
            paid:bool,confirmation:str,
            rights_confirmed:bool,google_transfer_confirmed:bool,
            google_terms_accepted:bool,invoice_verified:bool,
            provider=None, convert_video:bool=True)->dict:
    if output_dir.exists():
        raise VideoCallDisabled("One-shot output path already exists; no overwrite")
    envelope,receipt=prepare_one_shot(
        spent_today_usd=spent_today_usd,paid=paid,confirmation=confirmation,
        rights_confirmed=rights_confirmed,
        google_transfer_confirmed=google_transfer_confirmed,
        google_terms_accepted=google_terms_accepted,
        invoice_verified=invoice_verified)
    if paid and os.getenv("DRAMA_ENABLE_PAID_GENERATION")!="YES":
        raise VideoCallDisabled("Paid generation is not enabled")
    if paid and not os.getenv("GEMINI_API_KEY") and provider is None:
        raise VideoCallDisabled("GEMINI_API_KEY secret absent")
    output_dir.mkdir(parents=True,exist_ok=False)
    if not paid:
        (output_dir/"receipt.json").write_text(
            json.dumps(receipt,ensure_ascii=False,indent=2),"utf-8")
        return receipt
    source=output_dir/"s02_raw_omni_9x16.mp4"
    # One Google request. Even on timeout, NO retry.
    response=(provider or GoogleOmniVideoProvider()).generate_approved_reference_envelope(
        envelope,source,live_consent={
            "shot_id":SHOT,
            "request_fingerprint_sha256":envelope.receipt["request_fingerprint_sha256"],
            "source_rights_verified_by_operator":rights_confirmed,
            "external_model_transfer_approved":google_transfer_confirmed,
            "provider_retention_terms_accepted":google_terms_accepted,
            "already_spent_today_usd":spent_today_usd,
            "max_run_spend_usd":str(MAX_RESERVE_USD),
        })
    if (response.get("is_mock") is not False
            or response.get("model_calls")!=1 or not source.is_file()):
        raise VideoCallDisabled("No real media bytes returned; refuse fake success")
    # Do NOT label technically-successful character footage creative approved.
    receipt.update({
        "model_calls":1,"source_pngs_transmitted":1,
        "output_media":"real_omni_video_downloaded",
        "source_video_real_model":True,
        "source_video_sha256":_sha(source.read_bytes()),
        "source_video_media_qa":_ffprobe(source),
        "reference_image_count":response.get("reference_image_count"),
        "provider_task_id":response.get("provider_task_id"),
        "provider_reference_applied":response.get("provider_reference_applied"),
        "actual_fee_usd":None,"provider_billing_unverified":True,
    })
    if convert_video:
        target=output_dir/"s02_owner_1080x1440_3x4_NOT_FINAL.mp4"
        info=_reframe_3_4(source,target)
        receipt["reframed_media_qa"]=info
        receipt["reframed_video_sha256"]=_sha(target.read_bytes())
    (output_dir/"receipt.json").write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2),"utf-8")
    return receipt


def main(argv=None):
    p=argparse.ArgumentParser(description="CityDiscount s02 manual ONE image-reference Omni generation")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--nz-spend-today-usd",required=True)
    p.add_argument("--confirmation",choices=[PREVIEW,PAID],required=True)
    for option in ("rights-confirmed","google-transfer-confirmed",
                   "google-terms-accepted","invoice-verified"):
        p.add_argument("--"+option,action="store_true")
    x=p.parse_args(argv)
    try:
        result=run_s02(
            output_dir=x.out,spent_today_usd=x.nz_spend_today_usd,
            paid=x.confirmation==PAID,confirmation=x.confirmation,
            rights_confirmed=x.rights_confirmed,
            google_transfer_confirmed=x.google_transfer_confirmed,
            google_terms_accepted=x.google_terms_accepted,
            invoice_verified=x.invoice_verified)
    except (ValueError,RuntimeError,OSError) as exc:
        p.exit(2,"BLOCKED: "+exc.__class__.__name__+"\n")
    print(json.dumps({k:result[k] for k in (
        "shot_id","model_calls","output_media","actual_fee_usd",
        "publication_approved")},ensure_ascii=False))


if __name__=="__main__":
    main()
