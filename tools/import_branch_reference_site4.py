"""Snapshot reviewed site15 branch facts and owner-supplied local photographs.

Read-only with respect to both sources. Default only reviews photo matching.
--apply imports a self-contained, branch-only snapshot and immutable media bytes.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = ROOT.parent / '새 홈페이지15'
PHOTOS = Path('C:/Users/1992k/Desktop/WAWA 전국센터 사진')
DATA = ROOT / 'tools/data/branches'
REPORTS = ROOT / 'tools/reports/branches'
# Reviewed against the displayed source addresses on 2026-09-13. These differ
# only by province/district notation or by a redundant dong before the road.
# Parcel-only records were checked against fullAddress, including building/floor.
REVIEWED_PHOTO_MATCHES = {
    'center-row-015': 321, 'center-row-022': 285, 'center-row-038': 320,
    'center-row-043': 493, 'center-row-044': 389, 'center-row-049': 456,
    'center-row-052': 332, 'center-row-062': 322, 'center-row-070': 424,
    'center-row-075': 511, 'center-row-077': 4, 'center-row-087': 331,
    'center-row-119': 231, 'center-row-122': 325, 'center-row-130': 274,
    'center-row-141': 328, 'center-row-151': 315, 'center-row-171': 44,
    'center-row-178': 371, 'center-row-194': 343,
}


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write(path, value):
    data = value if isinstance(value, bytes) else value.encode('utf-8')
    if path.exists() and path.read_bytes() == data:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def save(path, value):
    write(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def norm(value):
    value = value.replace('서울특별시', '서울').replace('경기도', '경기')
    value = value.replace('강원특별자치도', '강원').replace('강원도', '강원')
    value = value.replace('전북특별자치도', '전북').replace('전라북도', '전북')
    value = value.replace('충청북도', '충북').replace('충청남도', '충남')
    value = value.replace('경상북도', '경북').replace('경상남도', '경남')
    value = value.replace('제주특별자치도', '제주').replace('세종특별자치시', '세종')
    value = value.replace('전남광주통합특별시', '광주').replace('광역시', '')
    return re.sub(r'[\s,().·]', '', value)


def road_key(value):
    m = re.search(r'^(.+?(?:대로|로|길)\s*\d+(?:-\d+)?)(?=\s|,|$)', value.strip())
    return norm(m[1]) if m else ''


def match_photo(c, catalog):
    if c['id'] in REVIEWED_PHOTO_MATCHES:
        photo = next(p for p in catalog if p['id'] == REVIEWED_PHOTO_MATCHES[c['id']])
        assert norm(photo['placeName']) == norm(c['sourceCenterName'])
        return photo, 'reviewed-name-and-road-or-parcel'
    # A place name alone is not enough: the reviewed road address must agree.
    road = road_key(c['address'])
    exact = [p for p in catalog if road and road == road_key(p.get('doroAddr1', ''))]
    named = [p for p in exact if norm(p['placeName']) == norm(c['sourceCenterName'])]
    candidates = named or exact
    candidates = [p for p in candidates if p.get('placeSubCateName') != 'W+']
    if len(candidates) == 1:
        return candidates[0], 'road-address-and-name' if named else 'unique-road-address'
    # Name-only candidates are retained for review, never automatically attached.
    similar = [p for p in catalog if norm(p['placeName']) == norm(c['sourceCenterName'])]
    return None, [{'photoCenterId': p['id'], 'name': p['placeName'],
                   'roadAddress': p.get('doroAddr1'), 'folder': p['folder']} for p in similar]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    assert ROOT.name == '새 홈페이지4' and REFERENCE.is_dir() and PHOTOS.is_dir()
    sys.path.insert(0, str(REFERENCE / 'tools'))
    import generate_branch_pages as old
    from PIL import Image
    _, centers, reference = old.load_branch_data()
    matches = {m['centerId']: m for m in read(old.DATA / 'school-match-audit.json')['matches']}
    matches.update(reference.get('schoolMatches', {}))
    catalog_path = PHOTOS / '_정리내역/수집목록.json'
    catalog = read(catalog_path)['centers']
    photo_usage = Counter(p['sha256'] for c in catalog for p in c.get('photos', []) if p.get('status') == 'saved')
    results, assets, photo_links = [], {}, {}

    def import_asset(source, folder, expected=None):
        source = source.resolve()
        assert source.is_relative_to(PHOTOS.resolve()) or source.is_relative_to(REFERENCE.resolve())
        content = source.read_bytes()
        sha = hashlib.sha256(content).hexdigest()
        if expected:
            assert sha == expected, f'Changed source: {source}'
        with Image.open(source) as image:
            width, height = image.size
            image.verify()
        src = '/assets/branches/' + folder + '/' + sha[:24] + source.suffix.lower()
        assets[src] = {'source': str(source), 'sha256': sha, 'bytes': len(content), 'width': width, 'height': height}
        if args.apply:
            write(ROOT / src.lstrip('/'), content)
        return {'src': src, 'width': width, 'height': height, 'sha256': sha}

    for c in centers:
        c['_neighborhoodPages'] = []
        c['_searchNeighborhoods'] = matches.get(c['id'], {}).get('neighborhoods', [])
        ref = reference['centers'].get(c['id'], {})
        ref['images'] = []  # Do not import generic photos from the old reference.
        photo, reason = match_photo(c, catalog)
        row = {'centerId': c['id'], 'name': c['sourceCenterName'], 'province': c['region']['province'],
               'address': c['address'], 'status': 'unmatched', 'photos': 0}
        if photo:
            row.update(photoCenterId=photo['id'], folder=photo['folder'], basis=reason,
                       photoRoadAddress=photo['doroAddr1'], status='no-unique-photo')
            seen = set()
            for p in photo.get('photos', []):
                if p.get('status') != 'saved' or p.get('category') != 'center_registered':
                    continue
                # Shared images are not evidence of a particular branch's interior.
                if photo_usage[p['sha256']] > 1 or p['sha256'] in seen:
                    continue
                seen.add(p['sha256'])
                a = import_asset(PHOTOS / photo['folder'] / p['saved_file'], 'photos', p['sha256'])
                ref['images'].append({'localSrc': a.pop('src'), **a})
            row['photos'] = len(ref['images'])
            if row['photos']:
                row['status'] = 'matched-with-photos'
        else:
            row['candidates'] = reason
        results.append(row)
        photo_links[c['id']] = row
        media = ref.get('primaryMedia', {})
        for kind in ('body', 'map'):
            if not media.get(kind):
                continue
            source_asset = media[kind]
            a = import_asset(REFERENCE / unquote(source_asset['src']).lstrip('/'), 'primary')
            if source_asset.get('displayPanel'):
                a['displayPanel'] = source_asset['displayPanel']
            media[kind] = a
        ref['primaryMedia'] = {k: media[k] for k in ('body', 'map') if media.get(k)}
    summary = dict(Counter(r['status'] for r in results))
    report = {'centerCount': len(centers), 'summary': summary, 'photoCount': sum(r['photos'] for r in results),
              'uniqueAssets': len(assets), 'assetBytes': sum(a['bytes'] for a in assets.values()), 'centers': results}
    if args.apply:
        # Retain only the reviewed branch set; no neighborhood/grade manuscripts or paths.
        save(DATA / 'snapshot.json', {'centers': centers,
             'reference': {c['id']: reference['centers'][c['id']] for c in centers},
             'regions': {k: {key: value for key, value in v.items() if key != 'images'} for k, v in reference['regions'].items()},
             'schoolMatches': {c['id']: matches[c['id']] for c in centers if c['id'] in matches}})
        save(DATA / 'assets.json', assets)
        save(DATA / 'photo-matches.json', report)
        save(DATA / 'provenance.json', {'referenceProject': str(REFERENCE), 'photoRoot': str(PHOTOS),
             'photoCatalogSha256': hashlib.sha256(catalog_path.read_bytes()).hexdigest(),
             'referenceGeneratorSha256': hashlib.sha256((REFERENCE / 'tools/generate_branch_pages.py').read_bytes()).hexdigest(),
             'excludedCenterIds': sorted(old.EXCLUDED_CENTER_IDS), 'importDate': '2026-09-13',
             'notes': ['Reviewed source facts; user-supplied fee schedule retained.',
                       'Only unique registered photos with a matching road address. No shared fallback photos.',
                       'No branch descendants imported. Target contact endpoints are preserved.']})
        # Mechanical port of pure reviewed rendering helpers. Target shell and
        # all runtime inputs live locally; normal regeneration never imports site15.
        source = (REFERENCE / 'tools/generate_branch_pages.py').read_text(encoding='utf-8')
        tree = ast.parse(source)
        excluded = {'load_branch_data', 'page', 'sync_navigation', 'main', 'reference_gallery'}
        constants = {'REGIONS', 'LEVELS', 'FEES', 'HUB', 'CURRICULUM_COPY'}
        chunks = ['"""Reviewed branch renderer ported from site15; site4 shell and data are independent."""',
                  'from collections import defaultdict\nfrom html import escape, unescape\nimport re\nfrom urllib.parse import quote',
                  'from branch_site4_support import DOMAIN, page, reference_gallery']
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name not in excluded:
                chunks.append(ast.get_source_segment(source, node))
            elif isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets):
                chunks.append(ast.get_source_segment(source, node))
        code = '\n\n\n'.join(chunks).replace('영수코칭', '와와학원').replace('tel:01068398283', 'tel:01039578283') + '\n'
        write(ROOT / 'tools/branch_templates_site4.py', code)
        write(ROOT / 'assets/branches.css', (REFERENCE / 'assets/branches.css').read_bytes())
        write(ROOT / 'assets/branch-search.js', (REFERENCE / 'assets/branch-search.js').read_bytes())
        save(REPORTS / 'import.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'centers'}, ensure_ascii=False, indent=2))
    print(json.dumps([r for r in results if r['status'] == 'unmatched'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
