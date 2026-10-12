"""PR-01: explicit column/series scoping, versioned canon, backwards migration."""
import json
import sqlite3
from drama_factory.db import Database, DEFAULT_COLUMN_ID


def column(client, slug, style="live_action"):
    r = client.post('/api/v1/columns',json={
        'slug':slug, 'name':slug, 'default_visual_style':style})
    assert r.status_code == 201, r.text
    return r.json()['column_id']


def series(client, column_id, title):
    r=client.post(f'/api/v1/columns/{column_id}/series',json={
        'title':title, 'premise':'两个人重逢', 'visual_style':'live_action'})
    assert r.status_code == 201, r.text
    return r.json()['series_id']


def asset(client, series_id, kind, key, **spec):
    r=client.post(f'/api/v1/series/{series_id}/assets',json={
        'kind':kind,'key':key,'specification':spec})
    assert r.status_code==201, r.text
    return r.json()


def test_two_columns_and_two_series_can_share_names_but_not_assets(client):
    c1=column(client,'romance')
    c2=column(client,'mystery')
    s1=series(client,c1,'第一部')
    s2=series(client,c2,'第二部')
    assert {p['id'] for p in client.get(f'/api/v1/columns/{c1}/series').json()} == {s1}
    assert {p['id'] for p in client.get('/api/v1/projects',params={'column_id':c2}).json()} == {s2}
    a1=asset(client,s1,'actor','heroine',name='小雪',appearance='黑长发',identity_anchors=['左眉痣'])
    a2=asset(client,s2,'actor','heroine',name='小雪',appearance='黑短发',identity_anchors=['右眼痣'])
    assert a1['asset_id']!=a2['asset_id']
    assert a1['version']==a2['version']==1
    assert {a['id'] for a in client.get(f'/api/v1/series/{s1}/assets').json()} == {a1['asset_id']}
    bad=client.post(f'/api/v1/projects/{s1}/episodes',json={
        'title':'错引用','episode_number':1,'target_duration_seconds':6,
        'shots':[{'shot_id':'s1','duration_seconds':6,'visual_description':'走入客厅',
                  'character_ids':[a2['asset_id']]}]})
    assert bad.status_code==422
    ok=client.post(f'/api/v1/projects/{s1}/episodes',json={
        'title':'正确','episode_number':1,'target_duration_seconds':6,
        'shots':[{'shot_id':'s1','duration_seconds':6,'visual_description':'走入客厅',
                  'character_ids':[a1['asset_id']]}]})
    assert ok.status_code==201,ok.text


def test_series_in_same_column_remain_independent(client):
    cid=column(client,'drama')
    a=series(client,cid,'剧A')
    b=series(client,cid,'剧B')
    scene=asset(client,a,'scene','livingroom',name='客厅',location='上海',layout='左侧沙发')
    bad=client.post(f'/api/v1/projects/{b}/episodes',json={
        'title':'第一集','episode_number':1,'target_duration_seconds':5,
        'shots':[{'shot_id':'s1','duration_seconds':5,'visual_description':'进门',
                  'scene_id':scene['asset_id']} ]})
    assert bad.status_code==422


def test_asset_kinds_voice_binding_and_immutable_versions(client):
    c=column(client,'actors')
    s=series(client,c,'声音')
    v=asset(client,s,'voice','lead_voice',name='女主声线',voice_description='中低音')
    a=asset(client,s,'actor','lead',name='女主',appearance='干练',identity_anchors=['短发'],
            voice_asset_id=v['asset_id'])
    assert a['version']==1
    a2=asset(client,s,'actor','lead',name='女主',appearance='干练',identity_anchors=['短发','美人痣'],
             voice_asset_id=v['asset_id'])
    assert a2['version']==2 and a2['asset_id'] != a['asset_id']
    records=client.get(f'/api/v1/series/{s}/assets',params={'kind':'actor'}).json()
    assert [r['version'] for r in records]==[2,1]
    assert json.loads(records[1]['specification_json'])['identity_anchors']==['短发']
    other=series(client,c,'另一部')
    invalid=client.post(f'/api/v1/series/{other}/assets',json={'kind':'actor','key':'lead',
        'specification':{'name':'男主','appearance':'黑发','identity_anchors':['黑发'],
                         'voice_asset_id':v['asset_id']}})
    assert invalid.status_code==422
    wrong_kind=client.post(f'/api/v1/projects/{s}/episodes',json={
        'title':'错角色','episode_number':1,'target_duration_seconds':5,
        'shots':[{'shot_id':'s1','duration_seconds':5,'visual_description':'说话',
                  'character_ids':[v['asset_id']]}]})
    assert wrong_kind.status_code==422


