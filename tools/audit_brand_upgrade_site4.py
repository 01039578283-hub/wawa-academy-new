"""Audit the bounded brand release without rewriting site files or using a browser."""
from __future__ import annotations
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import urlopen
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup as Soup
from upgrade_brand_site4 import ROOT, DATA, REPORTS, BASE, DOMAIN, read, digest, dump, text, graph, kind, faq, fixed, protect

checks = []
metrics = {}
cache = {}


def check(label, condition, detail=None):
    checks.append({'check': label, 'pass': bool(condition), **({'detail': detail} if not condition else {})})


def parse(rel):
    if rel not in cache:
        cache[rel] = Soup(read(ROOT / rel), 'html.parser')
    return cache[rel]


def resolve(url, base):
    full = urlsplit(urljoin(base, url))
    if full.scheme not in ('http', 'https') or full.hostname != urlsplit(DOMAIN).hostname:
        return None
    path = ROOT / unquote(full.path).lstrip('/')
    if path.is_dir():
        path /= 'index.html'
    assert path.resolve().is_relative_to(ROOT.resolve()), str(path)
    return path, unquote(full.fragment)


def walk(value):
    if isinstance(value, dict):
        yield value
        for v in value.values():
            yield from walk(v)
    elif isinstance(value, list):
        for v in value:
            yield from walk(v)


def page_audit(item):
    rel = item['path']
    soup = parse(rel)
    raw_original = subprocess.check_output(['git', 'show', f'{BASE}:{rel}'], cwd=ROOT).decode('utf-8')
    original = Soup(raw_original, 'html.parser')
    current_fixed, original_fixed = fixed(soup), fixed(original)
    current_nodes = graph(soup)
    ids = [e['id'] for e in soup.select('[id]')]
    check(rel + ': one H1/main/title/canonical', all(len(soup.select(s)) == 1 for s in ['h1','main','title','link[rel=canonical]']))
    check(rel + ': unique HTML IDs', len(ids) == len(set(ids)), [x for x,c in Counter(ids).items() if c > 1])
    check(rel + ': canonical/OG/image/contact/verification preserved', all(current_fixed[k] == original_fixed[k] for k in ['canonical','ogUrl','ogImage','contact','verification']))
    check(rel + ': indexable server HTML', 'noindex' not in str(soup.select_one('meta[name=robots]')) and soup.html.get('lang') == 'ko' and len(text(soup.main)) > 500)
    check(rel + ': usable metadata', 10 <= len(text(soup.title)) <= 65 and 35 <= len(soup.select_one('meta[name=description]')['content']) <= 180 and text(soup.title) == soup.select_one('meta[property="og:title"]')['content'])
    check(rel + ': no nested links/buttons/details', not soup.select('a a, a button, p h2, p h3, summary a, summary button'))
    check(rel + ': bounded assets loaded once', len(soup.select('link[href^="/assets/brand-learning-v2.css"]')) == 1 and len(soup.select('script[src^="/assets/brand-learning-v2.js"]')) == 1)
    check(rel + ': no iframe/remote player added', len(soup.select('iframe')) == len(original.select('iframe')) == 0)
    if item['mode'] == 'hub':
        check(rel + ': original topic/title/FAQ/center/region content retained', current_fixed == original_fixed and protect(soup) == protect(original))
        brief = json.loads(read(DATA/'hub-briefs.json'))[rel]
        actual = soup.select_one('#hub-coaching-brief')
        check(rel + ': two contextual deep links', [(a['href'], text(a).removesuffix('→').strip()) for a in actual.select('a')] == [tuple(x) for x in brief['links']])
        element = next(n for n in current_nodes if n.get('@id') == item['url'] + '#hub-coaching-brief')
        check(rel + ': schema brief equals visible copy', element['text'] == ' '.join(text(p) for p in actual.select('p:not(.wa-kicker)')) and element['name'] == text(actual.h2))
    else:
        check(rel + ': removed writing-only text', not re.search(r'구조로 (설계|만들었)|JSON-LD|FAQPage|홈페이지입니다|SEO|AEO|GEO', text(soup.main)))
        old_destinations = {unquote(urljoin(item['url'], a['href'])).split('#')[0] for a in original.select('a[href]') if not a['href'].startswith('#')}
        new_destinations = {unquote(urljoin(item['url'], a['href'])).split('#')[0] for a in soup.select('a[href]')}
        check(rel + ': previous navigation destinations retained', old_destinations <= new_destinations, sorted(old_destinations - new_destinations))
        check(rel + ': explicit program and center boundary', '센터마다 다릅니다' in text(soup.main) or '센터별로 다릅니다' in text(soup.main))
    schema_faq = [q for n in current_nodes if kind(n,'FAQPage') for q in n.get('mainEntity',[])]
    check(rel + ': FAQ schema equals visible questions and answers', schema_faq == faq(soup))
    node_ids = [n['@id'] for n in current_nodes if '@id' in n]
    check(rel + ': unique JSON-LD IDs', len(node_ids) == len(set(node_ids)))
    errors = []
    for node in walk(current_nodes):
        if '@id' in node and set(node) == {'@id'}:
            ref = node['@id']
            if unquote(ref).split('#')[0] == unquote(item['url']) and ref not in node_ids:
                errors.append(ref)
    check(rel + ': local JSON-LD references resolve', not errors, errors)
    web = next(n for n in current_nodes if kind(n,'WebPage'))
    bad_parts = []
    for part in web.get('hasPart', []):
        node = next((n for n in current_nodes if n.get('@id') == part.get('@id')), part)
        url = node.get('url', node.get('@id', ''))
        fragment = unquote(urlsplit(url).fragment)
        if fragment and fragment not in ids:
            bad_parts.append(url)
    check(rel + ': page sections point to real anchors', not bad_parts, bad_parts)
    check(rel + ': no invented universal hours/search action', not any(n.get('potentialAction') for n in current_nodes if kind(n,'WebSite')) and not any(n.get('openingHours') or n.get('openingHoursSpecification') for n in current_nodes if n.get('@id') == DOMAIN + '/#organization'))
    bad_links = []
    for a in soup.select('a[href], link[href], script[src], img[src], option[data-url]'):
        url = a.get('href', a.get('src', a.get('data-url')))
        target = resolve(url, item['url'])
        if not target:
            continue
        path, fragment = target
        if not path.is_file():
            bad_links.append(url)
        elif fragment and path.suffix == '.html' and not parse(path.relative_to(ROOT).as_posix()).find(id=fragment):
            bad_links.append(url)
    check(rel + ': internal links/files/anchors valid', not bad_links, bad_links[:20])
    images = soup.select('main img')
    check(rel + ': images have meaningful alt and dimensions', all(im.get('alt') and im.get('width') and im.get('height') for im in images))
    metrics[rel] = {'title': text(soup.title), 'characters': len(text(soup.main)), 'FAQ': len(faq(soup)), 'images': len(images), 'internalLinks': sum(bool(resolve(a['href'], item['url'])) for a in soup.select('main a[href]'))}


