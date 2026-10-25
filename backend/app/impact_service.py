"""Scoped saved reports; no generation or external network side effects."""
from .impact import ENGINE_VERSION, ImpactInputs, apply_scenario, calculate, classify, digest, freshness, load_carbon, load_scenario


def get_report(store, client_id, job_id, report_id=None):
    rows = store.history(client_id, job_id=job_id)
    if not rows:
        raise LookupError('No such history entry.')
    row = rows[0]
    if row['status'] != 'done':
        raise ValueError('Impact analysis is available for completed designs only.')
    from .impact_research import relevant_benchmark
    scope = digest([client_id, job_id])
    catalog = [e for e in store.evidence_catalog() if (not e.get('scope') or e['scope'] == scope) and (e['kind'] != 'benchmark' or relevant_benchmark(e['title'], row))]
    if report_id:
        report = store.impact_report(client_id, job_id, report_id=report_id)
        if not report:
            raise LookupError('No such saved impact report.')
    else:
        # Persist defaults sparsely. Revalidation must not turn absent inputs into explicit zeroes.
        merged, scenario = apply_scenario(store.impact_input(client_id, job_id), classify(row)['category'])
        inputs = ImpactInputs(**merged)
        fingerprint = digest({'engine': ENGINE_VERSION, 'history': {k:v for k,v in row.items() if k != 'files_available'},
                              'inputs': inputs.model_dump(), 'scenario': scenario, 'carbon': load_carbon(), 'evidence': sorted((e['id'], e['version']) for e in catalog)})
        report = store.impact_report(client_id, job_id, fingerprint=fingerprint)
        if not report:
            draft = calculate(row, catalog, inputs)
            draft['scenario'] = scenario
            draft['market_snapshot'] = [e for e in catalog if e.get('scope') == scope]
            report = store.save_impact_report(client_id, job_id, fingerprint, draft)
    return {'report': report, 'market_observations': report.get('market_snapshot', []) if report_id else [e for e in store.market_observations(scope) if e['kind'] != 'benchmark' or relevant_benchmark(e['title'], row)], 'research': store.research_state(client_id, job_id), 'freshness': [freshness(e) for e in report['sources']],
            'refresh_status': {key: value for key,value in store.refresh_status().items() if key in {e['id'] for e in report['sources']}},
            'versions': store.list_impact_reports(client_id, job_id),
            'catalog': [{'id': e['id'], 'kind': e['kind'], 'subject': e['subject'], 'title': e['title'], 'data': e['data']} for e in catalog if e['kind'] in ('filament_factor', 'grid_factor')]}
