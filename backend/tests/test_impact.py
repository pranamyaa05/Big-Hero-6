"""Calculation fixtures below are synthetic test data, never production benchmarks."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import uuid

import httpx
import pytest
from pydantic import ValidationError

from app.impact import ImpactInputs, calculate, classify, freshness
from app.impact_sources import normalize, parse_offer, refresh_evidence, validate_evidence
from app.impact_service import get_report
from app.store import Store


def evidence(id='fixture', kind='benchmark', subject='drawer_knob', **data):
    return {'id':id,'kind':kind,'subject':subject,'title':'SYNTHETIC TEST FIXTURE; not a product claim',
            'url':'https://example.invalid/test-fixture','publisher':'Test suite only','region':'India',
            'retrieved_at':datetime.now(timezone.utc).isoformat(), 'publication_date':None,'version':'test-v1',
            'unit':{'benchmark':'INR/item','material_price':'INR/kg','grid_factor':'kg CO2e/kWh','filament_factor':'kg CO2e/kg filament'}.get(kind,'g'),
            'verified':True,'reliability':'test fixture','data':data}


def history_row(title='Broken drawer knob', material='PLA'):
    return {'job_id':uuid.uuid4().hex,'title':title,'request':title,'material':material,'filament_g':100,'print_minutes':60,'size_mm':[[21,21,27]],
            'result':{'pieces':[{'volume_cm3':80}], 'estimate':{'support_g':10,'source':'test slicer'}}}


def complete(**over):
    data = dict(material_price_inr_kg=1000, printer_watts=100, tariff_inr_kwh=10,
                labor_minutes=30,labor_inr_hour=120,machine_inr_hour=20,setup_inr=5,consumables_inr=2,
                postprocess_inr=3,failure_rate=.2,extra_print_waste_g=10,
                components=[dict(name='Test fastener',cost_inr=4,mass_g=5,co2e_kg=.1,provenance='Synthetic fixture')],
                delivery_inr=10,delivery_co2e_kg=.03,additional_process_co2e_kg=.02,
                filament_factor_id='filament',grid_factor_id='grid',benchmark_confirmed=True,
                notes='Synthetic test inputs only. Not a real manufacturing scenario.')
    data.update(over)
    return ImpactInputs(**data)


def test_three_metrics_bom_energy_failures_and_no_double_support():
    catalog = [evidence(price_inr=300,price_basis='retail',material_consumed_g=200,mass_basis='production_consumed',production_delivery_co2e_kg=1,carbon_boundary='cradle_to_delivered'),
               evidence('filament','filament_factor','pla',kg_co2e_kg=2,boundary='cradle_to_filament'),
               evidence('grid','grid_factor','India',kg_co2e_kwh=.5,boundary='life_cycle_electricity')]
    report = calculate(history_row(),catalog,complete())
    assert report['costs']['raw_filament_inr'] == 100
    assert report['costs']['printing_inr'] == 111
    assert report['costs']['production_inr'] == pytest.approx(253.25)
    assert report['costs']['delivered_inr'] == pytest.approx(263.25)
    assert report['manufacturing']['electricity_kwh'] == .1
    assert report['manufacturing']['expected_print_waste_g'] == pytest.approx(47.5)
    assert len(report['metrics']) == 3
    cost,carbon,mass=report['metrics']
    assert cost['difference'] == pytest.approx(46.75)
    assert carbon['reform3d'] == pytest.approx(.4875)
    assert mass['reform3d'] == pytest.approx(142.5)
    assert all(m['comparable'] and not m['verified_savings'] for m in report['metrics'])


@pytest.mark.parametrize('name,material,category,price',[
    ('Personalized spoon grip','TPU','utensil_grip',70),('Personalized pen grip','TPU','pen_grip',60),
    ('Broken drawer knob','PLA','drawer_knob',30),('Replacement phone case','TPU','phone_case',199),
    ('Appliance handle repair','PETG','appliance_handle',250)])
def test_entity_scenarios_are_functionally_distinct(name,material,category,price):
    row=history_row(name,material)
    assert classify(row)['category']==category
    catalog=[evidence('correct',subject=category,price_inr=price,price_basis='retail',compatibility='Test model' if category in ('phone_case','appliance_handle') else None),
             evidence('unrelated',subject='whole_appliance',price_inr=40000,price_basis='retail')]
    report=calculate(row,catalog,complete(compatibility='Test model'))
    assert report['benchmark']['id']=='correct'
    assert report['metrics'][0]['industry']==price
    assert report['metrics'][0]['comparable']
    assert report['material']==material


def test_ambiguous_and_unrelated_never_choose_expensive_whole_appliance():
    assert classify(history_row('spoon grip and drawer knob'))['category']=='unclassified'
    report=calculate(history_row('Appliance handle repair','PETG'),[evidence(subject='whole_appliance',price_inr=40000,price_basis='retail')],complete())
    assert report['benchmark'] is None
    assert not any(m['comparable'] for m in report['metrics'])


def test_cheapest_equivalent_and_government_price_basis():
    catalog=[evidence('expensive',price_inr=4000,price_basis='retail'),evidence('cheap',price_inr=30,price_basis='retail'),
             evidence('beneficiary',price_inr=0,price_basis='beneficiary'),evidence('procurement',price_inr=10,price_basis='procurement')]
    r=calculate(history_row(),catalog,complete())
    assert r['benchmark']['id']=='cheap'
    assert r['metrics'][0]['direction']=='higher'
    assert r['metrics'][0]['difference']<0


def test_missing_values_never_become_zero_or_full_manufacturing_cost():
    r=calculate(history_row(),[],ImpactInputs())
    assert r['costs']['production_inr'] is None
    assert r['costs']['printing_inr'] is None
    assert r['metrics'][1]['reform3d'] is None
    assert all(m['difference'] is None and m['percent'] is None for m in r['metrics'])
    assert r['costs']['missing_items']


def test_packaged_mass_and_mismatched_carbon_boundaries_are_not_comparisons():
    catalog=[evidence(price_inr=30,price_basis='retail',material_consumed_g=30,mass_basis='packaged',production_delivery_co2e_kg=1,carbon_boundary='cradle_to_grave')]
    r=calculate(history_row(),catalog,complete())
    assert not r['metrics'][1]['comparable']
    assert not r['metrics'][2]['comparable']


def test_phone_and_oem_need_exact_model_compatibility():
    e=evidence(subject='phone_case',price_inr=199,price_basis='retail',compatibility='iPhone 13')
    r=calculate(history_row('phone case','TPU'),[e],complete(compatibility='iPhone 14'))
    assert not r['metrics'][0]['comparable']
    del e['data']['compatibility']
    r=calculate(history_row('phone case','TPU'),[e],complete())
    assert not r['metrics'][0]['comparable']


def test_changed_material_does_not_reuse_filament_weight_or_print_time():
    r=calculate(history_row(),[],complete(material='TPU'))
    assert r['manufacturing']['filament_g'] is None
    assert r['manufacturing']['print_minutes'] is None
    assert r['costs']['production_inr'] is None


def test_solid_geometry_fallback_and_unknown_material():
    row=history_row();row['filament_g']=None
    r=calculate(row,[],ImpactInputs())
    assert r['manufacturing']['filament_g']==pytest.approx(80*1.24)
    assert 'fallback' in r['manufacturing']['mass_method']
    row['material']='Unknown'
    r=calculate(row,[],ImpactInputs())
    assert r['manufacturing']['filament_g'] is None


def test_input_validation_provenance_nan_negative_failure_and_typos():
    for data in ({'printer_watts':100},{'tariff_inr_kwh':-1,'notes':'fixture'}, {'failure_rate':1,'notes':'fixture'},
                 {'printer_watts':float('nan'),'notes':'fixture'}, {'typo_rate':1}):
        with pytest.raises(ValidationError): ImpactInputs(**data)


def test_units_freshness_and_source_validation():
    assert normalize(.65,'INR/g','INR/kg')==650
    assert normalize(0.02,'kg','g')==20
    assert normalize(700,'g CO2e/kWh','kg CO2e/kWh')==pytest.approx(.7)
    with pytest.raises(ValueError): normalize(1,'USD/kg','INR/kg')
    e=evidence();e['retrieved_at']=(datetime.now(timezone.utc)-timedelta(days=40)).isoformat()
    assert freshness(e)['stale'] and not freshness(e)['live']
    del e['url']
    with pytest.raises(ValueError):validate_evidence(e)


def persist(store,client='a',title='Broken drawer knob'):
    row=history_row(title)
    store.create(row['job_id'],'template',{'description':title,'material':'PLA'},client)
    store.update(row['job_id'],result=dict(row['result'],part_name=title,pieces=[{'volume_cm3':80}],files=[],estimate={'filament_g':100,'print_minutes':60,'material':'PLA'}))
    store.update(row['job_id'],status='done')
    return row['job_id']


def test_reports_reproducible_versioned_survive_cleanup_restart_and_isolated(tmp_path):
    store=Store(tmp_path)
    jid=persist(store)
    first=get_report(store,'a',jid)['report']
    assert first==get_report(store,'a',jid)['report']
    store.save_impact_input('a',jid,complete().model_dump())
    second=get_report(store,'a',jid)['report']
    assert first['report_id']!=second['report_id']
    store.delete(jid);store.close();store=Store(tmp_path)
    assert get_report(store,'a',jid,first['report_id'])['report']==first
    assert get_report(store,'a',jid)['report']==second
    with pytest.raises(LookupError):get_report(store,'b',jid,first['report_id'])
    assert len(store.list_impact_reports('a',jid))==2
    store.clear_history('a')
    assert store.list_impact_reports('a',jid)==[]
    assert store.impact_input('a',jid)=={}
    store.close()


def test_evidence_update_recalculates_without_rewriting_history(tmp_path):
    store=Store(tmp_path);jid=persist(store)
    first=get_report(store,'a',jid)['report']
    original=store.history('a',job_id=jid)[0]
    e=next(e for e in store.evidence_catalog() if e['id']=='robu-pla-black')
    e['retrieved_at']=datetime.now(timezone.utc).isoformat();e['data']['inr_kg']=700
    store.add_evidence(e)
    second=get_report(store,'a',jid)['report']
    assert second['report_id']!=first['report_id']
    assert store.history('a',job_id=jid)[0]==original
    assert second['costs']['raw_filament_inr']==70
    assert get_report(store,'a',jid,first['report_id'])['report']==first
    store.close()


def test_scoped_api_and_validation(client):
    jid=persist(client.app.state.store)
    url=f'/api/v1/history/{jid}/impact'
    assert client.get(url,headers={'X-Client-Id':'b'}).status_code==404
    h={'X-Client-Id':'a'}
    first=client.get(url,headers=h).json()['report']
    assert first['coverage']['total_metrics']==3
    assert client.post(url,headers=h,json={'tariff_inr_kwh':-1}).status_code==422
    assert client.post(url,headers=h,json=complete().model_dump()).status_code==200
    assert client.get(url+'?report_id='+first['report_id'],headers=h).json()['report']==first
    client.delete('/api/v1/history',headers=h)
    assert client.get(url,headers=h).status_code==404


def test_offer_refresh_keeps_last_verified_on_failure_and_caches_attempts(tmp_path):
    store=Store(tmp_path)
    e=next(e for e in store.evidence_catalog() if e['id']=='medilab-pencil-grip')
    original=deepcopy(e)
    bad=httpx.MockTransport(lambda request:httpx.Response(503))
    assert refresh_evidence(store,e,bad)['status']=='unavailable'
    current=next(e for e in store.evidence_catalog() if e['id']==original['id'])
    assert current==original
    assert refresh_evidence(store,e,bad)['status']=='cached_attempt'
    html='<script type="application/ld+json">'+json.dumps({'@type':'Product','name':'Pencil Grip','offers':{'@type':'Offer','priceCurrency':'INR','price':'500'}})+'</script>'
    good=httpx.MockTransport(lambda request: httpx.Response(200,json={'currency':'INR'}) if request.url.path == '/cart.js' else httpx.Response(200,json={'id':7354021281948,'title':'Pencil Grip','price':50000,'price_min':50000,'price_max':50000,'available':True}))
    assert refresh_evidence(store,e,good,force=True)['status']=='verified'
    current=next(e for e in store.evidence_catalog() if e['id']==original['id'])
    assert current['data']['price_inr']==500
    assert current['version']!=original['version']
    store.close()


def test_refresh_rejects_currency_identity_and_ambiguous_offers():
    for doc in [ {'@type':'Product','name':'Wrong product','offers':{'@type':'Offer','priceCurrency':'INR','price':100}},
                 {'@type':'Product','name':'Pencil Grip','offers':{'@type':'Offer','priceCurrency':'USD','price':100}},
                 {'@type':'Product','name':'Pencil Grip','offers':[{'@type':'Offer','priceCurrency':'INR','price':100},{'@type':'Offer','priceCurrency':'INR','price':200}]}]:
        with pytest.raises(ValueError):parse_offer('<script type="application/ld+json">'+json.dumps(doc)+'</script>','Pencil Grip')


def test_actual_template_function_overrides_unrelated_request():
    row=history_row('Broken drawer knob')
    row['source']='template'
    row['result']['part_id']='door-handle-adapter'
    assert classify(row)['category']=='unclassified'
    row['result']['part_id']='pen-grip'
    assert classify(row)['category']=='pen_grip'


def test_limited_index_price_is_candidate_not_supported_savings():
    e=evidence(price_inr=60,price_basis='retail')
    e['reliability']='limited: publisher listing via search index'
    r=calculate(history_row(),[e],complete())
    assert r['benchmark']['id']=='fixture'
    assert not r['metrics'][0]['comparable']
    assert r['metrics'][0]['percent'] is None


def test_shopify_refresh_rejects_wrong_currency_and_replaced_product(tmp_path):
    store=Store(tmp_path)
    e=next(e for e in store.evidence_catalog() if e['id']=='medilab-pencil-grip')
    usd=httpx.MockTransport(lambda request:httpx.Response(200,json={'currency':'USD'}))
    assert refresh_evidence(store,e,usd,force=True)['status']=='unavailable'
    wrong=httpx.MockTransport(lambda request:httpx.Response(200,json={'currency':'INR'}) if request.url.path=='/cart.js' else httpx.Response(200,json={'id':0,'title':'Pencil Grip','price':10000,'price_min':10000,'price_max':10000}))
    assert refresh_evidence(store,e,wrong,force=True)['status']=='unavailable'
    assert next(x for x in store.evidence_catalog() if x['id']==e['id'])['version']==e['version']
    store.close()
