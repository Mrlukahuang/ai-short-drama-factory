"""CityDiscount G4/R4.4 Owner-shot s05: ONE real 360p sheep double-dig.

Reuses the already proven s02 original-asset SHA verifier, Omni FND-02
signed-reference adapter and FFmpeg 3:4 postprocessing. Never auto-pays or
retries. A single five-second attempt cannot guarantee model action timing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import time
from tempfile import TemporaryDirectory

from drama_factory.pipeline.omni_media_envelope import prepare_offline_omni_envelope
from drama_factory.pipeline.visual_media_admission import (
    PLAN_SCHEMA, digest_json, issue_operator_grant,
)
from drama_factory.providers.google_omni_video import (
    GoogleOmniVideoProvider, VideoCallDisabled,
)
from citydiscount_s02_omni_reference_once import (
    ROOT, PILOT, MODEL, MAX_RESERVE_USD, MAX_NZ_DAY_USD,
    _money, _canonical_png, _sha, _ffprobe, _reframe_3_4,
)

SHOT="s05"
PREVIEW="PREVIEW_ONLY"
PAID="GENERATE_ONE_S05_PAID_WITH_OWNER_IMAGE"
PROMPT=(
    "ONE SINGLE CONTINUOUS FIVE-SECOND animated video in VERTICAL 9:16. "
    "Real stop-motion movement in a WIDE SHOT of a magical Auckland "
    "NEEDLE-FELTED miniature vegetable market. ALL the buildings, fruit, "
    "vegetables, market stalls, floor, sky, shovel, soil, and coins are wool "
    "and handmade stitched felt with tactile fuzzy fibres. The exact tiny "
    "CityDiscount sheep from the one approved owner-provided image reference, "
    "with SAME VERY LARGE ROUND BRIGHT EYES, same face, muzzle, ears, curly "
    "wool, scarf and proportions, stands next to a felt vegetable stall. "
    "Keep the sheep small (ideally 15–22% of video frame height, NEVER more "
    "than 27%) and fully visible including shovel at all times. "
    "TIMING IS CRITICAL: from 0.0 to 1.5 seconds the sheep LIFTS the "
    "tiny shovel and clearly DIGS THE GROUND ONCE, moving wool soil chunks. "
    "From 1.5 to 3.0 seconds the same sheep lifts and DIGS A DISTINCT SECOND "
    "TIME into the same little hole. ONLY AFTER THE SECOND DIG, at 3.0 seconds "
    "EXACTLY ONE SMALL GOLD FELT COIN APPEARS in that hole (not before) with "
    "a simple blank circular golden face; the sheep reacts happily, then "
    "at 4.0 seconds picks it up and puts that ONE coin into its tiny wool bag. "
    "The official verified CD coin lettering must be added in postproduction; "
    "do not draw any letters yourself. ONE coin ONLY, TWO clear digging "
    "motions ONLY, no extras. Clear limb movement, solid shovel contact, "
    "coherent character animation with continuous location and camera. "
    "No static slideshow, no frozen poses, no abrupt cut or scene switch, "
    "no camera zoom-in, no enlarged sheep, no identity or clothing changes. "
    "Warm felt light, whimsical soft felt footsteps, two separate shovel "
    "sounds and one soft magical coin chime; NO narration, subtitles, signs, "
    "numbers, shopping prices, promises of real deals or generated text."
)

def _preflight(*,spent_today_usd:str,paid:bool,confirmation:str,
               rights_confirmed:bool,google_transfer_confirmed:bool,
               google_terms_accepted:bool,invoice_verified:bool):
    if confirmation not in (PREVIEW,PAID) or paid!=(confirmation==PAID):
        raise VideoCallDisabled("Exactly one manually selected s05 mode required")
    if spent_today_usd.strip().upper()=="UNKNOWN":
        if paid:
            raise VideoCallDisabled("Google charges UNKNOWN; no s05 paid call allowed")
        spent=None
    else:
        spent=_money(spent_today_usd)
        if spent+MAX_RESERVE_USD>MAX_NZ_DAY_USD:
            raise VideoCallDisabled("USD 2 run reserve exceeds USD 5 NZ-day balance")
    if paid and not all((rights_confirmed,google_transfer_confirmed,
                         google_terms_accepted,invoice_verified)):
        raise VideoCallDisabled("Separate Owner/Google rights, retention and reconciled spend confirmation required")
    raw=PILOT.read_bytes()
    doc=json.loads(raw.decode("utf-8"))
    frame=doc["shots"][4]
    if (doc.get("project")!="CityDiscount" or doc.get("revision")!=4
            or doc["format"].get("width")!=1080
            or doc["format"].get("height")!=1440
            or doc["format"].get("aspect_ratio")!="3:4"
            or doc["format"].get("shot_count")!=12
            or frame.get("shot_id")!=SHOT
            or frame.get("storybeat")!="supermarket_dig"
            or frame.get("duration_seconds")!=5
            or frame.get("coins_newly_found")!=1
            or [p["event"] for p in frame.get("action_phases",[])]
               !=["first_shovel_dig","second_shovel_dig","single_CD_coin_found","pack_coin_and_depart"]
            or [p["relative_ms"] for p in frame["action_phases"]]
               !=[0,1500,3000,4000]
            or doc.get("controls",{}).get("publish_approved") is not False
            or doc.get("controls",{}).get("g4_exit_approved") is not False):
        raise VideoCallDisabled("Current owner s05 double dig creative contract changed")
    receipt={
        "schema":"g4-citydiscount-real-s05-once.v1",
        "shot_id":SHOT,"model":MODEL,
        "owner_story_sha256":_sha(raw),
        "owner_action_phases":frame["action_phases"],
        "target_px":[1080,1440],
        "source_request_aspect":"9:16",
        "source_request_resolution":"360p",
        "not_native_1080p":True,
        "postprocess":"nonstrretched central video, blurred side-fill 3:4",
        "coin_lettering_status":"blank model coin; genuine CD lettering requires separate verified deterministic postcomposition",
        "max_run_usd_operator_reserve":str(MAX_RESERVE_USD),
        "nz_day_before_run_operator_declared_usd":str(spent) if spent is not None else "UNKNOWN",
        "provider_has_hard_usd_cap":False,
        "actual_fee_usd":None,
        "provider_billing_unverified":True,
        "rights_owner_assertion":rights_confirmed,
        "google_image_transfer_owner_approved":google_transfer_confirmed,
        "google_provider_retention_terms_accepted":google_terms_accepted,
        "prior_invoice_reconciled_by_operator":invoice_verified,
        "model_calls":0,"output_media":"not_generated",
        "source_pngs_transmitted":0,"source_video_real_model":False,
        "publication_approved":False,"g4_exit_approved":False,
        "no_automatic_retry":True,
        "prompt_sha256":_sha(PROMPT.encode("utf-8")),
    }
    return doc,receipt


def prepare_s05(*,spent_today_usd:str,paid:bool,confirmation:str,
                rights_confirmed:bool,google_transfer_confirmed:bool,
                google_terms_accepted:bool,invoice_verified:bool):
    doc,receipt=_preflight(
        spent_today_usd=spent_today_usd,paid=paid,confirmation=confirmation,
        rights_confirmed=rights_confirmed,
        google_transfer_confirmed=google_transfer_confirmed,
        google_terms_accepted=google_terms_accepted,
        invoice_verified=invoice_verified)
    rgb,original=_canonical_png()  # Existing SHA verified source, original eyes unchanged.
    receipt["original_mascot"]=original
    if not paid:
        return None,receipt
    ref={"role":"actor","image":{
        "series_id":doc["campaign_id"],"kind":"actor",
        "asset_id":"citydiscount-original-mascot-v1",
        "asset_version":original["original_png_sha256"][:16],
        "view":"front","png_sha256":original["sanitized_rgb_sha256"]}}
    plan={
        "schema":PLAN_SCHEMA,
        "series_id":doc["campaign_id"],
        "model_submission_allowed":False,
        "provider_reference_applied":False,
        "shots":[{"shot_id":SHOT,"selected_references":[ref]}],
    }
    plan["plan_sha256"]=digest_json(plan)
    key=secrets.token_bytes(48)
    grant=issue_operator_grant(
        plan,SHOT,[original["sanitized_rgb_sha256"]],
        reviewer="manual-owner-github-s05",
        expiry_epoch=int(time.time())+360,
        signing_key=key)
    with TemporaryDirectory() as dirname:
        source=Path(dirname)/"canonical_sheep_rgb.png"
        source.write_bytes(rgb)
        envelope=prepare_offline_omni_envelope(
            plan,SHOT,original_prompt=PROMPT,
            reference_paths=[source],
            operator_grant=grant,verification_key=key,
            now_epoch=int(time.time()))
    receipt["request_fingerprint_sha256"]=envelope.receipt["request_fingerprint_sha256"]
    return envelope,receipt


def run_s05(*,output_dir:Path,spent_today_usd:str,paid:bool,confirmation:str,
            rights_confirmed:bool,google_transfer_confirmed:bool,
            google_terms_accepted:bool,invoice_verified:bool,
            provider=None,convert_video:bool=True):
    if output_dir.exists():
        raise VideoCallDisabled("Refuse s05 rerun/overwrite of existing attempt")
    envelope,receipt=prepare_s05(
        spent_today_usd=spent_today_usd,paid=paid,confirmation=confirmation,
        rights_confirmed=rights_confirmed,
        google_transfer_confirmed=google_transfer_confirmed,
        google_terms_accepted=google_terms_accepted,
        invoice_verified=invoice_verified)
    if paid and os.getenv("DRAMA_ENABLE_PAID_GENERATION")!="YES":
        raise VideoCallDisabled("Paid requests disabled")
    if paid and not os.getenv("GEMINI_API_KEY") and provider is None:
        raise VideoCallDisabled("Missing existing GitHub GEMINI_API_KEY secret")
    output_dir.mkdir(parents=True,exist_ok=False)
    if not paid:
        (output_dir/"receipt.json").write_text(
            json.dumps(receipt,ensure_ascii=False,indent=2),"utf-8")
        return receipt
    destination=output_dir/"s05_raw_omni_9x16.mp4"
    # Exactly ONE paid request; a timeout, malformed response or missing
    # MP4 must never trigger an automatic second provider request.
    output=(provider or GoogleOmniVideoProvider()).generate_approved_reference_envelope(
        envelope,destination,live_consent={
            "shot_id":SHOT,
            "request_fingerprint_sha256":envelope.receipt["request_fingerprint_sha256"],
            "source_rights_verified_by_operator":rights_confirmed,
            "external_model_transfer_approved":google_transfer_confirmed,
            "provider_retention_terms_accepted":google_terms_accepted,
            "already_spent_today_usd":spent_today_usd,
            "max_run_spend_usd":str(MAX_RESERVE_USD)})
    if output.get("is_mock") is not False or output.get("model_calls")!=1 or not destination.is_file():
        raise VideoCallDisabled("Real Omni source MP4 missing or fake")
    receipt.update({
        "model_calls":1,"source_pngs_transmitted":1,
        "reference_image_count":output.get("reference_image_count"),
        "provider_reference_applied":output.get("provider_reference_applied"),
        "provider_task_id":output.get("provider_task_id"),
        "output_media":"real_omni_video_downloaded",
        "source_video_real_model":True,
        "source_mp4_sha256":_sha(destination.read_bytes()),
        "source_mp4_ffprobe":_ffprobe(destination),
        "actual_fee_usd":None,
        "publication_approved":False,
    })
    if convert_video:
        final=output_dir/"s05_1080x1440_3x4_NOT_FINAL.mp4"
        receipt["reframed_media_qa"]=_reframe_3_4(destination,final)
        receipt["reframed_video_sha256"]=_sha(final.read_bytes())
    (output_dir/"receipt.json").write_text(
        json.dumps(receipt,ensure_ascii=False,indent=2),"utf-8")
    return receipt


def main():
    p=argparse.ArgumentParser(description="ONE Owner-launched real Omni s05 360p double shovel dig")
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--nz-spend-today-usd",required=True)
    p.add_argument("--confirmation",choices=[PREVIEW,PAID],required=True)
    for f in ("rights-confirmed","google-transfer-confirmed",
              "google-terms-accepted","invoice-verified"):
        p.add_argument("--"+f,action="store_true")
    x=p.parse_args()
    try:
        result=run_s05(
            output_dir=x.out,spent_today_usd=x.nz_spend_today_usd,
            paid=x.confirmation==PAID,confirmation=x.confirmation,
            rights_confirmed=x.rights_confirmed,
            google_transfer_confirmed=x.google_transfer_confirmed,
            google_terms_accepted=x.google_terms_accepted,
            invoice_verified=x.invoice_verified)
    except (ValueError,RuntimeError,OSError) as exc:
        p.exit(2,"BLOCKED: "+exc.__class__.__name__+"\n")
    print(json.dumps({
        k:result[k] for k in ("shot_id","model_calls","output_media",
                              "actual_fee_usd","publication_approved")},
        ensure_ascii=False))


if __name__=="__main__":
    main()
