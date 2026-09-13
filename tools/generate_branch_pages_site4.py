"""Generate /지점안내/ -> region -> branch, without any descendants or deployment."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import escape

from bs4 import BeautifulSoup
from branch_site4_support import ROOT, DOMAIN, with_navigation, without_navigation
import branch_templates_site4 as render
from branch_verified_facts_site4 import load_reviewed_snapshot

DATA = ROOT / 'tools/data/branches'
REPORTS = ROOT / 'tools/reports/branches'
EXCLUDE = {'.git', '.vercel', 'node_modules', 'tools', '__pycache__', '지점안내'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    return render.write_changed(path, json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def update_discovery(pages):
    sitemap_path = ROOT / 'sitemap.xml'
    original = sitemap_path.read_bytes().decode('utf-8')
    existing = set(re.findall(r'<loc>(.*?)</loc>', original))
    added = []
    for path, _ in pages:
        url = DOMAIN + quote(path, safe='/')
        if url not in existing:
            added.append(f'  <url><loc>{url}</loc><lastmod>2026-09-13</lastmod></url>\n')
    if added:
        render.write_changed(sitemap_path, original.replace('</urlset>', ''.join(added) + '</urlset>'))
    rss_path = ROOT / 'rss.xml'
    rss = rss_path.read_bytes().decode('utf-8')
    existing = set(re.findall(r'<link>(.*?)</link>', rss))
    items = []
    for path, content in pages:
        if len(path.strip('/').split('/')) > 2:
            continue
        url = DOMAIN + quote(path, safe='/')
        if url in existing:
            continue
        soup = BeautifulSoup(content, 'html.parser')
        items.append('<item><title>' + escape(soup.title.string) + '</title><link>' + url + '</link>'
                     '<guid isPermaLink="true">' + url + '</guid><description>'
                     + escape(soup.select_one('meta[name="description"]')['content'])
                     + '</description><pubDate>Sun, 13 Sep 2026 09:00:00 +0900</pubDate></item>')
    if items:
        assert '</channel>' in rss
        render.write_changed(rss_path, rss.replace('</channel>', ''.join(items) + '</channel>'))
    return {'sitemapAdded': len(added), 'rssAdded': len(items)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pages-only', action='store_true', help='Regenerate branch pages without revisiting the unchanged legacy navigation.')
    parser.add_argument('--repair-navigation', action='store_true', help='Repair only navigation exceptions from the last complete audit.')
    args = parser.parse_args()
    data = load_reviewed_snapshot()
    centers = data['centers']
    assert len(centers) == 193 and all(not c.get('_neighborhoodPages') for c in centers)
    # Only manifest-listed, already generated descendants may appear in parents.
    child_manifest = ROOT / 'tools/data/branch-topics/manifest.json'
    if child_manifest.exists():
        from branch_topic_manuscripts_site4 import TOPICS
        by_id = {c['id']: c for c in centers}
        entries = json.loads(child_manifest.read_text(encoding='utf8'))['pages']
        assert len({x['path'] for x in entries}) == len(entries)
        for child in entries:
            c = by_id[child['centerId']]
            assert child['parentPath'] == render.branch_path(c)
            assert child['path'].startswith(child['parentPath']) and len(child['path'].strip('/').split('/')) == 4
            assert (ROOT / child['path'].strip('/') / 'index.html').is_file()
            c.setdefault('_neighborhoodPages', []).append({**child, 'topicOrder': TOPICS.index(child['topic'])})
    baseline_path = DATA / 'legacy-baseline.json'
    baseline = json.loads(baseline_path.read_text(encoding='utf-8')) if baseline_path.exists() else {}
    legacy = [] if args.pages_only else [p for p in ROOT.rglob('*.html') if not EXCLUDE.intersection(p.relative_to(ROOT).parts)]
    if args.repair_navigation:
        errors = json.loads((REPORTS / 'audit.json').read_text(encoding='utf-8'))['errors']
        names = [x.removeprefix('legacy header/footer link: ') for x in errors if x.startswith('legacy header/footer link: ')]
        assert all(n in baseline for n in names)
        legacy = [ROOT / n for n in names]
    assert baseline or not args.pages_only, 'Run the initial navigation import first'
    if not baseline:
        baseline = {p.relative_to(ROOT).as_posix(): sha(p.read_bytes()) for p in legacy}
        save(baseline_path, baseline)
    updates = []
    for path in legacy:
        relative = path.relative_to(ROOT).as_posix()
        html = path.read_bytes().decode('utf-8')
        # Refuse to overwrite later unrelated user edits outside the nav addition.
        assert sha(without_navigation(html).encode('utf-8')) == baseline[relative], relative
        new = with_navigation(html)
        assert new.count('data-branch-directory-link="true"') == 2, 'Unrecognized navigation: ' + relative
        if render.write_changed(path, new):
            updates.append(relative)
    pages = [render.directory_page(centers)]
    regions = []
    for region in render.REGIONS:
        group = [c for c in centers if c['region']['province'] == region]
        if group:
            regions.append(region)
            pages.append(render.region_page(region, group, data['regions'].get(region)))
    pages += [render.center_page(c, data['schoolMatches'].get(c['id']), centers, data['reference'][c['id']]) for c in centers]
    save(REPORTS / 'editorial-plan.json', {c['id']: render.editorial.profile(c, data['reference'][c['id']], data['schoolMatches'].get(c['id'])) for c in centers})
    assert len(pages) == 210 and len({p for p, _ in pages}) == len(pages)
    changed = 0
    for path, content in pages:
        assert len(path.strip('/').split('/')) <= 3 and path.startswith('/지점안내/')
        # Preserve source records while omitting invisible end-of-line spaces.
        content = re.sub(r'[ \t]+(?=\r?$)', '', content, flags=re.M)
        changed += render.write_changed(ROOT / path.strip('/') / 'index.html', content)
    discovery = update_discovery(pages)
    result = {'site': DOMAIN, 'branchCount': len(centers), 'regionCount': len(regions), 'pageCount': len(pages),
              'regions': regions, 'paths': [p for p, _ in pages], 'changedBranchPages': changed,
              'legacyHtmlCount': len(baseline), 'navigationOnlyUpdates': len(updates),
              'discovery': discovery, 'deployment': 'NOT DEPLOYED - local only'}
    save(REPORTS / 'generation.json', result)
    print(json.dumps({k: v for k, v in result.items() if k != 'paths'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
