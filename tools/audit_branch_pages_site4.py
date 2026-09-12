"""Branch facts, media, discoverability and non-branch preservation checks."""
from __future__ import annotations
import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit, quote
from urllib.request import urlopen
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from branch_site4_support import ROOT, DOMAIN, without_navigation
from branch_templates_site4 import FEES, branch_path, subject_summary

DATA = ROOT / 'tools/data/branches'
REPORTS = ROOT / 'tools/reports/branches'


def norm(text):
    return ' '.join(text.split())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-url')
    parser.add_argument('--skip-legacy', action='store_true', help='After a full audit, rerun only branch checks when old HTML has not changed.')
    args = parser.parse_args()
    data = json.loads((DATA / 'snapshot.json').read_text(encoding='utf-8'))
    generation = json.loads((REPORTS / 'generation.json').read_text(encoding='utf-8'))
    assets = json.loads((DATA / 'assets.json').read_text(encoding='utf-8'))
    baseline = json.loads((DATA / 'legacy-baseline.json').read_text(encoding='utf-8'))
    errors, checks, photo_count, faq_count = [], 0, 0, 0
    def check(test, label):
        nonlocal checks
        checks += 1
        if not test:
            errors.append(label)
    paths = generation['paths']
    child_manifest = ROOT / 'tools/data/branch-topics/manifest.json'
    children = json.loads(child_manifest.read_text(encoding='utf8'))['pages'] if child_manifest.exists() else []
    child_paths = [x['path'] for x in children]
    check(len(child_paths) == len(set(child_paths)), 'unique manifest child paths')
    centers = {branch_path(c): c for c in data['centers']}
    check(len(paths) == 210 and len(centers) == 193, 'branch/region counts')
    actual = ['/' + p.parent.relative_to(ROOT).as_posix() + '/' for p in (ROOT / '지점안내').rglob('index.html')]
    check(set(actual) == set(paths + child_paths), 'no missing/extra branch descendants outside explicit manifests')
    titles, descriptions = [], []
    soup_by_path = {}
    for path in paths:
        soup = BeautifulSoup((ROOT / path.strip('/') / 'index.html').read_bytes(), 'html.parser')
        soup_by_path[path] = soup
        canonical = DOMAIN + quote(path, safe='/')
        check(len(soup.select('h1')) == 1, path + ': one H1')
        check(len(soup.select('title')) == 1, path + ': one title')
        titles.append(soup.title.get_text())
        descriptions.append(soup.select_one('meta[name="description"]')['content'])
        check(soup.select_one('link[rel="canonical"]')['href'] == canonical, path + ': canonical')
        check(soup.select_one('meta[property="og:url"]')['content'] == canonical, path + ': og:url')
        check(not soup.select('[name="robots"][content*="noindex"]'), path + ': indexable')
        check(len(soup.select('.main-nav [href="/지점안내/"]')) == 1, path + ': branch menu')
        check(len(soup.select('.floating-actions a')) == 3, path + ': same contact controls')
        check(not re.search(r'010[- ]?\d{4}[- ]?\d{4}', soup.get_text(' ', strip=True)), path + ': no visible phone-number text')
        ids = [n['id'] for n in soup.select('[id]')]
        check(len(ids) == len(set(ids)), path + ': unique DOM ids')
        for a in soup.select('a[href]'):
            u = urlsplit(a['href'])
            if u.scheme or u.netloc:
                continue
            target_path = unquote(u.path) or path
            check(target_path.startswith('/'), path + ': root relative ' + a['href'])
            target = ROOT / target_path.lstrip('/')
            if target.is_dir():
                target = target / 'index.html'
            check(target.is_file(), path + ': destination ' + a['href'])
            if u.fragment and not u.path:
                check(unquote(u.fragment) in ids, path + ': anchor ' + u.fragment)
        graph = json.loads(soup.select_one('script[type="application/ld+json"]').string)['@graph']
        graph_ids = [n['@id'] for n in graph if '@id' in n]
        check(len(graph_ids) == len(set(graph_ids)), path + ': unique schema ids')
        check(all(x.startswith(DOMAIN) for x in graph_ids), path + ': target schema domain')
        check(not any(n['@type'] in ('Review', 'AggregateRating') for n in graph), path + ': no invented reviews')
        html_faq = [(norm(x.summary.get_text(' ', strip=True)), norm(x.p.get_text(' ', strip=True))) for x in soup.select('.branch-faq details')]
        json_faq = [(norm(q['name']), norm(q['acceptedAnswer']['text'])) for n in graph if n['@type'] == 'FAQPage' for q in n['mainEntity']]
        check(html_faq == json_faq, path + ': visible FAQ matches JSON-LD')
        faq_count += len(html_faq)
        for image in soup.select('img'):
            check(image.get('alt') and image.get('width') and image.get('height'), path + ': image alt and dimensions')
            check((ROOT / unquote(image['src']).lstrip('/')).is_file(), path + ': image file ' + image['src'])
        if path in centers:
            c = centers[path]
            ref = data['reference'][c['id']]
            check(soup.title.get_text() == c['displayName'], path + ': exact branch title')
            check(norm(soup.h1.get_text(' ', strip=True)) == norm(c['displayName']), path + ': exact branch H1')
            check(norm(c['address']) in norm(soup.select_one('#center-info').get_text(' ', strip=True)), path + ': address')
            for source_field in ('registeredAcademyName', 'registrationNumber'):
                check(not c[source_field] or norm(c[source_field]) in norm(soup.select_one('#center-info').get_text(' ', strip=True)), path + ': ' + source_field)
            rows = soup.select('#programs .branch-subject-row')
            check(len(rows) == len(c['subjects']), path + ': subject count')
            for row, (name, course) in zip(rows, c['subjects'].items()):
                check(row.strong.get_text() == name and row.select_one('.branch-grade-range').get_text() == subject_summary(c, name, course, ref), path + ': subject grades ' + name)
            policy = '서울' if c['region']['province'] == '서울' else '서울 외'
            displayed_fees = [x.get_text() for x in soup.select('#tuition dd')]
            expected_fees = [f'{n:,}원' for amounts in FEES[policy].values() for n in amounts]
            check(displayed_fees == expected_fees, path + ': user tuition')
            media = soup.select('.branch-primary-media img')
            expected_media = [ref['primaryMedia'][k] for k in ('body', 'map') if ref.get('primaryMedia', {}).get(k)]
            check([x['src'] for x in media] == [x['src'] for x in expected_media], path + ': body then map')
            for img, kind in zip(media, ('본문', '지도')):
                check(img['alt'] == c['displayName'] + ' ' + kind, path + ': primary alt')
                if kind == '본문':
                    check(not img.find_parent('details') and not img.get('style') and not img.has_attr('hidden'), path + ': full visible body image')
            gallery = soup.select('.branch-gallery img')
            expected_photos = ref.get('images', [])
            check([x['src'] for x in gallery] == [x['localSrc'] for x in expected_photos], path + ': matched local photo gallery')
            photo_count += len(gallery)
            if gallery:
                disclosure = soup.select_one('#learning-space details')
                check(disclosure is not None and not disclosure.has_attr('open'), path + ': gallery initially collapsed')
                check(soup.select('main section')[-1]['id'] == 'learning-space', path + ': gallery last section')
            expected_children = {x['path'] for x in children if x['parentPath'] == path}
            listed_children = [a['href'] for a in soup.select('#neighborhood-pages a')]
            check(set(listed_children) == expected_children and len(listed_children) == len(expected_children), path + ': exact requested child navigation')
            check(not soup.select('#child-pages'), path + ': no deeper grade hierarchy requested')
            if expected_children:
                check(soup.select_one('#questions').find_next_sibling('section').get('id') == 'neighborhood-pages', path + ': children immediately after FAQ')
    check(len(set(titles)) == len(titles), 'unique titles across 210 pages')
    check(len(set(descriptions)) == len(descriptions), 'unique meta descriptions across 210 pages')
    # Every old HTML byte is unchanged after removing only the marked nav addition.
    def legacy_result(item):
        relative, expected_hash = item
        raw = (ROOT / relative).read_bytes().decode('utf-8')
        return relative, hashlib.sha256(without_navigation(raw).encode('utf-8')).hexdigest() == expected_hash, raw.count('data-branch-directory-link="true"') == 2
    if not args.skip_legacy:
        with ThreadPoolExecutor(max_workers=6) as pool:
            for relative, preserved, linked in pool.map(legacy_result, baseline.items()):
                check(preserved, 'legacy body preserved: ' + relative)
                check(linked, 'legacy header/footer link: ' + relative)
    for src, info in assets.items():
        path = ROOT / src.lstrip('/')
        check(path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == info['sha256'], 'original asset bytes: ' + src)
    urls = [unquote(n.text) for n in ET.parse(ROOT / 'sitemap.xml').getroot().iter() if n.tag.endswith('}loc')]
    check(len(urls) == len(set(urls)) == len(baseline) + len(paths) + len(child_paths), 'sitemap unique total')
    check(all(DOMAIN + p in urls for p in child_paths), 'all requested descendants in sitemap')
    check(all(DOMAIN + p in urls for p in paths), 'all branches in sitemap')
    rss = ET.parse(ROOT / 'rss.xml')
    check(bool(rss.findall('.//item')), 'RSS parses with entries')
    http = []
    if args.base_url:
        base = args.base_url.rstrip('/')
        assert urlsplit(base).hostname in ('localhost', '127.0.0.1'), 'This audit is local-only'
        def fetch(path):
            with urlopen(base + quote(path, safe='/'), timeout=30) as res:
                return {'path': path, 'status': res.status, 'bytes': len(res.read())}
        with ThreadPoolExecutor(max_workers=6) as pool:
            http = list(pool.map(fetch, paths + ['/assets/branches.css', '/assets/branches-site4.css', '/assets/branch-search.js', '/assets/branch-navigation.css', '/sitemap.xml', '/rss.xml']))
        check(all(r['status'] == 200 for r in http), 'local HTTP success')
    report = {'status': 'PASS' if not errors else 'FAIL', 'checks': checks, 'errors': errors,
              'pages': len(paths), 'centers': len(centers), 'legacyHtmlPreserved': len(baseline),
              'uniqueAssets': len(assets), 'branchPhotos': photo_count, 'visibleFaqs': faq_count,
              'legacyCheckPerformed': not args.skip_legacy,
              'sitemapUrls': len(urls), 'rssItems': len(rss.findall('.//item')), 'http': http}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / ('audit-branch-only.json' if args.skip_legacy else 'audit.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('http', 'errors')}, ensure_ascii=False, indent=2))
    if errors:
        print(json.dumps({'errorCount': len(errors), 'firstErrors': errors[:15]}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if errors else 0)


if __name__ == '__main__':
    main()
