"""Deterministic per-design costing and impact. Unknown inputs remain unknown.

No network calls or AI calls occur in this calculation module. All evidence is
versioned in the existing SQLite store; reports contain their complete inputs.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from .printability import MATERIALS, ALIASES, named, profile_for

ENGINE_VERSION = '1.3.1'
CATEGORIES = {
    'zipper_pull': 'Replacement zipper pull / accessible zip loop',
    'utensil_grip': 'Adaptive utensil grip', 'pen_grip': 'Ergonomic writing grip',
    'drawer_knob': 'Replacement drawer knob', 'phone_case': 'Replacement phone case',
    'appliance_handle': 'Compatible appliance handle', 'unclassified': 'Comparison not established',
}


class Component(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    name: str = Field(min_length=1, max_length=100)
    cost_inr: float | None = Field(None, ge=0, le=1e7)
    mass_g: float | None = Field(None, ge=0, le=1e6)
    co2e_kg: float | None = Field(None, ge=0, le=1e6)
    provenance: str = Field(min_length=3, max_length=500)


class ImpactInputs(BaseModel):
    model_config = ConfigDict(extra='forbid', allow_inf_nan=False)
    material: Literal['PLA', 'PETG', 'TPU', 'ABS', 'Nylon'] | None = None
    filament_g: float | None = Field(None, ge=0, le=1e6)
    print_minutes: float | None = Field(None, ge=0, le=1e6)
    measurement: Literal['estimated', 'measured'] = 'estimated'
    material_price_inr_kg: float | None = Field(None, ge=0, le=1e7)
    printer_watts: float | None = Field(None, ge=0, le=100000)
    electricity_kwh: float | None = Field(None, ge=0, le=1e6)
    tariff_inr_kwh: float | None = Field(None, ge=0, le=10000)
    labor_minutes: float | None = Field(None, ge=0, le=1e6)
    labor_inr_hour: float | None = Field(None, ge=0, le=1e6)
    machine_inr_hour: float | None = Field(None, ge=0, le=1e6)
    setup_inr: float | None = Field(None, ge=0, le=1e7)
    consumables_inr: float | None = Field(None, ge=0, le=1e7)
    postprocess_inr: float | None = Field(None, ge=0, le=1e7)
    failure_rate: float | None = Field(None, ge=0, lt=0.95)
    extra_print_waste_g: float | None = Field(None, ge=0, le=1e6)
    components: list[Component] | None = Field(None, max_length=30)
    delivery_inr: float | None = Field(None, ge=0, le=1e7)
    store_price_inr: float | None = Field(None, ge=0, le=1e7)
    delivery_co2e_kg: float | None = Field(None, ge=0, le=1e6)
    additional_process_co2e_kg: float | None = Field(None, ge=0, le=1e6)
    filament_factor_id: str | None = Field(None, max_length=100)
    grid_factor_id: str | None = Field(None, max_length=100)
    benchmark_id: str | None = Field(None, max_length=100)
    benchmark_confirmed: bool = False
    compatibility: str = Field('', max_length=100)
    region: str = Field('India', max_length=100)
    disposal_scenario: str = Field('Not assessed; no avoided-disposal claim.', max_length=500)
    notes: str = Field('', max_length=3000)

    @model_validator(mode='after')
    def explicit_provenance(self):
        provided = self.model_fields_set - {'benchmark_id', 'benchmark_confirmed', 'compatibility', 'filament_factor_id', 'grid_factor_id', 'store_price_inr'}
        if provided and len(self.notes.strip()) < 3:
            raise ValueError('Explain the source or assumptions for your manufacturing inputs in notes.')
        if self.benchmark_confirmed and len(self.notes.strip()) < 3:
            raise ValueError('Document why the alternative fits the same function and dimensions.')
        return self


def number(value):
    return float(value) if isinstance(value, (float, int)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0 else None


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def classify(row):
    result = row.get('result') or {}
    design = result.get('design') or {}
    part_id = result.get('part_id')
    if row.get('source') in ('template', 'fallback') and part_id:
        # A ready-made adapter/pull is not a replacement knob just because the
        # request asked for one. Prefer the actual known template's function.
        category = {'pen-grip': 'pen_grip', 'utensil-grip': 'utensil_grip', 'zipper-pull': 'zipper_pull'}.get(part_id, 'unclassified')
        return {'category': category, 'label': CATEGORIES[category], 'method': 'saved template function',
                'reason': 'Known template function; alternative fit and suitability still need confirmation.' if category != 'unclassified' else 'No equivalent benchmark category is established for this actual template. The request alone cannot override its function.'}
    primary = ' '.join(str(v or '') for v in (row.get('title'), row.get('request'), result.get('part_id'))).lower().replace('_', ' ').replace('-', ' ')
    secondary = str(design.get('understanding') or '').lower()
    def matches(text):
        rules = {
            'zipper_pull': r'\b(?:zipper|zip)\b.{0,30}\b(?:loop|pull|grip|tab)\b',
            'phone_case': r'\b(?:phone|iphone|smartphone|mobile)\b.{0,35}\b(?:case|cover)\b',
            'utensil_grip': r'\b(?:spoon|fork|utensil|cutlery)\b.{0,35}\b(?:grip|holder|handle|cuff)\b',
            'pen_grip': r'\b(?:pen|pencil|writing)\b.{0,30}\b(?:grip|holder|aid)\b',
            'drawer_knob': r'\b(?:drawer|cabinet|cupboard|furniture)\b.{0,30}\bknob\b',
            'appliance_handle': r'\b(?:appliance|refrigerator|fridge|washing machine|microwave|oven|dishwasher)\b.{0,40}\bhandle\b',
        }
        return [key for key, pattern in rules.items() if re.search(pattern, text) or re.search(pattern, ' '.join(reversed(text.split()))) ]
    found = matches(primary)
    if not found:
        found = matches(secondary)
    category = found[0] if len(found) == 1 else 'unclassified'
    return {'category': category, 'label': CATEGORIES[category], 'method': 'deterministic functional rules',
            'reason': 'One functional category matched; fit and performance still require validation.' if category != 'unclassified' else 'Insufficient or conflicting functional evidence. No unrelated alternative selected.'}


SCENARIO_FILE = Path(__file__).parent / 'data' / 'impact_scenario.json'
CARBON_FILE = Path(__file__).parent / 'data' / 'impact_carbon.json'


def load_carbon():
    try:
        return json.loads(CARBON_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def simple_summary(carbon_cfg, *, material_key, mass_g, failure_rate, cost_total, filament_cost, electricity_cost, store_price, store_source, minutes):
    """The three numbers a person actually reads: what it costs, what it emits, how long it takes.

    Carbon is weight x a per-gram factor, for the printed part and for a bought one of the same weight, so both sides use one boundary."""
    out = {'cost': None, 'carbon': None, 'time': None, 'custom': True}
    if cost_total is not None:
        other = cost_total - (filament_cost or 0) - (electricity_cost or 0)
        saved = store_price - cost_total if store_price is not None else None
        out['cost'] = {'store': store_price, 'store_source': store_source, 'print': cost_total, 'filament': filament_cost, 'electricity': electricity_cost,
                       'other': max(other, 0), 'saved': saved, 'percent': saved/store_price*100 if saved is not None and store_price > 0 else None}
    if carbon_cfg and mass_g is not None:
        p, s = carbon_cfg['print'], carbon_cfg['store']
        ref = p['reference_mass_g']
        material = mass_g*p['material_kg_co2e']/ref
        printing = mass_g*p['printing_kg_co2e']/ref
        failed = (material+printing)*failure_rate/(1-failure_rate) if failure_rate else 0
        total = material+printing+failed
        per_g = (s['kg_co2e_low']+s['kg_co2e_high'])/2/((s['mass_g_low']+s['mass_g_high'])/2)
        store = mass_g*per_g
        saved = store-total
        out['carbon'] = {'store': store, 'print': total, 'material': material, 'printing': printing, 'failed': failed, 'saved': saved,
                         'percent': saved/store*100 if store > 0 else None, 'mass_g': mass_g,
                         'material_specific': str(material_key or '').casefold() == p['measured_material'].casefold(), 'material_name': material_key}
    if minutes is not None:
        d = (carbon_cfg or {}).get('delivery_days')
        out['time'] = {'print_minutes': minutes, 'delivery_days': d}
    return out


def load_scenario():
    try:
        return json.loads(SCENARIO_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def apply_scenario(stored, category, scenario=None):
    """Fill every input the person has not saved with the documented default scenario. Saved inputs always win, field by field.

    Returns (inputs dict, info). The scenario is a set of stated assumptions with sources, not measurements, and the report says so."""
    scenario = load_scenario() if scenario is None else scenario
    if not scenario:
        return dict(stored), None
    merged, applied = dict(stored), []
    for key, value in scenario['values'].items():
        if key not in merged:
            merged[key] = value; applied.append(key)
    cat = scenario.get('category_defaults', {}).get(category)
    cat_applied = []
    if cat and 'benchmark_confirmed' not in merged:
        merged['benchmark_confirmed'] = cat['benchmark_confirmed']; cat_applied.append('benchmark_confirmed')
    if applied or cat_applied:
        text = f"Default scenario '{scenario['label']}' applied to the inputs left blank (edit any of them below): " + '; '.join(f"{b['field']}: {b['text']} ({b['basis']})" for b in scenario['basis'] if any(f.strip() in applied for f in b['field'].split('/')))
        if cat_applied and cat:
            text += ' Alternative: ' + cat['note']
        user = merged.get('notes', '').strip()
        merged['notes'] = (text + (f'\n\nYour notes: {user}' if user else ''))[:3000]
    info = {'id': scenario['id'], 'label': scenario['label'], 'applied': applied + cat_applied,
            'basis': [b for b in scenario['basis'] if any(f.strip() in applied for f in b['field'].split('/'))],
            'category_note': cat['note'] if cat_applied and cat else None}
    return merged, info


def freshness(evidence, at=None):
    at = at or datetime.now(timezone.utc)
    verified = datetime.fromisoformat(evidence['retrieved_at'].replace('Z', '+00:00'))
    age = max(0, (at-verified).days)
    return {'id': evidence['id'], 'version': evidence['version'], 'last_verified': evidence['retrieved_at'],
            'age_days': age, 'stale': age > evidence.get('max_age_days', 30), 'live': False,
            'refresh_method': evidence.get('refresh', {}).get('method', 'manual')}


def select_benchmark(classification, catalog, inputs):
    candidates = [e for e in catalog if e['kind'] == 'benchmark' and e['subject'] == classification['category']
                  and e.get('verified') and e.get('region') == inputs.region
                  and e['data'].get('price_basis') == 'retail' and number(e['data'].get('price_inr')) is not None]
    # Cheapest evidenced equivalent, never an entire appliance for a replacement part.
    candidates.sort(key=lambda e: (e['data']['price_inr'], e['id']))
    # Unless the user picked one, compare against the cheapest candidate whose publisher page was verified. Cheaper listings that
    # could not be verified stay visible as caveats (see calculate), so a pricier alternative never hides a cheaper one.
    verified = [e for e in candidates if not e.get('reliability', '').startswith('limited')]
    selected_pool = [e for e in candidates if e['id'] == inputs.benchmark_id] if inputs.benchmark_id else (verified or candidates)
    selected = selected_pool[0] if selected_pool else None
    compatible = bool(selected and inputs.benchmark_confirmed and not selected.get('reliability', '').startswith('limited'))
    if selected and selected['data'].get('compatibility'):
        compatible = compatible and inputs.compatibility.casefold().strip() == selected['data']['compatibility'].casefold().strip()
    if selected and classification['category'] in ('appliance_handle', 'phone_case') and not selected['data'].get('compatibility'):
        compatible = False  # A generic price range cannot establish model-specific compatibility.
    return selected, compatible, candidates


def calculate(row, catalog, inputs: ImpactInputs):
    res, est = row.get('result') or {}, (row.get('result') or {}).get('estimate') or {}
    classification = classify(row)
    text_material = inputs.material or row.get('material') or est.get('material') or ''
    material = profile_for(text_material).key if named(text_material) or text_material.lower() == 'nylon' else None
    sources = {}
    def use(e):
        if e:
            sources[e['id']] = e
        return e
    def evidence(kind, subject, selected_id=None):
        eligible = [e for e in catalog if e['kind'] == kind and e['subject'] == subject and e.get('verified') and (kind != 'material_price' or e['region'] == inputs.region)]
        if selected_id:
            eligible = [e for e in eligible if e['id'] == selected_id]
        return use(sorted(eligible, key=lambda e: (e['retrieved_at'], e['id']), reverse=True)[0] if eligible else None)
    for ref in catalog:
        if ref['kind'] == 'reference' and (ref['subject'] in ('all', classification['category']) or ref['subject'] == 'assistive' and classification['category'] in ('utensil_grip', 'pen_grip')):
            use(ref)
    price_evidence = evidence('material_price', material) if material and inputs.material_price_inr_kg is None else None
    price = inputs.material_price_inr_kg if inputs.material_price_inr_kg is not None else (price_evidence or {}).get('data', {}).get('inr_kg')
    # A changed material needs new toolpath estimates; do not silently reuse another material's grams/time.
    base_material = row.get('material') or est.get('material') or ''
    material_changed = bool(inputs.material and (not named(base_material) or material != profile_for(base_material).key))
    mass = inputs.filament_g if inputs.filament_g is not None else None if material_changed else number(row.get('filament_g'))
    minutes = inputs.print_minutes if inputs.print_minutes is not None else None if material_changed else number(row.get('print_minutes'))
    volumes = [number(p.get('volume_cm3')) for p in res.get('pieces', [])]
    volume = sum(volumes) if volumes and all(v is not None for v in volumes) else None
    mass_method = inputs.measurement if inputs.filament_g is not None else 'sliced estimate' if est.get('source') else 'rough estimate'
    if mass is None and material and volume is not None and not material_changed:
        mass = volume * MATERIALS[material].density
        mass_method = 'CAD volume × density; solid-volume fallback, supports not included'
    energy = inputs.electricity_kwh
    energy_method = inputs.measurement if energy is not None else 'average printer watts × hours; estimated'
    if energy is None and inputs.printer_watts is not None and minutes is not None:
        energy = inputs.printer_watts/1000 * minutes/60
    components = [c.model_dump() for c in inputs.components] if inputs.components is not None else None
    component_cost = sum(c['cost_inr'] for c in components) if components is not None and all(c['cost_inr'] is not None for c in components) else None
    component_mass = sum(c['mass_g'] for c in components) if components is not None and all(c['mass_g'] is not None for c in components) else None
    component_co2 = sum(c['co2e_kg'] for c in components) if components is not None and all(c['co2e_kg'] is not None for c in components) else None
    waste = inputs.extra_print_waste_g
    consumed = mass + waste if mass is not None and waste is not None else None
    raw = mass/1000*price if mass is not None and price is not None else None
    all_filament = consumed/1000*price if consumed is not None and price is not None else None
    electricity_cost = energy*inputs.tariff_inr_kwh if energy is not None and inputs.tariff_inr_kwh is not None else None
    labor = inputs.labor_minutes/60*inputs.labor_inr_hour if inputs.labor_minutes is not None and inputs.labor_inr_hour is not None else None
    machine = minutes/60*inputs.machine_inr_hour if minutes is not None and inputs.machine_inr_hour is not None else None
    # Retry model: each failed attempt consumes a full print; 1/(1-p) attempts per successful print.
    repeat_items = [all_filament, electricity_cost, inputs.consumables_inr, labor, machine]
    repeat_base = sum(repeat_items) if all(v is not None for v in repeat_items) else None
    failure = repeat_base*inputs.failure_rate/(1-inputs.failure_rate) if repeat_base is not None and inputs.failure_rate is not None else None
    costs = [all_filament, electricity_cost, inputs.consumables_inr, labor, machine, inputs.setup_inr, failure, inputs.postprocess_inr, component_cost]
    total = sum(costs) if all(v is not None for v in costs) else None
    printing = all_filament+electricity_cost if all_filament is not None and electricity_cost is not None else None
    delivered = total+inputs.delivery_inr if total is not None and inputs.delivery_inr is not None else None
    factor = evidence('filament_factor', material, inputs.filament_factor_id) if material and inputs.filament_factor_id else None
    grid = evidence('grid_factor', inputs.region, inputs.grid_factor_id) if inputs.grid_factor_id else None
    filament_co2 = consumed/1000*factor['data']['kg_co2e_kg'] if consumed is not None and factor and factor['data'].get('boundary') == 'cradle_to_filament' else None
    electricity_co2 = energy*grid['data']['kg_co2e_kwh'] if energy is not None and grid and grid['data'].get('boundary') == 'life_cycle_electricity' else None
    carbon_parts = [filament_co2, electricity_co2]
    print_co2 = sum(carbon_parts)/(1-inputs.failure_rate) if all(v is not None for v in carbon_parts) and inputs.failure_rate is not None else None
    carbon_complete = [print_co2, component_co2, inputs.additional_process_co2e_kg, inputs.delivery_co2e_kg]
    carbon = sum(carbon_complete) if all(v is not None for v in carbon_complete) else None
    expected_print_g = consumed/(1-inputs.failure_rate) if consumed is not None and inputs.failure_rate is not None else None
    total_mass = expected_print_g+component_mass if expected_print_g is not None and component_mass is not None else None
    support = None if material_changed else number(est.get('support_g'))
    expected_waste = (support + waste + consumed*inputs.failure_rate/(1-inputs.failure_rate)) if support is not None and waste is not None and consumed is not None and inputs.failure_rate is not None else None
    benchmark, equivalent, candidates = select_benchmark(classification, catalog, inputs)
    use(benchmark)
    b = benchmark['data'] if benchmark else {}
    cheaper_unverified = [c for c in candidates if benchmark and c['id'] != benchmark['id'] and c['data']['price_inr'] < benchmark['data']['price_inr']
                          and c.get('reliability', '').startswith('limited')]
    cost_caveats = [f"A cheaper listing exists but could not be verified and is not used: {c['title']} at ₹{c['data']['price_inr']:g} ({c['reliability']}). {c['data'].get('notes', '')}".strip()
                    for c in cheaper_unverified]
    def metric(key, title, unit, ours, theirs, allowed, reason, boundary, caveats=()):
        comparable = allowed and ours is not None and theirs is not None
        delta = theirs-ours if comparable else None
        return {'key': key, 'title': title, 'unit': unit, 'reform3d': ours, 'industry': theirs,
                'comparable': comparable, 'status': 'estimated' if comparable else 'unavailable',
                'difference': delta, 'percent': delta/theirs*100 if comparable and theirs > 0 else None,
                'direction': 'lower' if comparable and delta > 0 else 'higher' if comparable and delta < 0 else 'equal' if comparable else None,
                'reason': 'Modelled comparison, not experimentally verified savings.' if comparable else reason,
                'boundary': boundary, 'verified_savings': False, 'caveats': list(caveats)}
    cost_benchmark = number(b.get('price_inr'))
    if benchmark is None:
        cost_reason = 'No verified retail alternative has been established for this functional category and region.'
    elif benchmark.get('reliability', '').startswith('limited'):
        cost_reason = 'Candidate price only: direct publisher verification is missing. Last observed date and limitations are shown in Sources.'
    elif not equivalent:
        cost_reason = 'Functional equivalence is unconfirmed. Phone cases and appliance handles also require an exact model-specific benchmark.'
    elif total is None:
        cost_reason = 'Complete production cost is unavailable: one or more manufacturing inputs are still unknown. See the itemized BOM.'
    else:
        cost_reason = 'A complete comparable cost is unavailable.'
    metrics = [metric('cost', 'Cost', '₹', total, cost_benchmark, equivalent,
                      cost_reason,
                      'ReForm3D complete manufacturing cost vs alternative retail acquisition price; excludes consumer delivery on both sides.',
                      cost_caveats),
               metric('carbon', 'Carbon emissions', 'kg CO₂e', carbon, number(b.get('production_delivery_co2e_kg')) if b.get('carbon_boundary') == 'cradle_to_delivered' else None,
                      equivalent and b.get('carbon_boundary') == 'cradle_to_delivered' and bool(factor and factor['data'].get('boundary') == 'cradle_to_filament'),
                      'A matching filament LCA, electricity factor, process/delivery inputs and an equivalent product LCA with matching boundaries are required.',
                      'Raw materials through production and delivery; use and end-of-life excluded for both alternatives.'),
               metric('material', 'Material consumption', 'g', total_mass, number(b.get('material_consumed_g')) if b.get('mass_basis') == 'production_consumed' else None,
                      equivalent and b.get('mass_basis') == 'production_consumed',
                      'Production material input is required for both alternatives. Packaged weight or net product mass cannot stand in for material consumed.',
                      'Production material consumed per successful functional item, including expected printing waste; not waste avoided.')]
    bom_values = [('filament', 'Print filament including extra print waste', all_filament), ('electricity', 'Printing electricity', electricity_cost),
                  ('consumables', 'Consumables per attempt', inputs.consumables_inr), ('labor', 'Labor per attempt', labor),
                  ('machine', 'Machine time / overhead per attempt', machine), ('setup', 'Setup per completed item', inputs.setup_inr),
                  ('failure', 'Expected failed-print allowance', failure), ('postprocess', 'Post-processing per completed item', inputs.postprocess_inr),
                  ('components', 'Additional components', component_cost)]
    assumptions = [
        'One completed design is not a measured physical print. Estimates describe one successful functional item.',
        'Missing inputs are never set to zero. Enter zero explicitly only when justified in the input notes.',
        'Supports are already included in slicer filament weight; support grams are shown separately and never added twice.',
        'Extra print waste covers purge, brim or raft material absent from the saved estimate; enter zero if already included.',
        'Retry model assumes a full print is consumed on each failure; recurring filament, electricity, labor, consumables and machine time scale by 1/(1-failure rate). Setup, components and post-processing occur once.',
        'No avoided disposal of an entire appliance, no landfill credit, no biodegradability benefit, and no government subsidy are inferred.',
        'Material or printer-brand reference data are scenarios, not proof of the actual spool or printer used.',
        'Cost compares making against buying at retail; it does not compare the manufacturing costs of both alternatives.',
    ]
    store_price, store_source = (inputs.store_price_inr, {'kind': 'you'}) if inputs.store_price_inr is not None else \
        (cost_benchmark, {'kind': 'listing', 'title': benchmark['title'], 'url': benchmark['url']}) if benchmark and equivalent and cost_benchmark is not None else (None, None)
    simple = simple_summary(load_carbon(), material_key=MATERIALS[material].name if material else None, mass_g=mass, failure_rate=inputs.failure_rate, cost_total=total, filament_cost=all_filament,
                            electricity_cost=electricity_cost, store_price=store_price, store_source=store_source, minutes=minutes)
    return {'engine_version': ENGINE_VERSION, 'job_id': row['job_id'], 'simple': simple, 'title': row['title'], 'classification': classification,
            'material': MATERIALS[material].name if material else None, 'geometry': {'volume_cm3': volume, 'size_mm': row.get('size_mm') or (res['pieces'][0].get('size_mm') if len(res.get('pieces') or []) == 1 else None)},
            'manufacturing': {'filament_g': mass, 'mass_method': mass_method, 'print_minutes': minutes, 'support_g': support,
                              'electricity_kwh': energy, 'energy_method': energy_method, 'extra_print_waste_g': waste,
                              'expected_print_waste_g': expected_waste, 'additional_components': components,
                              'material_price_inr_kg': price, 'material_price_source': {k:price_evidence[k] for k in ('title','url','retrieved_at','reliability')} if price_evidence else None, 'filament_co2e_kg': filament_co2, 'electricity_co2e_kg': electricity_co2,
                              'disposal_scenario': inputs.disposal_scenario},
            'costs': {'raw_filament_inr': raw, 'printing_inr': printing, 'production_inr': total, 'delivered_inr': delivered,
                      'known_subtotal_inr': sum(v for v in costs if v is not None) if any(v is not None for v in costs) else None,
                      'missing_items': [label for _, label, v in bom_values if v is None]},
            'bom': [{'key': k, 'label': label, 'value': v, 'unit': '₹', 'status': 'estimated' if v is not None else 'unavailable'} for k, label, v in bom_values],
            'benchmark': benchmark, 'benchmark_equivalent': equivalent, 'benchmark_candidates': candidates,
            'metrics': metrics, 'sources': list(sources.values()), 'inputs': inputs.model_dump(), 'assumptions': assumptions,
            'evidence_quality': 'Estimated scenario; user-confirmed equivalence' if any(m['comparable'] for m in metrics) else 'Incomplete comparison evidence',
            'coverage': {'comparable_metrics': sum(m['comparable'] for m in metrics), 'total_metrics': 3}}
