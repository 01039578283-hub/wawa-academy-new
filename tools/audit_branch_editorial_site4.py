"""Before/after editorial comparison; these are local measurements, not Naver scores."""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import hashlib
from html import unescape
import json
from pathlib import Path
import re
from statistics import mean

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'tools/reports/branches'
BASE = REPORTS / 'editorial-before.json'
DATA = ROOT / 'tools/data/branches'
SELECTOR = '.branch-editorial-intro, #learning, #curriculum, #consultation-guide'


def normal(text):
    return re.sub(r'\s+', ' ', unescape(text)).strip()


def blocks(soup):
    out = []
    for container in soup.select(SELECTOR):
        elements = [container] if container.name == 'p' else container.select('p, dd, li')
        for element in elements:
            if element.find(['p', 'dd', 'li']):
                continue
            text = normal(element.get_text(' ', strip=True))
            if len(text) >= 40:
                out.append(text)
    return out


def pages():
    result = {}
    for file in sorted((ROOT / '지점안내').glob('*/*/index.html')):
        raw = file.read_bytes()
        soup = BeautifulSoup(raw, 'html.parser')
        path = '/' + file.parent.relative_to(ROOT).as_posix() + '/'
        result[path] = {
            'sha256': hashlib.sha256(raw).hexdigest(), 'blocks': blocks(soup),
            'intro': soup.select_one('.branch-editorial-intro').get_text(' ', strip=True),
            'title': soup.title.string, 'h1': soup.h1.get_text(' ', strip=True),
            'canonical': soup.select_one('link[rel="canonical"]')['href'],
            'programs': [normal(e.get_text(' ', strip=True)) for e in soup.select('#programs .branch-subject-row')],
            'fees': [e.get_text(strip=True) for e in soup.select('#tuition dd')],
            'schools': [e.get_text(' ', strip=True) for e in soup.select('#schools .branch-school-list li')],
            'images': [{k: e.get(k) for k in ('src', 'alt', 'width', 'height', 'style')} for e in soup.select('.branch-primary-media img,.branch-gallery img')],
            'bodyChars': len(soup.select_one('main').get_text(' ', strip=True)),
        }
    assert len(result) == 193
    return result


def summarize(data):
    counts = Counter(text for page in data.values() for text in set(page['blocks']))
    shared = {text for text, count in counts.items() if count >= 20}
    lengths = [sum(map(len, p['blocks'])) for p in data.values()]
    repeat = [sum(len(t) for t in p['blocks'] if t in shared) for p in data.values()]
    return {
        'pages': len(data), 'averageIntroChars': round(mean(len(p['intro']) for p in data.values()), 1),
        'averageMainTextChars': round(mean(p['bodyChars'] for p in data.values()), 1),
        'averageEditorialChars': round(mean(lengths), 1),
        'passagesSharedBy20OrMoreBranches': len(shared),
        'sharedPassageCharacterRatio': round(sum(repeat) / max(1, sum(lengths)), 4),
        'topRepeatedPassages': [{'text': t, 'branchCount': n} for t, n in counts.most_common(12)],
    }


def legacy_matches(wanted):
    baseline = json.loads((DATA / 'legacy-baseline.json').read_text(encoding='utf-8'))
    # Only compare exact substantial prose blocks; labels, prices and navigation
    # are excluded. Do not call this a semantic similarity or indexing score.
    pattern = re.compile(r'<(?:p|dd|li)\b[^>]*>(.*?)</(?:p|dd|li)>', re.I | re.S)
    def inspect(name):
        html = (ROOT / name).read_text(encoding='utf-8')
        main = re.search(r'<main\b[^>]*>(.*?)</main>', html, re.S | re.I)
        if main:
            html = main.group(1)
        html = re.sub(r'<(script|style|nav|footer)\b[^>]*>.*?</\1>', '', html, flags=re.S | re.I)
        matches = set()
        for raw in pattern.findall(html):
            text = normal(re.sub(r'<[^>]+>', ' ', raw))
            if text in wanted:
                matches.add(text)
        return name, matches
    found = defaultdict(list)
    with ThreadPoolExecutor(max_workers=6) as pool:
        for name, matches in pool.map(inspect, baseline):
            for text in matches:
                found[text].append(name)
    return {'legacyPagesScanned': len(baseline), 'matchingEditorialBlocks': len(found),
            'matches': [{'text': t, 'legacyPageCount': len(v), 'examples': v[:3]} for t, v in sorted(found.items())]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--capture-before', action='store_true')
    parser.add_argument('--compare-legacy', action='store_true')
    args = parser.parse_args()
    current = pages()
    if args.capture_before:
        assert not BASE.exists(), 'Never overwrite the before snapshot'
        data_hashes = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in DATA.glob('*.json')}
        BASE.write_text(json.dumps({'pages': current, 'sourceHashes': data_hashes, 'summary': summarize(current)}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(summarize(current), ensure_ascii=False, indent=2))
        return
    before = json.loads(BASE.read_text(encoding='utf-8'))
    errors = []
    for name, digest in before['sourceHashes'].items():
        if hashlib.sha256((DATA / name).read_bytes()).hexdigest() != digest:
            errors.append('source data changed: ' + name)
    for path, old in before['pages'].items():
        for key in ('title', 'h1', 'canonical', 'programs', 'fees', 'schools', 'images'):
            if current[path][key] != old[key]:
                errors.append(f'{path}: {key} changed')
    result = {'status': 'FAIL' if errors else 'PASS', 'errors': errors,
              'measurement': 'Same four editorial sections, 40+ character blocks; shared in at least 20 of 193 branches. Necessary fact tables/fees/FAQ/navigation excluded. Not a search-engine score.',
              'before': before['summary'], 'after': summarize(current),
              'changedPages': sum(p['sha256'] != before['pages'][path]['sha256'] for path, p in current.items())}
    if args.compare_legacy:
        wanted = {t for group in (before['pages'], current) for p in group.values() for t in p['blocks']}
        result['legacyComparison'] = legacy_matches(wanted)
        old_blocks = {t for p in before['pages'].values() for t in p['blocks']}
        new_blocks = {t for p in current.values() for t in p['blocks']}
        for key, texts in [('before', old_blocks), ('after', new_blocks)]:
            result['legacyComparison'][key + 'MatchingBlocks'] = sum(x['text'] in texts for x in result['legacyComparison']['matches'])
    (REPORTS / 'editorial-comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    assert not errors, errors


if __name__ == '__main__':
    main()
