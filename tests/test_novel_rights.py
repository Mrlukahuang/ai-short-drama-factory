"""Rights review versions, expiry, scope and offline-only enforcement."""


def upload(client, status="owned", scope="screen_adaptation"):
    data = {"title": "自己的故事", "rights_status": status, "rights_scope": scope}
    if status == "licensed":
        data["rights_reference"] = "LIC-001"
    response = client.post("/api/v1/novels/upload", data=data,
                           files={"file": ("x.txt", b"Chapter 1\nHello", "text/plain")})
    assert response.status_code == 201
    return response.json()["source_id"]


def review(decision="approved", external=False):
    return {
        "decision": decision, "reviewer_label": "内部版权审核员",
        "rights_holder": "持有人", "evidence_reference": "contract-ref-001",
        "valid_from": "2026-01-01", "valid_until": "2030-01-01",
        "territories": ["NZ", "AU"], "languages": ["zh"],
        "media_types": ["short_drama", "animation"],
        "allow_external_ai": external,
    }


def test_no_review_means_not_eligible(client):
    source = upload(client)
    status = client.get(f"/api/v1/novels/{source}/rights-eligibility")
    assert status.status_code == 200
    assert status.json()["eligible"] is False


def test_approved_rights_still_do_not_enable_paid_model_calls(client):
    source = upload(client)
    base = f"/api/v1/novels/{source}"
    recorded = client.post(base + "/rights-reviews", json=review(external=True))
    assert recorded.status_code == 201, recorded.text
    assert recorded.json()["model_calls_enabled"] is False
    allowed = client.get(base + "/rights-eligibility?territory=NZ&language=zh&media_type=short_drama&external_ai=true").json()
    assert allowed["eligible"] is True
    assert allowed["external_model_calls_enabled"] is False
    assert client.get("/health").json()["provider_calls_enabled"] is False


def test_scope_exclusions_and_ai_permission(client):
    source = upload(client)
    base = f"/api/v1/novels/{source}"
    assert client.post(base + "/rights-reviews", json=review()).status_code == 201
    assert client.get(base + "/rights-eligibility?territory=US").json()["eligible"] is False
    assert client.get(base + "/rights-eligibility?language=en").json()["eligible"] is False
    assert client.get(base + "/rights-eligibility?media_type=film").json()["eligible"] is False
    assert client.get(base + "/rights-eligibility?external_ai=true").json()["eligible"] is False
    assert client.get(base + "/rights-eligibility?external_ai=false").json()["eligible"] is True


def test_latest_rejection_revokes_prior_review(client):
    source = upload(client)
    base = f"/api/v1/novels/{source}"
    assert client.post(base + "/rights-reviews", json=review(external=True)).json()["version"] == 1
    assert client.post(base + "/rights-reviews", json=review("rejected")).json()["version"] == 2
    current = client.get(base + "/rights-eligibility").json()
    assert current["eligible"] is False
    assert current["active_review_version"] == 2
    assert len(client.get(base + "/rights-reviews").json()) == 2


def test_unconfirmed_source_cannot_be_approved(client):
    source = upload(client, status="pending", scope="")
    assert client.post(f"/api/v1/novels/{source}/rights-reviews", json=review()).status_code == 403


def test_bad_date_window_and_unrecognized_values(client):
    source = upload(client)
    base = f"/api/v1/novels/{source}"
    value = review()
    value["valid_from"] = "2031-01-01"
    assert client.post(base + "/rights-reviews", json=value).status_code == 422
    value = review()
    value["territories"] = ["NZ", "NZ"]
    assert client.post(base + "/rights-reviews", json=value).status_code == 422
    assert client.get(base + "/rights-eligibility?media_type=unsupported").status_code == 422


def test_expired_grant_and_license_reference(client):
    source = upload(client, status="licensed")
    value = review(external=True)
    value["valid_until"] = "2026-01-02"
    assert client.post(f"/api/v1/novels/{source}/rights-reviews", json=value).status_code == 201
    assert client.get(f"/api/v1/novels/{source}/rights-eligibility").json()["eligible"] is False


def test_book_reviews_do_not_leak_across_sources(client):
    a, b = upload(client), upload(client)
    assert client.post(f"/api/v1/novels/{a}/rights-reviews", json=review()).status_code == 201
    assert client.get(f"/api/v1/novels/{b}/rights-reviews").json() == []
    assert client.get(f"/api/v1/novels/{b}/rights-eligibility").json()["eligible"] is False
