import uuid

import pytest

from app.store import Store
from app.api import create_app
from fastapi.testclient import TestClient
from conftest import make_settings


def finish(store, status='done', client='a', estimate=None, source='explicit'):
    jid = uuid.uuid4().hex
    store.create(jid, 'template', {'description': 'A useful part', 'who_for': 'Me'}, client)
    result = {'part_name': 'Useful part', 'pieces': [], 'files': []}
    if estimate is not None:
        result['estimate'] = estimate
    store.update(jid, plan={'source': source}, result=result)
    store.update(jid, status=status, error='Reason' if status != 'done' else None)
    return jid


@pytest.mark.parametrize('status', ['done', 'declined', 'failed'])
def test_terminal_saved_and_deduplicated(tmp_path, status):
    store = Store(tmp_path)
    jid = finish(store, status)
    store.save_history(jid)
    row, = store.history('a')
    assert row['status'] == status
    assert row['title'] == 'Useful part'
    assert row['result']['part_name'] == 'Useful part'
    store.close()


def test_restart_and_cleanup(tmp_path):
    store = Store(tmp_path)
    jid = finish(store)
    store.delete(jid)
    store.close()
    store = Store(tmp_path)
    row, = store.history('a')
    assert row['job_id'] == jid
    assert not row['files_available']
    store.close()


def test_isolation_and_delete(client):
    store = client.app.state.store
    a, b = finish(store, client='a'), finish(store, client='b')
    h = {'X-Client-Id': 'a'}
    assert [r['job_id'] for r in client.get('/api/v1/history', headers=h).json()['rows']] == [a]
    assert client.get(f'/api/v1/history/{b}', headers=h).status_code == 404
    assert client.get('/api/v1/stats', headers=h).json()['total_requests'] == 1
    assert client.delete('/api/v1/history', headers=h).json()['deleted'] == 1
    assert store.history('b')[0]['job_id'] == b
    assert not store.history('a')


def test_empty_and_missing_estimates(tmp_path):
    store = Store(tmp_path)
    s = store.history_stats('a')
    assert s['total_requests'] == 0
    assert s['filament_g']['value'] is None
    finish(store)
    finish(store, estimate={'filament_g': 12, 'print_minutes': 30})
    finish(store, estimate={'filament_g': 8, 'source': 'PrusaSlicer-test'})
    s = store.history_stats('a')
    assert s['filament_g'] == dict(value=20, rows=2, excluded=1, sliced=1, estimated=1, label='sliced and estimated')
    assert s['print_minutes']['value'] == 30
    assert s['print_minutes']['excluded'] == 2
    assert len(s['designs_per_day']) == 14
    store.close()


def test_broken_history_does_not_fail_job(client, monkeypatch, caplog):
    def broken(*args):
        raise RuntimeError('disk full')
    monkeypatch.setattr(client.app.state.store, 'save_history', broken)
    response = client.post('/api/v1/parts/zipper-pull/build?wait=60', json={})
    assert response.status_code == 200
    assert response.json()['status'] == 'done'
    assert 'Could not save history' in caplog.text


def test_anonymous_and_cors(client):
    finish(client.app.state.store, client='')
    assert client.get('/api/v1/history').json()['total'] == 1
    assert client.get('/health').json()['history'] == {'store': 'sqlite', 'rows': 1}


def test_real_job_persists_across_app_restart(tmp_path):
    settings = make_settings(tmp_path)
    with TestClient(create_app(settings)) as c:
        r = c.post('/api/v1/parts/zipper-pull/build?wait=60', json={}, headers={'X-Client-Id': 'persistent'})
        assert r.json()['status'] == 'done'
        jid = r.json()['id']
    with TestClient(create_app(settings)) as c:
        row = c.get(f'/api/v1/history/{jid}', headers={'X-Client-Id': 'persistent'}).json()
        assert row['files_available']
        assert row['job']['result']['estimate']['filament_g'] == row['filament_g']


def test_stats_sources_models_recipients_and_ai_time(tmp_path):
    store = Store(tmp_path)
    jid = uuid.uuid4().hex
    store.create(jid, 'design', {'description': 'Grip', 'who_for': 'Parent'}, 'a')
    store.update(jid, plan={'source': 'design'}, result={'design': {'models': ['test-model'], 'attempts': 2, 'reviewed': True}, 'pieces': [], 'files': []})
    store.update(jid, status='done')
    finish(store, source='cache')
    finish(store, source='fallback')
    stats = store.history_stats('a')
    assert stats['sources'] == {'ai': 1, 'cache': 1, 'fallback': 1}
    assert stats['models'] == {'test-model': 1}
    assert stats['who_for'] == {'Parent': 1, 'Me': 2}
    assert stats['most_common_who_for'] == 'Me'
    assert stats['average_ai_design_seconds']['rows'] == 1
    assert stats['average_ai_design_seconds']['value'] is not None
    assert sum(d['count'] for d in stats['designs_per_day']) == 3
    store.close()


def test_history_rate_limit_and_client_header_preflight(make_client):
    client = make_client(rate_limit_per_min=1)
    assert client.get('/api/v1/history', headers={'X-Client-Id': 'a'}).status_code == 200
    # Changing the browser UUID cannot bypass the IP-based rate limit.
    assert client.get('/api/v1/stats', headers={'X-Client-Id': 'b'}).status_code == 429
    response = client.options('/api/v1/history', headers={'Origin': 'http://localhost:5500', 'Access-Control-Request-Method': 'GET', 'Access-Control-Request-Headers': 'X-Client-Id'})
    assert response.status_code == 200
    assert 'X-Client-Id' in response.headers['access-control-allow-headers']
