"""Read-only public release verification against a specific committed snapshot.

The only output is the branch-reviews production-verification report. Earlier
release evidence remains untouched. --dry-run enumerates targets without HTTP
requests or report writes.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

from verify_branch_release_site4 import ROOT, DOMAIN, git, blob_id, PageAssets


OUTPUT = ROOT / 'tools/reports/branch-reviews/production-verification.json'
TEXT_SUFFIXES = {'.html', '.css', '.js', '.xml', '.txt', '.svg'}
NEGATIVE_ROUTES = (
    'tools/data/branch-topics/manuscripts.json',
    'tools/data/branches/snapshot.json',
    'tools/data/branch-reviews/published-reviews.json',
    'tools/data/branch-verification/owner-course-confirmation.json',
    '.git/config',
    '.env.local',
    '지점안내/서울/명일점/명일동수학학원/',
)


def read_commit(commit, file):
    return git('show', commit + ':' + file)


def sitemap_urls(raw):
    return [unquote((n.text or '').strip()) for n in ET.fromstring(raw).iter()
            if n.tag.rsplit('}', 1)[-1] == 'loc']


def build_targets(commit):
    """Use released manifests, not a potentially changing working directory."""
    pages = json.loads(read_commit(commit, 'tools/data/branch-topics/manifest.json'))['pages']
    snapshot = json.loads(read_commit(commit, 'tools/data/branches/snapshot.json'))
    representatives = json.loads(read_commit(commit, 'tools/data/branch-topics/representatives.json'))
    images = json.loads(read_commit(commit, 'tools/data/branches/assets.json'))
    tree = {}
    for row in git('ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if row:
            head, file = row.split(b'\t', 1)
            _, kind, oid = head.decode().split()
            if kind == 'blob':
                tree[file.decode('utf8')] = oid

    centers = snapshot['centers']
    center_paths = {'/지점안내/' + c['region']['province'] + '/' + c['routeSlug'] + '/'
                    for c in centers}
    regions = {c['region']['province'] for c in centers}
    region_paths = {'/지점안내/' + region + '/' for region in regions}
    assert len(pages) == len({m['path'] for m in pages}) == 2226
    assert len(centers) == len(center_paths) == 193
    assert len(regions) == 16
    assert regions <= set(snapshot['regions'])
    assert {m['parentPath'] for m in pages} <= center_paths
    identity_paths = {c['id']: '/지점안내/' + c['region']['province'] + '/' + c['routeSlug'] + '/'
                      for c in centers}
    assert all(identity_paths[m['centerId']] == m['parentPath'] for m in pages)

    targets = {m['path'].strip('/') + '/index.html': 'branch-topic-page' for m in pages}
    targets.update({p.strip('/') + '/index.html': 'parent-branch-page' for p in center_paths})
    targets.update({p.strip('/') + '/index.html': 'region-hub-page' for p in region_paths})
    targets['지점안내/index.html'] = 'branch-directory-hub'
    targets.update({r['src'].lstrip('/'): 'original-representative-image' for r in representatives})
    targets.update({src.lstrip('/'): 'preserved-branch-image' for src in images})

    regressions = (
        'index.html', '학습코칭/index.html', '전국센터/index.html',
        '과목별코칭/index.html', '학년별코칭/index.html', '상담문의/index.html',
        '학습가이드/오답관리-루틴/index.html',
        '학습가이드/시험기간-학습계획/index.html',
        '학습가이드/학부모상담-준비/index.html',
    )
    targets.update({file: 'legacy-page-regression' for file in regressions})

    # Every branch and region can have different gallery media. Enumerate their
    # assets, plus each child template/category and the retained legacy layouts.
    # All child representative/body/map images are also covered by the two
    # immutable asset catalogs above; shared CSS/JS are checked against Git.
    sample_by_topic = {}
    for m in pages:
        sample_by_topic.setdefault(m['topic'], m['path'].strip('/') + '/index.html')
    asset_pages = sorted(set(regressions) | {'지점안내/index.html'}
                         | {p.strip('/') + '/index.html' for p in center_paths | region_paths}
                         | set(sample_by_topic.values()))
    hostname = urlsplit(DOMAIN).hostname
    for file in asset_pages:
        assert file in tree, 'Missing released HTML: ' + file
        collector = PageAssets()
        collector.feed(read_commit(commit, file).decode('utf-8-sig'))
        for value in collector.urls:
            u = urlsplit(urljoin(DOMAIN + '/' + file.removesuffix('index.html'), value))
            if u.hostname == hostname:
                asset = unquote(u.path).lstrip('/')
                assert asset in tree, 'Missing released asset: ' + asset
                targets.setdefault(asset, 'shared-page-asset')
    for file in ('assets/branch-topics-site4.css', 'assets/branches-site4.css',
                 'assets/branch-search.js', 'robots.txt', 'sitemap.xml', 'rss.xml', 'llms.txt'):
        targets.setdefault(file, 'discovery-or-navigation')
    assert all(file in tree for file in targets), 'A verification target is not in the released commit'

    expected_sitemap = sitemap_urls(read_commit(commit, 'sitemap.xml'))
    expected_rss_items = len(ET.fromstring(read_commit(commit, 'rss.xml')).findall('.//item'))
    required_routes = {'/'} | {'/지점안내/'} | center_paths | region_paths | {m['path'] for m in pages}
    required_urls = {DOMAIN + route for route in required_routes}
    assert len(expected_sitemap) == len(set(expected_sitemap)) == 12214
    assert expected_rss_items == 55
    assert required_urls <= set(expected_sitemap), 'Committed sitemap omits a target route'
    meta = {
        'newPages': len(pages), 'parentPages': len(center_paths), 'regionPages': len(region_paths),
        'directoryPages': 1, 'parentsWithTopicPages': len({m['parentPath'] for m in pages}),
        'representativeImages': len(representatives), 'branchImages': len(images),
        'legacySamplePages': len(regressions),
        'confirmedScopeMissingPages': sum(not m['confirmedGrades'] for m in pages),
        'expectedSitemapUrls': len(expected_sitemap), 'expectedRssItems': expected_rss_items,
    }
    return targets, tree, set(expected_sitemap), required_urls, meta


def verify_resource(job, tree, expected_sitemap, required_urls, expected_rss_items):
    file, kind = job
    route = file.removesuffix('index.html') if file.endswith('index.html') else file
    url = DOMAIN + '/' + quote(route, safe='/')
    row = {'path': file, 'kind': kind, 'url': url, 'expectedGitBlob': tree[file]}
    for attempt in range(3):
        try:
            request = Request(url, headers={
                'User-Agent': 'WawaOwnerReviewsReleaseQA/1.0',
                'Cache-Control': 'no-cache', 'Accept-Encoding': 'identity',
            })
            with urlopen(request, timeout=45) as response:
                raw = response.read()
                row.update(status=response.status, finalUrl=response.url, bytes=len(raw),
                           contentType=response.headers.get('content-type'),
                           cache=response.headers.get('x-vercel-cache'))
            digest = blob_id(raw)
            normalized = blob_id(raw.replace(b'\r\n', b'\n')) if Path(file).suffix in TEXT_SUFFIXES else digest
            row.update(actualGitBlob=digest, normalizedGitBlob=normalized,
                       matchesCommit=tree[file] in (digest, normalized), attempts=attempt + 1)
            row['passed'] = (row['status'] == 200 and row['matchesCommit']
                             and urlsplit(row['finalUrl']).hostname == urlsplit(DOMAIN).hostname)
            if file == 'sitemap.xml':
                urls = sitemap_urls(raw)
                row.update(urls=len(urls), requiredRoutesPresent=required_urls <= set(urls))
                row['passed'] &= (len(urls) == len(set(urls)) == len(expected_sitemap)
                                  and set(urls) == expected_sitemap and row['requiredRoutesPresent'])
            if file == 'rss.xml':
                row['items'] = len(ET.fromstring(raw).findall('.//item'))
                row['passed'] &= row['items'] == expected_rss_items
            if row['passed']:
                row.pop('error', None)
                return row
        except Exception as exc:
            row.update(passed=False, error=type(exc).__name__ + ': ' + str(exc), attempts=attempt + 1)
        if attempt < 2:
            time.sleep(2 * (attempt + 1))
    return row


def verify_negative(route):
    url = DOMAIN + '/' + quote(route, safe='/')
    row = {'path': route, 'url': url}
    try:
        request = Request(url, headers={'User-Agent': 'WawaOwnerReviewsReleaseQA/1.0', 'Cache-Control': 'no-cache'})
        with urlopen(request, timeout=30) as response:
            row.update(status=response.status, finalUrl=response.url)
    except HTTPError as exc:
        row.update(status=exc.code, finalUrl=exc.url)
    except Exception as exc:
        row.update(status=type(exc).__name__, error=str(exc))
    row['passed'] = (row['status'] in (403, 404)
                     and urlsplit(row.get('finalUrl', url)).hostname == urlsplit(DOMAIN).hostname)
    return row


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    parser.add_argument('--dry-run', action='store_true', help='Enumerate committed targets only; no HTTP or report write')
    args = parser.parse_args()
    commit = git('rev-parse', '--verify', args.commit + '^{commit}').decode().strip()
    targets, tree, expected_sitemap, required_urls, meta = build_targets(commit)
    if args.dry_run:
        print(json.dumps({'site': DOMAIN, 'commit': commit, 'dryRun': True,
                          'publicChecks': len(targets), 'negativeChecks': len(NEGATIVE_ROUTES),
                          'targetKinds': dict(Counter(targets.values())), **meta}, ensure_ascii=False, indent=2))
        return

    results = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs = [pool.submit(verify_resource, item, tree, expected_sitemap, required_urls, meta['expectedRssItems'])
                for item in sorted(targets.items())]
        for future in as_completed(jobs):
            results.append(future.result())
            if len(results) % 300 == 0:
                print('Verified', len(results), '/', len(targets), flush=True)
    private = [verify_negative(route) for route in NEGATIVE_ROUTES]
    failures = [row for row in results + private if not row['passed']]
    report = {'site': DOMAIN, 'commit': commit, 'verifiedAtUtc': datetime.now(timezone.utc).isoformat(),
              'passed': not failures, 'publicChecks': len(results), 'negativeChecks': len(private), **meta,
              'targetKinds': dict(Counter(targets.values())), 'failures': failures,
              'resources': sorted(results, key=lambda row: row['path']), 'private': private}
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('resources', 'private')}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not failures else 1)


if __name__ == '__main__':
    main()
