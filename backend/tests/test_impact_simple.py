"""The simple statistics summary: store price vs printing, per-gram carbon, and the store-price input."""
import pytest

from app.impact import load_carbon, simple_summary
from tests.test_impact import persist


def summary(**kw):
    base = dict(material_key='PLA', mass_g=35, failure_rate=0, cost_total=50.0, filament_cost=30.0, electricity_cost=2.0,
                store_price=200.0, store_source={'kind': 'you'}, minutes=60)
    base.update(kw)
    return simple_summary(load_carbon(), **base)


def test_pla_35g_matches_the_paper_figures():
    c = summary()['carbon']
    assert c['material'] == pytest.approx(0.08) and c['printing'] == pytest.approx(0.06)
    assert c['print'] == pytest.approx(0.14) and c['material_specific'] is True


def test_carbon_scales_with_weight():
    one, two = summary(mass_g=10)['carbon'], summary(mass_g=20)['carbon']
    assert two['print'] == pytest.approx(2*one['print']) and two['store'] == pytest.approx(2*one['store'])


def test_failed_print_allowance_is_added():
    c = summary(failure_rate=0.2)['carbon']
    assert c['failed'] == pytest.approx(0.14*0.25) and c['print'] == pytest.approx(0.14/0.8)


def test_store_carbon_uses_the_paper_average_per_gram():
    # 12-35 kg CO2e over 1,500-4,000 g: midpoint 23.5 kg / 2,750 g.
    assert summary(mass_g=100)['carbon']['store'] == pytest.approx(100*23.5/2750)


def test_other_materials_are_flagged_as_pla_average():
    assert summary(material_key='TPU')['carbon']['material_specific'] is False


def test_cost_saving_and_percentage():
    c = summary()['cost']
    assert c['saved'] == pytest.approx(150) and c['percent'] == pytest.approx(75) and c['other'] == pytest.approx(18)


def test_no_store_price_means_no_comparison_not_a_made_up_one():
    c = summary(store_price=None, store_source=None)['cost']
    assert c['store'] is None and c['saved'] is None and c['percent'] is None


def test_dearer_than_store_is_reported_as_negative_saving():
    assert summary(store_price=40.0)['cost']['saved'] == pytest.approx(-10)


def test_missing_mass_gives_no_carbon_and_missing_cost_gives_no_cost():
    s = summary(mass_g=None, cost_total=None)
    assert s['carbon'] is None and s['cost'] is None


def test_store_price_endpoint_merges_and_clears(client):
    job_id = persist(client.app.state.store)
    headers = {'X-Client-Id': 'a'}
    r = client.post(f'/api/v1/history/{job_id}/store-price', json={'price_inr': 250}, headers=headers)
    assert r.status_code == 200 and r.json()['report']['simple']['cost']['store'] == 250
    assert r.json()['report']['simple']['cost']['store_source'] == {'kind': 'you'}
    r = client.post(f'/api/v1/history/{job_id}/store-price', json={'price_inr': None}, headers=headers)
    assert r.json()['report']['simple']['cost']['store_source'] != {'kind': 'you'}
    assert client.post(f'/api/v1/history/{job_id}/store-price', json={'price_inr': -1}, headers=headers).status_code == 422


def test_history_summaries_cover_done_designs_only(client):
    jid = persist(client.app.state.store)
    headers = {'X-Client-Id': 'a'}
    out = client.get('/api/v1/history-summaries', headers=headers).json()
    assert set(out) == {jid} and out[jid]['carbon']['print'] > 0 and out[jid]['cost']['print'] > 0
    assert client.get('/api/v1/history-summaries', headers={'X-Client-Id': 'someone-else'}).json() == {}
    client.post(f'/api/v1/history/{jid}/store-price', json={'price_inr': 999}, headers=headers)
    assert client.get('/api/v1/history-summaries', headers=headers).json()[jid]['cost']['store'] == 999
