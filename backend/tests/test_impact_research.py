"""Synthetic provider/source fixtures; never production research or prices."""
import json
from datetime import datetime,timezone

import httpx
import pytest

from app.impact import classify,digest
from app.impact_research import ResearchService,ResearchUnavailable,grounded_response,verify_observation,public_url
from app.impact_service import get_report
from conftest import make_settings
from test_impact import history_row,persist


def config(tmp_path):
    return make_settings(tmp_path,enable_llm=True,llm_provider='gemini',llm_model='gemini-3-flash-preview',llm_api_key='test-secret-never-output')


def fixture_response():
    quote='Fixture drawer knob pack of 2 costs INR 60.'
    observation={'kind':'benchmark','title':'Fixture drawer knob','source_url':'https://publisher.example/knob','publisher':'Synthetic fixture',
                 'quote':quote,'value':60,'currency':'INR','quantity':2,'quantity_unit':'item','category':'drawer_knob','notes':'Synthetic test only'}
    metadata={'webSearchQueries':['fixture drawer knob price'], 'groundingChunks':[{'web':{'uri':observation['source_url'],'title':'Synthetic fixture'}}],
              'groundingSupports':[{'segment':{'text':quote},'groundingChunkIndices':[0]}]}
    return observation,metadata


def test_uncited_wrong_currency_or_wrong_category_rejected():
    o,m=fixture_response();row=history_row()
    assert verify_observation(o,{},row,'scope') is None
    assert verify_observation(dict(o,currency='USD'),m,row,'scope') is None
    assert verify_observation(dict(o,category='phone_case'),m,row,'scope') is None
    assert verify_observation(dict(o,value=5000),m,row,'scope') is None


def test_grounding_is_not_same_as_publisher_verification(monkeypatch):
    o,m=fixture_response();row=history_row()
    candidate=verify_observation(o,m,row,'scope')
    assert candidate['data']['price_inr']==30
    assert candidate['reliability'].startswith('limited')
    monkeypatch.setattr('app.impact_research.public_url',lambda url:url)
    with httpx.Client(transport=httpx.MockTransport(lambda req:httpx.Response(200,text='<title>Fixture drawer knob</title><p>'+o['quote']+'</p>'))) as client:
        checked=verify_observation(o,m,row,'scope',client)
    assert not checked['reliability'].startswith('limited')
    assert checked['scope']=='scope'


def test_provider_tool_and_credentials_are_backend_only(tmp_path):
    o,m=fixture_response()
    def provider(request):
        data=json.loads(request.content)
        assert data['tools']==[{'google_search':{}}]
        assert request.headers['x-goog-api-key']=='test-secret-never-output'
        assert 'who_for' not in data['contents'][0]['parts'][0]['text']
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps({'observations':[o]})}]},'groundingMetadata':m}]})
    data,metadata,model=grounded_response(config(tmp_path),history_row(),httpx.MockTransport(provider))
    assert data['observations'][0]['value']==60
    assert metadata['webSearchQueries']


def test_quota_does_not_leak_key_or_fabricate_results(tmp_path):
    with pytest.raises(ResearchUnavailable) as exc:
        grounded_response(config(tmp_path),history_row(),httpx.MockTransport(lambda req:httpx.Response(429,json={'error':{'message':'secret provider detail'}})))
    assert '429' in str(exc.value)
    assert 'test-secret' not in str(exc.value)
    assert 'secret provider detail' not in str(exc.value)


