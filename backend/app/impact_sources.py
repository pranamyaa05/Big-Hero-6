"""Evidence validation and bounded, opt-in refresh of publisher structured offers.

Run `python -m app.impact_sources --list`, `--refresh`, or `--import FILE`.
This module refreshes operator-reviewed sources; model-backed impact-page searches
are handled separately by impact_research.py. Generation never invokes research.
"""
from __future__ import annotations
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

import httpx
from .impact import number

SEED = Path(__file__).parent / 'data' / 'impact_sources.json'


def normalize(value, unit, target):
    scales = {('INR/g', 'INR/kg'): 1000, ('INR/kg', 'INR/kg'): 1,
              ('kg', 'g'): 1000, ('g', 'g'): 1, ('W', 'kW'): .001,
              ('kg CO2e/kg filament', 'kg CO2e/kg filament'): 1,
              ('g CO2e/kWh', 'kg CO2e/kWh'): .001, ('kg CO2e/kWh', 'kg CO2e/kWh'): 1}
    if number(value) is None or (unit, target) not in scales:
        raise ValueError('Unsupported unit conversion or invalid quantity')
    return value*scales[unit, target]


def validate_evidence(document):
    e = deepcopy(document)
    e.pop('version', None)
    for key in ('id', 'kind', 'subject', 'title', 'url', 'publisher', 'retrieved_at', 'region', 'unit', 'reliability', 'data'):
        if not e.get(key):
            raise ValueError(f'Evidence requires {key}')
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', e['id']):
        raise ValueError('Invalid evidence ID')
    url = urlsplit(e['url'])
    if url.scheme != 'https' or not url.hostname or url.username or url.password:
        raise ValueError('Evidence needs an exact public HTTPS source URL')
    stamp = datetime.fromisoformat(e['retrieved_at'].replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('Retrieval timestamp must include timezone')
    if stamp > datetime.now(timezone.utc):
        raise ValueError('Retrieval date cannot be in the future')
    e.setdefault('publication_date', None)
    e.setdefault('verified', False)
    e.setdefault('max_age_days', 30)
    if not isinstance(e['max_age_days'], int) or not 1 <= e['max_age_days'] <= 3650:
        raise ValueError('Invalid freshness period')
    if e['kind'] not in ('material_price', 'benchmark', 'filament_factor', 'grid_factor', 'reference', 'manufacturing'):
        raise ValueError('Unsupported evidence kind')
    if e['kind'] == 'material_price':
        if e['unit'] not in ('INR/kg', 'INR/g') or number(e['data'].get('inr_kg')) is None:
            raise ValueError('Material price must have a normalized nonnegative INR/kg value')
        if e['unit'] == 'INR/g':
            e['data']['inr_kg'] = normalize(e['data']['inr_kg'], 'INR/g', 'INR/kg')
            e['unit'] = 'INR/kg'
    if e['kind'] == 'benchmark':
        if e['data'].get('price_basis') not in ('retail', 'procurement', 'subsidy', 'beneficiary'):
            raise ValueError('Benchmark must distinguish retail/procurement/subsidy/beneficiary price')
        for field in ('price_inr', 'product_mass_g', 'package_mass_g', 'material_consumed_g', 'production_delivery_co2e_kg'):
            if e['data'].get(field) is not None and number(e['data'][field]) is None:
                raise ValueError('Invalid benchmark quantity: '+field)
    if e['kind'] in ('filament_factor', 'grid_factor'):
        field = 'kg_co2e_kg' if e['kind'] == 'filament_factor' else 'kg_co2e_kwh'
        expected = 'kg CO2e/kg filament' if e['kind'] == 'filament_factor' else 'kg CO2e/kWh'
        if e['unit'] != expected or number(e['data'].get(field)) is None or not e['data'].get('boundary'):
            raise ValueError('Emission factors require canonical units and a documented system boundary')
    # Reject NaN/Infinity anywhere in the persisted source snapshot.
    json.dumps(e, allow_nan=False)
    return e


class StructuredData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.current = ''
        self.documents = []
    def handle_starttag(self, tag, attrs):
        if tag == 'script' and dict(attrs).get('type', '').lower() == 'application/ld+json':
            self.active = True
            self.current = ''
    def handle_data(self, data):
        if self.active:
            self.current += data
    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            self.active = False
            try:
                self.documents.append(json.loads(self.current))
            except ValueError:
                pass


def parse_offer(text, identity):
    parser = StructuredData()
    parser.feed(text)
    def walk(value):
        if isinstance(value, dict):
            yield value
            for item in value.values():
                yield from walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item)
    prices = []
    availability = None
    for doc in parser.documents:
        for product in walk(doc):
            types = product.get('@type', [])
            types = [types] if isinstance(types, str) else types
            if 'Product' not in types or identity.casefold() not in str(product.get('name', '')).casefold():
                continue
            offers = product.get('offers', [])
            offers = [offers] if isinstance(offers, dict) else offers
            for offer in offers:
                if offer.get('@type') != 'Offer' or offer.get('priceCurrency') != 'INR':
                    continue
                try:
                    price = float(offer['price'])
                except (KeyError, TypeError, ValueError):
                    continue
                if number(price) is None or price <= 0:
                    continue
                prices.append(price)
                availability = offer.get('availability')
    if not prices or len(set(prices)) != 1:
        raise ValueError('No unambiguous INR offer with the expected product identity. Manual verification required.')
    return prices[0], availability


