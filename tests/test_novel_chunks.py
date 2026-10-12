"""Novel chunk manifest correctness, idempotency and rights gates."""


def upload(client, rights="owned", scope="screen_adaptation", suffix="甲"):
    text = f"第一章 初遇\n{suffix}" + "花园里有一场对话。" * 700 + "\n第二章 变化\n" + "主人公作出决定。" * 300
    response = client.post(
        "/api/v1/novels/upload",
        data={"title": f"测试{suffix}", "rights_status": rights, "rights_scope": scope},
        files={"file": ("book.txt", text.encode("utf-8"), "text/plain")},
    )
    assert response.status_code == 201
    return response.json(), text.strip()


def test_chunk_preparation_is_idempotent_and_lossless(client):
    book, text = upload(client)
    endpoint = f"/api/v1/novels/{book['source_id']}/analysis"
    first = client.post(endpoint + "/prepare")
    assert first.status_code == 202, first.text
    assert first.json()["model_calls"] == 0
    assert first.json()["extraction_started"] is False
    assert first.json()["source_text_sent_to_provider"] is False
    chunks = client.get(endpoint + "/chunks").json()
    assert first.json()["chunk_count"] == len(chunks)
    assert len(chunks) > 2
    assert all(ch["status"] == "pending" for ch in chunks)
    assert all(ch["end_offset"] - ch["start_offset"] <= 4000 for ch in chunks)
    assert client.post(endpoint + "/prepare").json()["chunk_count"] == len(chunks)
    assert client.get(endpoint + "/chunks").json() == chunks
    # Prove every indexed character is covered, not just aggregate length.
    chapters = client.get(f"/api/v1/novels/{book['source_id']}/chapters").json()
    for chapter in chapters:
        selected = [ch for ch in chunks if ch["chapter_ordinal"] == chapter["ordinal"]]
        assert selected[0]["start_offset"] == chapter["start_offset"]
        assert selected[-1]["end_offset"] == chapter["end_offset"]
        for x, y in zip(selected, selected[1:]):
            assert x["end_offset"] == y["start_offset"]


def test_pending_rights_cannot_start_analysis_preparation(client):
    book, _ = upload(client, rights="pending", scope="")
    url = f"/api/v1/novels/{book['source_id']}/analysis"
    assert client.post(url + "/prepare").status_code == 403
    assert client.get(url + "/chunks").json() == []


def test_separate_novel_chunk_sets(client):
    a, _ = upload(client, suffix="A")
    b, _ = upload(client, suffix="B")
    for book in (a, b):
        assert client.post(f"/api/v1/novels/{book['source_id']}/analysis/prepare").status_code == 202
    chunks_a = client.get(f"/api/v1/novels/{a['source_id']}/analysis/chunks").json()
    chunks_b = client.get(f"/api/v1/novels/{b['source_id']}/analysis/chunks").json()
    assert {c["id"] for c in chunks_a}.isdisjoint({c["id"] for c in chunks_b})


def test_unknown_novel_returns_not_found(client):
    assert client.post("/api/v1/novels/bad/analysis/prepare").status_code == 404
    assert client.get("/api/v1/novels/bad/analysis/chunks").status_code == 404