def test_model_prose_without_real_search_metadata_is_rejected(tmp_path):
    with pytest.raises(ResearchUnavailable):
        grounded_response(config(tmp_path),history_row(),httpx.MockTransport(lambda req:httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':'{"observations":[]}'}]}}]})))


def test_cache_isolation_history_recalculation_and_clear(client,tmp_path,monkeypatch):
    store=client.app.state.store;jid=persist(store)
    o,m=fixture_response();calls=[]
    def provider(request):
        calls.append(1)
        return httpx.Response(200,json={'candidates':[{'content':{'parts':[{'text':json.dumps({'summary':'Synthetic fixture','observations':[o],'missing':['Full product LCA']})}]},'groundingMetadata':m}]})
    monkeypatch.setattr('app.impact_research.public_url',lambda url:url)
    service=ResearchService(store,config(tmp_path),httpx.MockTransport(provider),httpx.MockTransport(lambda req:httpx.Response(200,text='<p>'+o['quote']+'</p>')))
    before=get_report(store,'a',jid)['report']
    result=service.run('a',jid)
    assert result['status']=='done' and len(result['observations'])==1
    assert service.run('a',jid)['status']=='done' and len(calls)==1
    payload=get_report(store,'a',jid)
    assert payload['report']['report_id']!=before['report_id']
    assert payload['market_observations']
    assert payload['report']['market_snapshot']
    other=persist(store,client='b')
    assert not get_report(store,'b',other)['market_observations']
    assert all(e['id']!=result['observations'][0]['id'] for e in get_report(store,'b',other)['report']['sources'])
    with pytest.raises(LookupError):service.run('b',jid)
    store.clear_history('a')
    assert store.research_state('a',jid) is None


def test_failure_is_cached_and_saved_report_remains(client,tmp_path):
    store=client.app.state.store;jid=persist(store);calls=[]
    def fail(req):
        calls.append(1);return httpx.Response(429)
    service=ResearchService(store,config(tmp_path),httpx.MockTransport(fail))
    assert service.run('a',jid)['status']=='unavailable'
    service.run('a',jid)
    assert len(calls)==1
    assert get_report(store,'a',jid)['report']['title']


def test_research_endpoint_ownership_and_unconfigured_state(client):
    jid=persist(client.app.state.store)
    url=f'/api/v1/history/{jid}/research'
    assert client.post(url,headers={'X-Client-Id':'b'}).status_code==404
    r=client.post(url,headers={'X-Client-Id':'a'})
    assert r.status_code==200
    assert r.json()['research']['status']=='unconfigured'
    assert not r.json()['research']['available']


def test_zipper_pull_now_has_relevant_category():
    assert classify(history_row('Ergonomic Zipper Loop Pull','PETG'))['category']=='zipper_pull'


def test_local_publisher_urls_rejected():
    for url in ('https://127.0.0.1/page','https://[::1]/page','http://example.com','https://user:pass@example.com'):
        with pytest.raises((ValueError,OSError)):public_url(url)


def test_advertised_pack_count_overrides_model_single_count():
    o,m=fixture_response()
    o['title']='Fixture drawer knob (20 pcs)';o['quantity']=1
    m['groundingSupports'][0]['segment']['text']='Fixture drawer knob pack of 20 costs INR 60.'
    record=verify_observation(o,m,history_row(),'scope')
    assert record['data']['pack_quantity']==20
    assert record['data']['price_inr']==3


def test_openrouter_search_fallback_has_real_citations(tmp_path):
    from app.config import PoolMember
    settings=config(tmp_path)
    settings.pool_entries=[PoolMember('openai','openrouter','fixture/model','https://openrouter.ai/api/v1','test-router-key',False)]
    o,m=fixture_response()
    def provider(req):
        if req.url.host=='generativelanguage.googleapis.com':return httpx.Response(429)
        body=json.loads(req.content)
        assert body['tools'][0]['type']=='openrouter:web_search'
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'observations':[o]}),'annotations':[{'type':'url_citation','url_citation':{'url':o['source_url'],'content':m['groundingSupports'][0]['segment']['text']}}]}}]})
    data,metadata,model=grounded_response(settings,history_row(),httpx.MockTransport(provider))
    assert model=='OpenRouter/fixture/model'
    assert verify_observation(data['observations'][0],metadata,history_row(),'scope')['data']['price_inr']==30


def test_zipper_research_does_not_import_a_more_expensive_unrelated_combo():
    o,m=fixture_response();row=history_row('Ergonomic Zipper Loop Pull','PETG')
    o['category']='zipper_pull';o['title']='Adaptive Button Hook with Zipper Pull Tool'
    assert verify_observation(o,m,row,'scope') is None
