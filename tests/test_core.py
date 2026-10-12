def test_original_status_machine(client):
    result = client.post('/api/v1/projects', json={"title":"重逢", "premise":"男女主再会", "visual_style":"live_action"})
    assert result.status_code == 201
    project_id = result.json()['project_id']
    ep = client.post(f'/api/v1/projects/{project_id}/episodes', json={
      "title":"第一集", "episode_number":1, "target_duration_seconds":6,
      "shots":[{"shot_id":"s1", "duration_seconds":6,"visual_description":"女主开门，看到男主"}]})
    assert ep.status_code == 201
    episode_id = ep.json()['episode_id']
    job = client.post(f'/api/v1/episodes/{episode_id}/productions')
    assert job.status_code == 201
    run = job.json()['production_id']
    assert client.post(f'/api/v1/productions/{run}/simulate').status_code == 409
    assert client.post(f'/api/v1/productions/{run}/approve-script').json()['status'] == 'character_review_pending'
    assert client.post(f'/api/v1/productions/{run}/approve-characters').json()['status'] == 'ready_for_video_generation'
    simulated = client.post(f'/api/v1/productions/{run}/simulate').json()
    assert simulated['status'] == 'mock_finished'
    assert simulated['video_created'] is False and simulated['paid_api_calls'] == 0


def test_default_google_model_and_upcoming_deprecation(client):
    cfg = client.get('/api/v1/models').json()
    assert cfg['default_video'] == 'gemini-omni-1.1-flash'
    assert cfg['video_models'][1]['production_eligible'] is False
    assert cfg['video_models'][1]['shutdown_date'] == '2026-10-22'


def test_novel_reading_and_rights_gate(client):
    novel = '序言\n' + '第一章 初遇\n她走进书店。\n' + '第二章 告白\n他说出了秘密。\n'
    r = client.post('/api/v1/novels/upload',
                    data={'title':'测试小说', 'rights_status':'pending'},
                    files={'file':('novel.txt',novel.encode('utf-8'),'text/plain')})
    assert r.status_code == 201
    book_id = r.json()['source_id']
    assert r.json()['chapter_count'] >= 2
    chapters = client.get(f'/api/v1/novels/{book_id}/chapters').json()
    assert any('第二章' in c['title'] for c in chapters)
    adapt = client.post(f'/api/v1/novels/{book_id}/adaptation-jobs', json={
        'desired_episodes': 8, 'target_seconds_per_episode': 90})
    assert adapt.status_code == 403


def test_owned_novel_creates_reserved_not_fake_success(client):
    r = client.post('/api/v1/novels/upload',
                    data={'title':'原创', 'rights_status':'owned', 'rights_scope':'screen_adaptation'},
                    files={'file':('book.txt',b'Chapter 1\nA person arrived.','text/plain')})
    assert r.status_code == 201
    source = r.json()['source_id']
    adapt = client.post(f'/api/v1/novels/{source}/adaptation-jobs', json={
        'desired_episodes': 3, 'target_seconds_per_episode': 60})
    assert adapt.status_code == 202
    assert adapt.json()['episodes_generated'] == 0
    assert adapt.json()['status'] == 'awaiting_adaptation_engine'


def test_licensed_requires_evidence_field(client):
    r = client.post('/api/v1/novels/upload',
       data={'title':'Licensed', 'rights_status':'licensed', 'rights_scope':'screen_adaptation'},
       files={'file':('novel.md',b'# Hello','text/markdown')})
    assert r.status_code == 422


def test_large_upload_rejected(client):
    r = client.post('/api/v1/novels/upload', data={'title':'too large'},
        files={'file':('x.txt', b'a'*(20*1024*1024+1),'text/plain')})
    assert r.status_code == 413


def test_invalid_ext(client):
    r = client.post('/api/v1/novels/upload', data={'title':'not allowed'},
        files={'file':('payload.exe', b'abc')})
    assert r.status_code == 415
