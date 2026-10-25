"""The default home-printing scenario: it fills only blank inputs, is disclosed, and never invents a comparison."""
import pytest

from app.impact import ImpactInputs, apply_scenario, calculate, load_scenario
from app.impact_service import get_report
from app.store import Store
from tests.test_impact import evidence, history_row, persist


def test_scenario_fills_blank_inputs_but_saved_inputs_win():
    merged, info = apply_scenario({'tariff_inr_kwh': 5.0, 'notes': 'My electricity bill, October.'}, 'pen_grip')
    assert merged['tariff_inr_kwh'] == 5.0                       # saved value kept
    assert merged['printer_watts'] == 150 and merged['failure_rate'] == 0.2
    assert 'tariff_inr_kwh' not in info['applied'] and 'printer_watts' in info['applied']
    assert merged['notes'].startswith("Default scenario") and 'Your notes: My electricity bill, October.' in merged['notes']
    assert merged['benchmark_confirmed'] is True
    ImpactInputs(**merged)                                       # the merged inputs pass the model's own provenance rules


def test_unconfirmed_alternative_is_not_forced_when_the_person_unchecked_it():
    merged, info = apply_scenario({'benchmark_confirmed': False, 'notes': 'Not the same size.'}, 'pen_grip')
    assert merged['benchmark_confirmed'] is False and 'benchmark_confirmed' not in info['applied']


def test_unknown_category_gets_costs_but_no_alternative():
    merged, info = apply_scenario({}, 'unclassified')
    assert 'benchmark_confirmed' not in merged and info['category_note'] is None


def test_every_scenario_value_has_a_stated_basis_and_known_source():
    scenario = load_scenario()
    from app.store import Store as _S
    import json
    from pathlib import Path
    ids = {e['id'] for e in json.loads((Path(__file__).parents[1] / 'app' / 'data' / 'impact_sources.json').read_text(encoding='utf-8'))}
    fields = {f.strip() for b in scenario['basis'] for f in b['field'].split('/')}
    assert set(scenario['values']) <= fields
    for b in scenario['basis']:
        assert b['basis'].strip() and (b['source_id'] is None or b['source_id'] in ids)
    # assumptions that have no source must say so in words
    assert all('ssumption' in b['basis'] for b in scenario['basis'] if b['source_id'] is None)


def test_cost_with_the_scenario_matches_hand_arithmetic():
    row = history_row()
    row['filament_g'], row['print_minutes'] = 14.9, 95
    merged, _ = apply_scenario({}, 'pen_grip')
    price = 649
    report = calculate(row, [evidence(price_inr=530, price_basis='retail', subject='pen_grip')], ImpactInputs(**{**merged, 'material_price_inr_kg': price, 'notes': merged['notes']}))
    filament = 14.9 / 1000 * price
    electricity = 0.150 * 95 / 60 * 8.16
    labor = 10 / 60 * 112.39
    machine = 95 / 60 * 9
    base = filament + electricity + labor + machine
    expected = base + base * 0.2 / 0.8
    assert report['costs']['production_inr'] == pytest.approx(expected)


def test_cheaper_unverified_listing_is_a_caveat_not_the_comparison():
    verified = evidence('retail-grip', price_inr=530, price_basis='retail', subject='pen_grip')
    cheap = evidence('child-set', price_inr=60, price_basis='retail', subject='pen_grip')
    cheap['reliability'] = 'limited: publisher listing via search index'
    merged, _ = apply_scenario({}, 'pen_grip')
    report = calculate(history_row('Pen grip'), [cheap, verified], ImpactInputs(**{**merged, 'material_price_inr_kg': 649}))
    assert report['benchmark']['id'] == 'retail-grip'
    cost = report['metrics'][0]
    assert cost['comparable'] and cost['industry'] == 530
    assert any('60' in c and 'could not be verified' in c for c in cost['caveats'])
    assert not cost['verified_savings']


def test_a_dearer_part_than_the_shop_alternative_is_reported_as_higher():
    merged, _ = apply_scenario({}, 'drawer_knob')
    row = history_row('Drawer knob')
    report = calculate(row, [evidence(price_inr=30, price_basis='retail')], ImpactInputs(**{**merged, 'material_price_inr_kg': 649}))
    cost = report['metrics'][0]
    assert cost['comparable'] and cost['direction'] == 'higher' and cost['difference'] < 0


def test_report_discloses_the_scenario_and_lists_its_sources(tmp_path):
    store = Store(tmp_path)
    jid = persist(store)
    report = get_report(store, 'a', jid)['report']
    assert report['scenario']['applied'] and report['scenario']['basis']
    shown = {s['id'] for s in report['sources']}
    assert {'scenario-printer-power-range', 'scenario-bescom-domestic-tariff'} <= shown
    store.close()
