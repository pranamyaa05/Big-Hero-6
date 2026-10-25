"""Standalone Playwright check; run with the backend virtualenv after installing Chromium."""
import functools
import http.server
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from playwright.sync_api import sync_playwright, expect
ROOT = Path(__file__).resolve().parents[2]
def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]
def main():
    ap, wp = port(), port()
    api = f'http://127.0.0.1:{ap}'
    server = http.server.ThreadingHTTPServer(('127.0.0.1', wp), functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT/'frontend/www')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    with tempfile.TemporaryDirectory(prefix='rf-browser-') as data:
        env = {k:v for k,v in os.environ.items() if not k.startswith('REFORM3D_')}
        env.update(REFORM3D_DATA_DIR=data, REFORM3D_ENABLE_LLM='false', REFORM3D_SLICER='off', REFORM3D_RATE_LIMIT='0')
        def start():
            proc = subprocess.Popen([sys.executable,'-m','uvicorn','app.main:app','--host','127.0.0.1','--port',str(ap)], cwd=ROOT/'backend', env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            for _ in range(150):
                try:
                    urllib.request.urlopen(api+'/health', timeout=1)
                    return proc
                except Exception:
                    if proc.poll() is not None: raise RuntimeError(proc.stderr.read().decode())
                    time.sleep(.1)
            raise RuntimeError('Backend did not start')
        proc = start()
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(args=['--enable-unsafe-swiftshader'])
                page = browser.new_page(viewport={'width':1280,'height':900}, reduced_motion='reduce')
                errors=[]
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(f'http://127.0.0.1:{wp}/?api={api}')
                button=page.get_by_role('button',name='History',exact=True)
                expect(button).to_be_visible(timeout=60000)
                job=page.evaluate('''async api => {const rf=new ReForm3D(api); const job=await rf.build('pen-grip'); document.dispatchEvent(new Event('rf-job-finished')); return job;}''',api)
                assert job['status']=='done'
                button.click()
                expect(page.locator('.rf-history-card')).to_have_count(1)
                page.get_by_role('button',name='View Impact ↗').click()
                expect(page.locator('.rf-impact-chart')).to_have_count(3)
                expect(page.locator('#rfImpactHeading')).to_contain_text(job['result']['part_name'])
                expect(page.locator('.rf-market')).to_be_visible()
                expect(page.locator('.rf-research-status')).to_contain_text('not configured')
                expect(page.locator('.rf-impact-chart').nth(1)).to_contain_text('Data unavailable')
                page.get_by_text('Bill of Materials',exact=False).first.click()
                expect(page.locator('.rf-impact-table')).to_contain_text('Known subtotal')
                page.get_by_text('Manufacturing inputs',exact=False).first.click()
                for key,value in {'printer_watts':100,'tariff_inr_kwh':10,'extra_print_waste_g':0,'failure_rate':0,
                                  'labor_minutes':0,'labor_inr_hour':0,'machine_inr_hour':0,'setup_inr':0,'consumables_inr':0,'postprocess_inr':0}.items():
                    page.locator(f'[name="{key}"]').fill(str(value))
                page.locator('[name="no_components"]').check()
                page.locator('[name="benchmark_id"]').select_option('medilab-pencil-grip')
                page.locator('[name="benchmark_confirmed"]').check()
                page.locator('[name="notes"]').fill('Browser regression scenario: 100 W assumed, tariff 10 INR/kWh, zero labor/overhead/waste/components. Selected specialized ergonomic grip and synthetic equivalence confirmation for testing only; not a production quote or fit validation.')
                page.get_by_role('button',name='Save inputs & recalculate').click()
                expect(page.locator('.rf-impact-chart').first).to_contain_text('Modelled comparison')
                expect(page.locator('.rf-impact-chart').first).to_contain_text('₹530')
                expect(page.locator('.rf-impact-chart').first.locator('.rf-impact-rail i')).to_have_count(2)
                page.get_by_text('Bill of Materials',exact=False).first.click()
                expect(page.locator('.rf-impact-table tfoot')).to_contain_text('Complete estimated production cost')
                expect(page.locator('.rf-market-donut svg')).to_be_visible()
                page.locator('#rfHistory').evaluate('(e)=>e.scrollTop=0')
                page.screenshot(path=str(ROOT/'frontend/impact-desktop.png'),full_page=False)
                page.set_viewport_size({'width':360,'height':800})
                assert page.locator('#rfHistory').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
                page.screenshot(path=str(ROOT/'frontend/impact-mobile.png'))
                page.get_by_role('button',name='← Back to history').click()
                expect(page.locator('.rf-history-card')).to_have_count(1)
                page.set_viewport_size({'width':1280,'height':900})
                grams=f"{job['result']['estimate']['filament_g']} g"
                expect(page.locator('.rf-history-card')).to_contain_text(grams)
                page.get_by_role('tab',name='Statistics',exact=True).click()
                expect(page.locator('#rfStatisticsDesign')).to_be_visible()
                expect(page.locator('#rfStatisticsImpact .rf-impact-chart')).to_have_count(3)
                expect(page.locator('#rfStatisticsImpact #rfImpactHeading')).to_contain_text(job['result']['part_name'])
                expect(page.locator('.rf-history-metrics')).not_to_be_visible()
                page.get_by_text('History totals',exact=False).first.click()
                expect(page.locator('.rf-history-metrics')).to_contain_text(grams)
                page.keyboard.press('Escape')
                expect(page.locator('#rfHistory')).not_to_be_visible()
                proc.terminate();proc.wait(timeout=15);proc=start()
                page.reload();button.click()
                page.get_by_role('tab',name='History',exact=True).click()
                expect(page.locator('.rf-history-card')).to_have_count(1)
                page.locator('[data-open]').click()
                expect(page.locator('#rfHistory')).not_to_be_visible()
                expect(page.locator('#rfOut')).to_contain_text(job['result']['part_name'])
                button.click();page.set_viewport_size({'width':360,'height':800})
                expect(page.locator('.rf-history-card')).to_be_visible()
                assert page.locator('#rfHistory').evaluate('(e)=>e.scrollWidth<=e.clientWidth+1')
                page.screenshot(path=str(ROOT/'frontend/history-mobile.png'))
                page.keyboard.press('Escape')
                b,n=button.bounding_box(),page.locator('.nav').bounding_box()
                assert b['x']>=n['x']+n['width'] or b['y']>=n['y']+n['height'],(b,n)
                button.click();page.on('dialog',lambda d:d.accept())
                page.get_by_role('button',name='Clear my history').click()
                expect(page.locator('#rfHistoryContent')).to_contain_text('Make a part to start your history.')
                page.keyboard.press('Escape');button.click();page.go_back()
                expect(page.locator('#rfHistory')).not_to_be_visible()
                assert not errors,errors
                browser.close()
                print('Browser checks passed: impact charts/BOM/input save, mobile impact, template, statistics, reopen, Esc, Back, clear, restart, 360px.')
        finally:
            proc.terminate();proc.wait(timeout=15);server.shutdown()
if __name__=='__main__':main()
