"""Site4 metadata and shared shell for the branch-only renderer."""
from functools import lru_cache
from html import escape, unescape
from pathlib import Path
from urllib.parse import urljoin, quote
import json
import re

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = 'https://xn--ol5ba64b839b.com'
NAV_LINK = '<a class="nav-link" data-branch-directory-link="true" href="/지점안내/">지점안내</a>'
FOOTER_LINK = '<a data-branch-directory-link="true" href="/지점안내/">지점안내</a>'
NAV_CSS = '<link rel="stylesheet" href="/assets/branch-navigation.css?v=20260913-1" data-branch-navigation="true">'


def with_navigation(html):
    def nav(m):
        block = m.group(0)
        if 'data-branch-directory-link' in block:
            return block
        # Insert before consultation; preserve every existing menu link verbatim.
        # The visible label is stable on both percent-encoded and Korean hrefs.
        return re.sub(r'(<a\b[^>]*>\s*상담문의\s*</a>)', NAV_LINK + r'\1', block, count=1)
    html = re.sub(r'<nav\b(?=[^>]*class=["\'][^"\']*\bmain-nav\b)[^>]*>.*?</nav>', nav, html, flags=re.S)
    def footer(m):
        block = m.group(0)
        return block if 'data-branch-directory-link' in block else block.replace('</div>', FOOTER_LINK + '</div>')
    html = re.sub(r'<div\b(?=[^>]*class=["\']footer-links["\'])[^>]*>.*?</div>', footer, html, flags=re.S)
    if 'data-branch-navigation=' not in html:
        html = html.replace('</head>', NAV_CSS + '</head>', 1)
    return html


def without_navigation(html):
    return html.replace(NAV_LINK, '').replace(FOOTER_LINK, '').replace(NAV_CSS, '')


@lru_cache(maxsize=1)
def shell():
    source = with_navigation((ROOT / 'index.html').read_text(encoding='utf-8'))
    soup = BeautifulSoup(source, 'html.parser')
    assert soup.select_one('link[rel="canonical"]')['href'] == DOMAIN + '/'
    header = soup.select_one('header.site-header')
    footer = soup.select_one('footer.site-footer')
    actions = soup.select_one('.floating-actions')
    for element in (header, footer):
        for a in element.select('a[href]'):
            href = a['href']
            if not re.match(r'^(?:https?:|tel:|sms:|/|#)', href):
                a['href'] = '/' + href.removeprefix('./')
        for a in element.select('.main-nav a'):
            a['class'] = ['nav-link']
            if a.get('href') == '/지점안내/':
                a['class'].append('is-active')
                a['aria-current'] = 'true'
    for node in footer.select('.footer-contact'):
        node.decompose()  # No visible phone-number text on branch pages.
    meta = [str(x) for x in soup.head.select('meta[name="naver-site-verification"],meta[name="google-site-verification"]')]
    og = soup.head.select_one('meta[property="og:image"]')['content']
    assert all(a['href'].startswith(('tel:01039578283', 'https://blogsms.net/', 'https://docs.google.com/')) for a in actions.select('a'))
    return str(header), str(footer) + str(actions), '\n'.join(meta), og


def reference_gallery(center, reference):
    photos = reference.get('images', [])
    if not photos:
        return ''
    images = []
    for index, img in enumerate(photos, 1):
        alt = escape(center['displayName'] + ' 학습 공간 ' + str(index), quote=True)
        images.append(f'<figure><img src="{escape(img["localSrc"])}" width="{img["width"]}" height="{img["height"]}" alt="{alt}" loading="lazy" decoding="async"></figure>')
    return '<p class="branch-photo-note">' + escape(center['sourceCenterName']) + '에 등록된 학습 공간 사진 ' + str(len(photos)) + '장입니다.</p><div class="branch-gallery">' + ''.join(images) + '</div>'