def main():
    generation = json.loads(read(REPORTS/'generation.json'))
    targets = generation['targets']
    check('exactly 29 reviewed pages', len(targets) == 29)
    for item in targets:
        page_audit(item)
    changed = subprocess.check_output(['git','-c','core.quotepath=false','diff','--name-only'],cwd=ROOT,stderr=subprocess.DEVNULL).decode('utf-8').splitlines()
    expected = {i['path'] for i in targets} | {'sitemap.xml','rss.xml','llms.txt'}
    check('tracked changes limited to reviewed pages and discovery', set(changed) == expected, sorted(set(changed) ^ expected))
    all_files = subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf-8').split('\0')
    total_html = sum(p.endswith('index.html') for p in all_files)
    check('other HTML unchanged', total_html == 9778 and not (set(changed) - expected))
    briefs = json.loads(read(DATA/'hub-briefs.json'))
    check('27 distinct brief headings and paragraph bodies', len({b['heading'] for b in briefs.values()}) == len({tuple(b['paragraphs']) for b in briefs.values()}) == 27)
    for path, selector in [('sitemap.xml','{*}url/{*}loc'),('rss.xml','./channel/item/link')]:
        before = ET.fromstring(subprocess.check_output(['git','show',f'{BASE}:{path}'],cwd=ROOT))
        after = ET.fromstring(read(ROOT/path))
        check(path + ': URL inventory and order preserved', [n.text for n in before.findall(selector)] == [n.text for n in after.findall(selector)])
    original_map = ET.fromstring(subprocess.check_output(['git','show',f'{BASE}:sitemap.xml'],cwd=ROOT))
    new_map = ET.fromstring(read(ROOT/'sitemap.xml'))
    target_urls = {unquote(i['url']) for i in targets}
    changed_map = [unquote(a.findtext('{*}loc')) for a,b in zip(original_map,new_map) if ET.tostring(a) != ET.tostring(b)]
    check('sitemap only actual 29 content dates updated', set(changed_map) == target_urls, changed_map)
    manifest = json.loads(read(DATA/'sources.json'))
    for im in manifest['assets']:
        check(im['file'] + ': verified original image bytes', digest((ROOT/'assets/official-learning'/im['file']).read_bytes()) == im['sha256'])
    resource_paths = [i['path'] for i in targets] + ['assets/site.css','assets/site.js','assets/hub-guide-v1.css','assets/brand-learning-v2.css','assets/brand-learning-v2.js','sitemap.xml','rss.xml','llms.txt'] + ['assets/official-learning/'+i['file'] for i in manifest['assets']]
    def local_http(path):
        uri = '/' + path.removesuffix('index.html') if path.endswith('index.html') else '/' + path
        try:
            with urlopen('http://127.0.0.1:8797' + quote(uri, safe='/'), timeout=15) as response:
                return {'path': path, 'status': response.status, 'matchesLocal': digest(response.read()) == digest((ROOT/path).read_bytes())}
        except Exception as e:
            return {'path': path, 'error': str(e)}
    with ThreadPoolExecutor(max_workers=4) as pool:
        responses = list(pool.map(local_http,resource_paths))
    check('local HTTP/resources exactly match local files', all(r.get('status') == 200 and r.get('matchesLocal') for r in responses), [r for r in responses if not r.get('matchesLocal')])
    report = {'baseline':BASE,'scope':len(targets),'htmlUnchanged':total_html-len(targets),'checks':len(checks),'passed':sum(c['pass'] for c in checks),'failed':[c for c in checks if not c['pass']],'pages':metrics,'http':responses}
    dump(REPORTS/'static-audit.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('pages','http')},ensure_ascii=False,indent=2))
    raise SystemExit(bool(report['failed']))


if __name__ == '__main__':
    main()
