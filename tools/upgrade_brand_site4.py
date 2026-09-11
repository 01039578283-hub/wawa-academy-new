"""Local, bounded postprocessor for two core pages and 27 existing editorial hubs.

Run AFTER enrich_top_hubs_site4.py if legacy hub content is regenerated.
Never edits locality/region manuscripts, contact destinations or hosting settings.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from email.utils import format_datetime
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import subprocess
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup as Soup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'tools/data/brand-upgrade-20260911'
REPORTS = ROOT / 'tools/reports/brand-upgrade'
DOMAIN = 'https://xn--ol5ba64b839b.com'
BASE = '28a48fcd38db0ccad44918b7c17e42532bf763c9'
CSS = '/assets/brand-learning-v2.css?v=20260911-1'
JS = '/assets/brand-learning-v2.js?v=20260911-1'
CORE = {
    'index.html': {
        'fragment': 'home.html', 'mode': 'home',
        'title': '와와학습코칭학원 | 초중고 맞춤 코칭·AI 학습 안내',
        'description': '초중고 학습코칭의 4C 과정과 AI 영어·수학·국어·독서, 학습 공간과 공식 영상을 살펴보세요. 과목·학년별 지역 안내에서 가까운 센터를 확인할 수 있습니다.',
    },
    '학습코칭/index.html': {
        'fragment': 'coaching.html', 'mode': 'coaching',
        'title': '와와 학습코칭 | 4C 진단·복습 관리·AI 활용',
        'description': '와와 4C 진단·처방·지도·상담과 플랜·학습·생활 관리, AI 과목별 대상·구성을 안내합니다. 학생의 복습 기록과 센터 상담 준비 방법을 확인하세요.',
    },
}


def read(path):
    return path.read_bytes().decode('utf-8-sig').replace('\r\n', '\n')


def digest(value):
    return hashlib.sha256(value).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def write_if_changed(path, value):
    original = path.read_bytes()
    newline = '\r\n' if b'\r\n' in original else '\n'
    encoded = value.replace('\r\n', '\n').replace('\n', newline).encode('utf-8')
    if encoded != original:
        path.write_bytes(encoded)
    return original != encoded


def kind(node, name):
    types = node.get('@type', [])
    return name in ([types] if isinstance(types, str) else types)


def text(node):
    return node.get_text(' ', strip=True)


def graph(soup):
    result = []
    for script in soup.select('script[type="application/ld+json"]'):
        value = json.loads(script.get_text())
        result.extend(value.get('@graph', [value]) if isinstance(value, dict) else value)
    return result


def faq(soup):
    items = soup.select('.wa-faq-list details, #hub-faq-list details')
    return [{'@type': 'Question', 'name': text(item.summary), 'acceptedAnswer': {'@type': 'Answer', 'text': ' '.join(text(p) for p in item.find_all('p'))}} for item in items]


def fixed(soup):
    return {
        'canonical': soup.select_one('[rel=canonical]')['href'],
        'ogUrl': soup.select_one('[property="og:url"]')['content'],
        'ogImage': soup.select_one('[property="og:image"]')['content'],
        'verification': {m['name']: m['content'] for m in soup.select('meta[name$="site-verification"]')},
        'contact': [a['href'] for a in soup.select('.floating-actions a, .footer-contact a, .header-cta')],
        'title': text(soup.title), 'h1': text(soup.h1),
    }


def protect(soup):
    # User-authored guide, navigation, destinations and actual center facts remain intact.
    selectors = ['#hub-directory', '.split-category-section', '#subject-directory', '#grade-directory', '#routine-directory', '#course-directory', '#hub-learning-guide', '#hub-center-examples', '#hub-learning-space', '#hub-answer']
    return {sel: [digest(str(n).encode()) for n in soup.select(sel)] for sel in selectors}


def apply_assets(soup, mode):
    soup.body['class'] = list(dict.fromkeys(soup.body.get('class', []) + ['wa-upgrade-page', f'wa-{mode}-page']))
    for selector in ['link[href^="/assets/brand-learning-v2.css"]', 'script[src^="/assets/brand-learning-v2.js"]']:
        for old in soup.select(selector):
            old.decompose()
    soup.head.append(soup.new_tag('link', rel='stylesheet', href=CSS))
    script = soup.new_tag('script', src=JS, defer='')
    # Capture listener is independent of registration order relative to legacy code.
    soup.body.append(script)


def update_core_schema(soup, original, config, modified):
    canonical = soup.select_one('[rel=canonical]')['href']
    website = deepcopy(next(n for n in original if kind(n, 'WebSite')))
    website.pop('potentialAction', None)  # No ?s= endpoint exists on this static site.
    org = deepcopy(next(n for n in original if n.get('@id') == DOMAIN + '/#organization'))
    org.pop('openingHours', None)
    org.pop('openingHoursSpecification', None)
    page_id = canonical + '#webpage'
    page = {'@type': 'WebPage', '@id': page_id, 'url': canonical,
            'name': config['title'], 'description': config['description'], 'inLanguage': 'ko-KR',
            'isPartOf': {'@id': website['@id']}, 'publisher': {'@id': org['@id']},
            'dateModified': modified, 'breadcrumb': {'@id': canonical + '#breadcrumb'},
            'about': [{'@id': org['@id']}],
            'mentions': [{'@type': 'Thing', 'name': name} for name in ['4C 학습코칭', '플랜·학습·생활 관리', 'AI 영어', 'AI 수학', 'AI 국어', 'AI 독서']]}
    breadcrumb_items = [{'@type': 'ListItem', 'position': 1, 'name': '홈', 'item': DOMAIN + '/'}]
    if config['mode'] != 'home':
        breadcrumb_items.append({'@type': 'ListItem', 'position': 2, 'name': '학습코칭', 'item': canonical})
    crumbs = {'@type': 'BreadcrumbList', '@id': canonical + '#breadcrumb', 'itemListElement': breadcrumb_items}
    nodes = [website, org, page, crumbs]
    elements = []
    for section in soup.select('main > section[id]'):
        heading = section.find(['h1', 'h2'])
        elements.append({'@type': 'WebPageElement', '@id': canonical + '#' + section['id'], 'url': canonical + '#' + section['id'], 'name': text(heading), 'isPartOf': {'@id': page_id}})
    page['hasPart'] = [{'@id': n['@id']} for n in elements]
    nodes.extend(elements)
    qa = {'@type': 'FAQPage', '@id': canonical + '#faq-data', 'url': canonical + '#faq', 'isPartOf': {'@id': page_id}, 'mainEntity': faq(soup)}
    nodes.append(qa)
    if config['mode'] == 'coaching':
        article_id = canonical + '#article'
        page['mainEntity'] = {'@id': article_id}
        nodes.append({'@type': 'Article', '@id': article_id, 'headline': text(soup.h1), 'description': config['description'], 'inLanguage': 'ko-KR', 'mainEntityOfPage': {'@id': page_id}, 'author': {'@id': org['@id']}, 'publisher': {'@id': org['@id']}, 'dateModified': modified,
                      'articleSection': [text(h) for h in soup.main.select('section > .wrap h2')], 'about': deepcopy(page['mentions']), 'hasPart': deepcopy(page['hasPart']), 'image': DOMAIN + '/assets/official-learning/teacher-coaching.png'})
    else:
        page['mainEntity'] = {'@id': org['@id']}
    return nodes


def store_graph(soup, nodes):
    scripts = soup.select('script[type="application/ld+json"]')
    assert scripts
    for script in scripts[1:]:
        script.decompose()
    scripts[0].string = json.dumps({'@context': 'https://schema.org', '@graph': nodes}, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/')


def core_page(rel, config, modified):
    path = ROOT / rel
    before = read(path)
    soup = Soup(before, 'html.parser')
    baseline = fixed(soup)
    if not soup.select_one('main[data-brand-upgrade]'):
        committed = subprocess.check_output(['git', 'show', f'{BASE}:{rel}'], cwd=ROOT).decode('utf-8').replace('\r\n', '\n')
        assert before == committed, f'Unreviewed core-page changes: {rel}'
    original_graph = graph(soup)
    markup = Soup(read(DATA / config['fragment']), 'html.parser').main
    soup.main.replace_with(markup)
    apply_assets(soup, config['mode'])
    soup.title.string = config['title']
    for key, value in [('description', config['description']), ('og:description', config['description']), ('og:title', config['title']), ('twitter:title', config['title']), ('twitter:description', config['description'])]:
        meta = soup.find('meta', attrs={'property' if key.startswith('og:') else 'name': key})
        if meta:
            meta['content'] = value
    # Keep existing contact URLs; make the surrounding copy useful to visitors.
    cta = soup.select_one('.final-cta')
    cta.h2.string = '학생에게 필요한 다음 공부를 함께 정리해 보세요.'
    cta.select_one('p:not(.eyebrow)').string = '현재 학년과 어려운 과목, 최근 공부 기록을 준비하면 상담 질문이 구체적입니다. 실제 개설 과목·시간·비용은 방문할 센터에서 확인해 주세요.'
    cta.select_one('.eyebrow').string = '상담 준비'
    store_graph(soup, update_core_schema(soup, original_graph, config, modified))
    current = fixed(soup)
    assert all(current[k] == baseline[k] for k in ['canonical', 'ogUrl', 'ogImage', 'verification', 'contact'])
    result = str(Soup(str(soup), 'html.parser'))
    return {'path': rel, 'changed': write_if_changed(path, result), 'url': current['canonical'], 'faq': len(faq(soup)), 'mode': config['mode']}


def hub_page(rel, brief, modified):
    path = ROOT / rel
    soup = Soup(read(path), 'html.parser')
    baseline = fixed(soup)
    protected = protect(soup)
    for old in soup.select('[data-brand-hub]'):
        old.decompose()
    esc = html.escape
    links = ''.join(f'<a href="{esc(url, quote=True)}">{esc(label)}<span aria-hidden="true">→</span></a>' for url, label in brief['links'])
    markup = f'<section class="wa-hub-brief" id="hub-coaching-brief" data-brand-hub="brief"><div class="wrap"><div class="wa-hub-brief-inner"><div><p class="wa-kicker">학습 방법도 함께 살펴보기</p><h2>{esc(brief["heading"])}</h2>{"".join("<p>"+esc(p)+"</p>" for p in brief["paragraphs"])}</div><div class="wa-hub-links">{links}</div></div></div></section>'
    soup.select_one('#hub-learning-guide').insert_before(Soup(markup, 'html.parser').section)
    jumps = soup.select_one('.hub-guide-jumps .wrap')
    anchor = soup.new_tag('a', href='#hub-coaching-brief', attrs={'data-brand-hub': 'jump'})
    anchor.string = '코칭·AI 활용'
    jumps.insert(1, anchor)
    apply_assets(soup, 'hub')
    nodes = [n for n in graph(soup) if n.get('@id') != baseline['canonical'] + '#hub-coaching-brief']
    page = next(n for n in nodes if kind(n, 'WebPage'))
    page['dateModified'] = modified
    part_id = baseline['canonical'] + '#hub-coaching-brief'
    page['hasPart'] = [p for p in page.get('hasPart', []) if p.get('@id') != part_id] + [{'@id': part_id}]
    old_topic_names = {n.get('name') for n in page.get('mentions', [])}
    page['mentions'] = page.get('mentions', []) + [{'@type': 'Thing', 'name': name} for name in brief['topics'] if name not in old_topic_names]
    for node in nodes:
        if kind(node, 'Article'):
            node['dateModified'] = modified
            sections = node.get('articleSection', [])
            node['articleSection'] = sections + ([brief['heading']] if brief['heading'] not in sections else [])
    nodes.append({'@type': 'WebPageElement', '@id': part_id, 'url': part_id,
                  'name': brief['heading'], 'text': ' '.join(brief['paragraphs']),
                  'isPartOf': {'@id': page['@id']},
                  'about': [{'@type': 'Thing', 'name': name} for name in brief['topics']]})
    page['significantLink'] = list(dict.fromkeys(page.get('significantLink', []) + [urljoin(DOMAIN, link[0]) for link in brief['links']]))
    store_graph(soup, nodes)
    assert baseline == fixed(soup), f'Protected meta/contact changed: {rel}'
    assert protected == protect(soup), f'Directory, source facts or original content changed: {rel}'
    output = str(Soup(str(soup), 'html.parser'))
    return {'path': rel, 'changed': write_if_changed(path, output), 'url': baseline['canonical'], 'faq': len(faq(soup)), 'mode': 'hub', 'contextualLinks': brief['links']}


def discovery(results, modified):
    urls = {unquote(r['url']): r for r in results}
    sitemap = ROOT / 'sitemap.xml'
    original = read(sitemap)
    count = 0
    def update_map(match):
        nonlocal count
        block = match[0]
        loc = html.unescape(re.search(r'<loc>(.*?)</loc>', block)[1])
        if unquote(loc) not in urls:
            return block
        count += 1
        return re.sub(r'<lastmod>.*?</lastmod>', '<lastmod>' + modified[:10] + '</lastmod>', block)
    output = re.sub(r'<url>.*?</url>', update_map, original, flags=re.S)
    assert count == len(results)
    assert [n.text for n in ET.fromstring(original).findall('{*}url/{*}loc')] == [n.text for n in ET.fromstring(output).findall('{*}url/{*}loc')]
    write_if_changed(sitemap, output)
    rss = ROOT / 'rss.xml'
    original = read(rss)
    rss_count = 0
    def update_rss(match):
        nonlocal rss_count
        block = match[0]
        loc = html.unescape(re.search(r'<link>(.*?)</link>', block)[1])
        item = urls.get(unquote(loc))
        if not item:
            return block
        rss_count += 1
        soup = Soup(read(ROOT / item['path']), 'html.parser')
        block = re.sub(r'<title>.*?</title>', lambda _: '<title>' + html.escape(text(soup.title)) + '</title>', block, flags=re.S)
        block = re.sub(r'<description>.*?</description>', lambda _: '<description>' + html.escape(soup.select_one('meta[name=description]')['content']) + '</description>', block, flags=re.S)
        return re.sub(r'<pubDate>.*?</pubDate>', '<pubDate>' + format_datetime(datetime.fromisoformat(modified)) + '</pubDate>', block)
    output = re.sub(r'<item>.*?</item>', update_rss, original, flags=re.S)
    output = re.sub(r'<lastBuildDate>.*?</lastBuildDate>', '<lastBuildDate>' + format_datetime(datetime.fromisoformat(modified)) + '</lastBuildDate>', output)
    assert [n.findtext('link') for n in ET.fromstring(original).findall('./channel/item')] == [n.findtext('link') for n in ET.fromstring(output).findall('./channel/item')]
    write_if_changed(rss, output)
    return {'sitemapUpdated': count, 'rssUpdated': rss_count}


def media(import_source):
    manifest_path = DATA / 'sources.json'
    if not manifest_path.is_file():
        assert import_source, '--import-assets must point to an existing verified source manifest'
        source = Path(import_source).resolve()
        manifest = json.loads(read(source))
        manifest['site'] = '와와학원.com'
        manifest['reuse'] = 'Official source pages rechecked; original local asset bytes reused without editing.'
        dump(manifest_path, manifest)
        # Manifest is at <project>/tools/data/<batch>/sources.json.
        media_root = source.parents[3] / 'assets/official-learning'
    else:
        manifest = json.loads(read(manifest_path))
        media_root = Path(import_source).resolve().parents[3] / 'assets/official-learning' if import_source else None
    dest = ROOT / 'assets/official-learning'
    dest.mkdir(parents=True, exist_ok=True)
    for item in manifest['assets']:
        assert Path(item['file']).name == item['file'], 'Media names must be simple filenames'
        target = dest / item['file']
        if not target.is_file():
            assert media_root is not None, f'Missing media: {target}'
            source = media_root / item['file']
            assert digest(source.read_bytes()) == item['sha256']
            shutil.copyfile(source, target)
        assert digest(target.read_bytes()) == item['sha256']
    return {'count': len(manifest['assets']), 'bytes': sum(x['bytes'] for x in manifest['assets'])}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--modified', help='ISO timestamp with timezone; retained on reruns unless explicitly changed')
    parser.add_argument('--import-assets', help='Existing verified sources.json; needed only at initial import')
    args = parser.parse_args()
    REPORTS.mkdir(parents=True, exist_ok=True)
    state_path = REPORTS / 'generation.json'
    state = json.loads(read(state_path)) if state_path.is_file() else {}
    modified = args.modified or state.get('modified') or datetime.now(timezone(timedelta(hours=9))).replace(microsecond=0).isoformat()
    assert datetime.fromisoformat(modified).tzinfo
    briefs = json.loads(read(DATA / 'hub-briefs.json'))
    original_hubs = json.loads(read(ROOT / 'tools/data/hub-guides/subject-copy.json'))
    assert set(briefs) == set(original_hubs) and len(briefs) == 27
    assets = media(args.import_assets)
    results = [core_page(p, c, modified) for p, c in CORE.items()]
    results += [hub_page(p, b, modified) for p, b in briefs.items()]
    maps = discovery(results, modified)
    dump(state_path, {'baseline': BASE, 'modified': modified, 'deployment': 'not requested; local only', 'targets': results, 'media': assets, 'discovery': maps})
    print(json.dumps({'pages': len(results), 'changed': sum(r['changed'] for r in results), 'faq': sum(r['faq'] for r in results), **assets, **maps}, ensure_ascii=False))


if __name__ == '__main__':
    main()