def page(title, desc, path, crumbs, body, graph, detail=False):
    canonical = DOMAIN + quote(path, safe='/')
    header, footer, verification, share_image = shell()
    # Registered photographs stay attributable to their own branch, never reused
    # as another center's photo or described as a newly confirmed facility.
    soup = BeautifulSoup(body, 'html.parser')
    parts = []
    for section in soup.select('section[id]'):
        heading = section.find(['h2', 'h1'])
        if not heading:
            continue
        part_id = canonical + '#' + section['id']
        part = {'@type': 'WebPageElement', '@id': part_id, 'url': part_id,
                'name': heading.get_text(' ', strip=True), 'isPartOf': {'@id': canonical + '#webpage'}}
        existing = next((n for n in graph if n.get('@id') == part_id), None)
        if existing:
            existing['isPartOf'] = part['isPartOf']
        else:
            graph.append(part)
        parts.append({'@id': part_id})
    graph[0]['name'] = '와와학습코칭학원'
    graph[1]['hasPart'] = parts
    for node in graph:
        if node.get('@type') == 'EducationalOrganization':
            photos = soup.select('.branch-gallery img')
            if photos:
                node['image'] = [DOMAIN + p['src'] for p in photos]
    graph[1]['significantLink'] = [DOMAIN + '/학습코칭/', DOMAIN + '/전국센터/']
    related = ('<section class="branch-panel branch-context-links" id="learning-guides"><h2>수업을 알아볼 때 함께 읽어보세요</h2>'
               '<p>지점별 수업 범위는 각 지점 안내에서, 학습코칭의 공통 원리와 과목별 점검 방법은 아래 안내에서 확인할 수 있습니다.</p>'
               '<div class="branch-actions"><a class="branch-button secondary" href="/학습코칭/">맞춤 코칭과 AI 학습</a>'
               '<a class="branch-button secondary" href="/전국센터/">과목·학년별 지역 안내</a>'
               '<a class="branch-button secondary" href="/학습가이드/학부모상담-준비/">상담 준비하기</a></div></section>')
    # Keep the closed learning-space section at the bottom, as on the reference.
    marker = '<section class="branch-panel" id="learning-space">'
    body = body.replace(marker, related + marker, 1) if marker in body else body + related
    related_id = canonical + '#learning-guides'
    graph[1]['hasPart'].append({'@id': related_id})
    graph.append({'@type': 'WebPageElement', '@id': related_id, 'url': related_id,
                  'name': '수업을 알아볼 때 함께 읽어보세요', 'isPartOf': {'@id': canonical + '#webpage'}})
    schema = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c')
    return f'''<!DOCTYPE html>
<html lang="ko"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title><meta name="description" content="{escape(desc, quote=True)}">
<link rel="canonical" href="{canonical}"><meta name="robots" content="index,follow">
<meta property="og:type" content="website"><meta property="og:site_name" content="와와학습코칭학원">
<meta property="og:title" content="{escape(title, quote=True)}"><meta property="og:description" content="{escape(desc, quote=True)}">
<meta property="og:url" content="{canonical}"><meta property="og:image" content="{escape(share_image, quote=True)}">
<meta name="twitter:card" content="summary_large_image"><meta name="twitter:title" content="{escape(title, quote=True)}">
{verification}
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
<link rel="alternate" href="{DOMAIN}/rss.xml" type="application/rss+xml" title="와와학습코칭학원 학습정보 RSS">
<link rel="stylesheet" href="/assets/site.css"><link rel="stylesheet" href="/assets/branches.css">
<link rel="stylesheet" href="/assets/branches-site4.css?v=20260913-2">{NAV_CSS}
<script type="application/ld+json">{schema}</script>
</head><body class="branch-page{' branch-detail-page' if detail else ''}">
<a class="skip-link" href="#main">본문 바로가기</a>{header}
<main id="main"><div class="wrap">{breadcrumb(crumbs)}{body}</div></main>
{footer}
{'<script src="/assets/branch-search.js" defer></script>' if not detail else ''}
</body></html>
'''


def breadcrumb(crumbs):
    return '<nav aria-label="현재 위치"><ol class="branch-breadcrumb">' + ''.join(
        f'<li><a href="{escape(path, quote=True)}">{escape(name)}</a></li>' if i < len(crumbs) - 1
        else f'<li><span aria-current="page">{escape(name)}</span></li>' for i, (name, path) in enumerate(crumbs)) + '</ol></nav>'