def test_story_bible_versioned_per_series(client):
    c=column(client,'fantasy')
    s1=series(client,c,'世界1')
    s2=series(client,c,'世界2')
    body={'title':'世界设定','logline':'两人重逢','genre':'奇幻'}
    for _ in range(2):
        assert client.post(f'/api/v1/series/{s1}/story-bibles',json=body).status_code==201
    assert len(client.get(f'/api/v1/series/{s2}/story-bibles').json())==0
    assert [b['version'] for b in client.get(f'/api/v1/series/{s1}/story-bibles').json()]==[2,1]


def test_production_filters_isolate_column_and_series(client):
    ca=column(client,'scifi')
    cb=column(client,'historical')
    ids=[]
    for cid in [ca,cb]:
        sid=series(client,cid,'第一部')
        ep=client.post(f'/api/v1/projects/{sid}/episodes',json={
            'title':'第一集','episode_number':1,'target_duration_seconds':6,
            'shots':[{'shot_id':'s1','duration_seconds':6,'visual_description':'相遇'}]})
        assert ep.status_code==201
        run=client.post(f'/api/v1/episodes/{ep.json()["episode_id"]}/productions')
        ids.append((sid,run.json()['production_id']))
    assert len(client.get('/api/v1/productions').json())==2
    r=client.get('/api/v1/productions',params={'column_id':ca}).json()
    assert [x['id'] for x in r]==[ids[0][1]]
    assert client.get('/api/v1/productions',params={'column_id':ca,'series_id':ids[1][0]}).json()==[]
    assert client.get('/api/v1/productions',params={'series_id':ids[1][0]}).json()[0]['id']==ids[1][1]


def test_legacy_project_routes_use_default_column(client):
    r=client.post('/api/v1/projects',json={'title':'老项目','premise':'老接口'})
    assert r.status_code==201,r.text
    assert r.json()['column_id']==DEFAULT_COLUMN_ID
    assert any(x['id']==r.json()['project_id'] for x in client.get('/api/v1/projects').json())
    assert any(x['slug']=='default' for x in client.get('/api/v1/columns').json())


def test_legacy_sqlite_migrates_with_same_project_id(tmp_path):
    path=tmp_path/'legacy.db'
    with sqlite3.connect(path) as conn:
        conn.execute('''CREATE TABLE projects (id TEXT PRIMARY KEY,title TEXT NOT NULL,
           premise TEXT NOT NULL,visual_style TEXT NOT NULL,ratio TEXT NOT NULL,
           created_at TEXT NOT NULL)''')
        conn.execute("INSERT INTO projects VALUES ('proj_old','Test','Story','live_action','9:16','2026-01-01')")
    db=Database(path)
    assert db.one("SELECT column_id FROM projects WHERE id='proj_old'")['column_id']==DEFAULT_COLUMN_ID
    assert db.one('SELECT * FROM columns WHERE id=?',(DEFAULT_COLUMN_ID,))['slug']=='default'
    Database(path)  # repeated startup is idempotent
    assert db.one("SELECT COUNT(*) n FROM projects")['n']==1
    with db.connection() as conn:
        try:
            conn.execute("INSERT INTO projects (id,title,premise,visual_style,ratio,created_at) VALUES ('bad','bad','bad','live_action','9:16','2026')")
        except sqlite3.IntegrityError:
            pass
        else:
            assert False,'New rows cannot omit column_id after migration'


def test_invalid_column_slug_and_unsupported_foreign_key(client):
    c=column(client,'abc')
    assert client.post('/api/v1/columns',json={'slug':'abc','name':'duplicate'}).status_code==409
    assert client.post('/api/v1/columns',json={'slug':'a b','name':'invalid'}).status_code==422
    assert client.post('/api/v1/projects',json={'title':'bad','premise':'x','column_id':'missing'}).status_code==404
    assert client.post(f'/api/v1/columns/{c}/series',json={
        'title':'bad','premise':'x','column_id':'different'}).status_code==422


def test_novel_standalone_entry_remains_available(client):
    r=client.post('/api/v1/novels/upload',data={'title':'Standalone'},files={'file':('a.txt',b'Chapter 1\nabc')})
    assert r.status_code==201,r.text
    assert r.json()['ai_adaptation_started'] is False