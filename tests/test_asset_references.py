"""Reference material provenance and cross-series safety tests."""


def setup(client, suffix="A"):
    project = client.post("/api/v1/projects", json={
        "title": f"剧{suffix}", "premise": "真实演员资产管理",
    }).json()["series_id"]
    actor = client.post(f"/api/v1/series/{project}/assets", json={
        "kind": "actor", "key": "lead", "specification": {
            "name": "女主", "appearance": "深色短发", "identity_anchors": ["右眼角的痣"],
        },
    }).json()["asset_id"]
    voice = client.post(f"/api/v1/series/{project}/assets", json={
        "kind": "voice", "key": "lead_voice", "specification": {
            "name": "女主声音", "voice_description": "普通话偏低沉",
        },
    }).json()["asset_id"]
    return project, actor, voice


def reference(series_id, kind="face_reference"):
    return {
        "media_kind": kind,
        "storage_key": f"series/{series_id}/actors/lead-front.png",
        "sha256": "a" * 64,
        "provenance": "synthetic",
        "rights_reference": "GOOGLE-IMAGE-TERMS-2026",
        "model_id": "candidate-image-model",
    }


def test_reference_metadata_created_and_reviewed(client):
    sid, actor, _ = setup(client)
    url = f"/api/v1/series/{sid}/assets/{actor}/references"
    response = client.post(url, json=reference(sid))
    assert response.status_code == 201, response.text
    ref = response.json()
    assert ref["status"] == "pending_review"
    assert ref["media_uploaded"] is False
    assert client.post(url + "/" + ref["reference_id"] + "/approve",
                       json={"reviewed_by_operator": False, "reviewer_label": "人工审核"}).status_code == 422
    approved = client.post(url + "/" + ref["reference_id"] + "/approve",
        json={"reviewed_by_operator": True, "reviewer_label": "人工审核"})
    assert approved.status_code == 200, approved.text
    assert approved.json()["external_calls"] == 0
    assert client.get(url).json()[0]["status"] == "approved"
    assert client.post(url + "/" + ref["reference_id"] + "/approve",
        json={"reviewed_by_operator": True, "reviewer_label": "人工审核"}).status_code == 409
    assert client.post(url, json=reference(sid)).json()["version"] == 2
    assert len(client.get(url).json()) == 2
    assert client.get(url).json()[1]["status"] == "approved"


def test_cross_series_and_wrong_asset_type_rejected(client):
    sid, actor, voice = setup(client, "A")
    other, other_actor, _ = setup(client, "B")
    prefix = f"/api/v1/series/{sid}/assets/{actor}/references"
    assert client.post(f"/api/v1/series/{other}/assets/{actor}/references",
                       json=reference(other)).status_code == 404
    assert client.post(prefix, json=reference(other)).status_code == 422
    assert client.post(f"/api/v1/series/{sid}/assets/{voice}/references",
                       json=reference(sid)).status_code == 422
    right_voice = reference(sid, "voice_sample")
    right_voice["storage_key"] = f"series/{sid}/voices/lead.wav"
    assert client.post(f"/api/v1/series/{sid}/assets/{voice}/references",
                       json=right_voice).status_code == 201


def test_disallow_unsafe_paths_and_unconsented_real_people(client):
    sid, actor, _ = setup(client)
    url = f"/api/v1/series/{sid}/assets/{actor}/references"
    for bad in ("../face.jpg", "/abs/path.jpg", f"series/{sid}/../secret.jpg",
                f"series/{sid}//face.jpg", "http://example.com/a.jpg"):
        val = reference(sid)
        val["storage_key"] = bad
        assert client.post(url, json=val).status_code in (422, 404)
    real = reference(sid)
    real["provenance"] = "licensed_person"
    real["model_id"] = ""
    assert client.post(url, json=real).status_code == 422
    real["consent_reference"] = "SIGNED-CONSENT-01"
    assert client.post(url, json=real).status_code == 201


def test_external_calls_still_disabled(client):
    sid, actor, _ = setup(client)
    ref = client.post(f"/api/v1/series/{sid}/assets/{actor}/references",
                      json=reference(sid)).json()
    assert ref["media_uploaded"] is False
    assert client.get("/health").json()["provider_calls_enabled"] is False