def bounded_get(client, url):
    with client.stream('GET', url) as response:
        response.raise_for_status()
        if response.is_redirect:
            raise ValueError('Source redirect requires manual review')
        data = bytearray()
        for chunk in response.iter_bytes():
            data.extend(chunk)
            if len(data) > 2_000_000:
                raise ValueError('Source response exceeded size limit')
        return data.decode('utf-8', errors='replace')


def shopify_offer(client, e):
    parsed = urlsplit(e['url'])
    origin = f'{parsed.scheme}://{parsed.netloc}'
    # The public Ajax API reports minor currency units. Check active currency with
    # the same client/cookie jar; do not guess from the source's country or symbol.
    cart = json.loads(bounded_get(client, origin+'/cart.js'))
    if cart.get('currency') != 'INR':
        raise ValueError('Storefront currency is not verified INR')
    product = json.loads(bounded_get(client, e['url']+'.js'))
    if str(product.get('title', '')).casefold().strip() != e['refresh']['identity'].casefold().strip():
        raise ValueError('Product identity changed; manual review required')
    expected_id = e['refresh'].get('product_id')
    if expected_id and product.get('id') != expected_id:
        raise ValueError('Product ID changed; manual review required')
    prices = [product.get(k) for k in ('price', 'price_min', 'price_max')]
    if any(number(p) is None or p <= 0 or not isinstance(p, int) for p in prices) or len(set(prices)) != 1:
        raise ValueError('Variant price range or invalid Shopify minor-unit price')
    return prices[0]/100, 'in_stock' if product.get('available') is True else 'out_of_stock'


def refresh_evidence(store, e, transport=None, force=False):
    # Only bundled, reviewed URLs have refresh permission. Imported sources stay manual.
    approved = {d['id']: d for d in json.loads(SEED.read_text())}
    base = approved.get(e['id'])
    method = e.get('refresh', {}).get('method', 'manual')
    previous = store.refresh_status().get(e['id'])
    if previous and not force and (datetime.now(timezone.utc)-datetime.fromisoformat(previous['attempted_at'])).total_seconds() < 3600:
        return {'id': e['id'], 'status': 'cached_attempt', 'message': 'Refresh attempted within the last hour.'}
    try:
        if not base or base['url'] != e['url'] or base.get('refresh') != e.get('refresh') or method not in ('jsonld_offer', 'shopify'):
            raise ValueError('Manual source review required; last verified values retained.')
        with httpx.Client(timeout=12, follow_redirects=False, transport=transport, headers={'User-Agent': 'ReForm3D evidence review/1.0'}) as client:
            if method == 'shopify':
                price, availability = shopify_offer(client, e)
            else:
                price, availability = parse_offer(bounded_get(client, e['url']), e['refresh']['identity'])
        updated = deepcopy(e)
        updated['data'][e['refresh']['price_field']] = price/e['refresh']['quantity']
        if updated['data'].get('pack_quantity'):
            updated['data']['pack_price_inr'] = price
        updated['data']['availability'] = availability
        updated['verified'] = True
        updated['reliability'] = 'primary publisher; structured offer checked'
        updated['retrieved_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
        updated['retrieval_method'] = 'Publisher Shopify public Ajax product and cart currency APIs; product identity and INR checked' if method == 'shopify' else 'Publisher Product JSON-LD; exact identity and INR offer checked'
        version = store.add_evidence(updated)
        result = {'id': e['id'], 'status': 'verified', 'message': 'Structured offer checked and versioned.', 'version': version}
    except Exception as exc:
        result = {'id': e['id'], 'status': 'unavailable', 'message': str(exc)[:300]}
    store.record_refresh(e['id'], result['status'], result['message'])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--list', action='store_true')
    group.add_argument('--refresh', action='store_true')
    group.add_argument('--import', dest='import_file', type=Path)
    parser.add_argument('--id', help='Limit refresh to a single reviewed source')
    parser.add_argument('--force', action='store_true', help='Ignore one-hour retry cache')
    args = parser.parse_args()
    from .store import Store
    from .config import get_settings
    store = Store(get_settings().data_dir)
    try:
        if args.import_file:
            records = json.loads(args.import_file.read_text())
            # Validate the whole batch before any write.
            validated = [validate_evidence(e) for e in records]
            print(json.dumps([{'id': e['id'], 'version': store.add_evidence(e)} for e in validated]))
        elif args.refresh:
            print(json.dumps([refresh_evidence(store, e, force=args.force) for e in store.evidence_catalog() if not args.id or e['id'] == args.id], indent=2))
        else:
            print(json.dumps(store.evidence_catalog(), indent=2))
    finally:
        store.close()

if __name__ == '__main__':
    main()
