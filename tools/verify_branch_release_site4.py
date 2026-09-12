"""Read-only custom-domain verification against Git blob IDs of a released commit."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError
from urllib.parse import quote, unquote, urljoin, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = 'https://xn--ol5ba64b839b.com'


class PageAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('img', 'script') and attrs.get('src'):
            self.urls.append(attrs['src'])
        if tag == 'link' and ('stylesheet' in attrs.get('rel', '') or 'icon' in attrs.get('rel', '')):
            self.urls.append(attrs.get('href', ''))


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


def blob_id(content):
    return hashlib.sha1(b'blob ' + str(len(content)).encode() + b'\0' + content).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    commit = git('rev-parse', args.commit).decode().strip()
    generation = json.loads(git('show', commit + ':tools/reports/branches/generation.json'))
    assets = json.loads(git('show', commit + ':tools/data/branches/assets.json'))
    tree = {}
    for row in git('ls-tree', '-rz', '--full-tree', commit).split(b'\0'):
        if row:
            head, file = row.split(b'\t', 1)
            mode, kind, oid = head.decode().split()
            if kind == 'blob':
                tree[file.decode('utf-8')] = oid
    targets = {route.strip('/') + '/index.html': 'branch-page' for route in generation['paths']}
    targets.update({src.lstrip('/'): 'branch-original-asset' for src in assets})
    # Existing page bodies have already been byte-preservation audited locally;
    # sample public destinations across the original main/guide/hub/detail layout.
    for file in ('index.html', '학습코칭/index.html', '전국센터/index.html', '과목별코칭/index.html',
                 '학년별코칭/index.html', '상담문의/index.html', '학습가이드/학부모상담-준비/index.html',
                 '전국센터/수학학원/명일동고등수학학원/index.html'):
        assert file in tree, file
        targets[file] = 'legacy-page-regression'
    for file in list(targets):
        if not file.endswith('.html'):
            continue
        if targets[file] == 'branch-page' and file != '지점안내/서울/명일점/index.html':
            continue  # shared branch assets; all branch images are already enumerated above
        collector = PageAssets()
        collector.feed(git('show', commit + ':' + file).decode('utf-8-sig'))
        base = DOMAIN + '/' + file.removesuffix('index.html')
        for value in collector.urls:
            u = urlsplit(urljoin(base, value))
            if u.hostname == urlsplit(DOMAIN).hostname:
                p = unquote(u.path).lstrip('/')
                if p:
                    assert p in tree, p
                    targets.setdefault(p, 'shared-page-asset')
    for file in ('robots.txt', 'sitemap.xml', 'rss.xml', 'llms.txt', 'assets/branch-search.js'):
        assert file in tree, file
        targets.setdefault(file, 'discovery-or-search')

    def verify(job):
        file, kind = job
        route = file.removesuffix('index.html') if file.endswith('index.html') else file
        url = DOMAIN + '/' + quote(route, safe='/')
        row = {'path': file, 'kind': kind, 'url': url, 'expectedGitBlob': tree[file]}
        for attempt in range(2):
            try:
                request = Request(url, headers={'User-Agent': 'WawaBranchReleaseVerification/1.0', 'Cache-Control': 'no-cache', 'Accept-Encoding': 'identity'})
                with urlopen(request, timeout=45) as response:
                    content = response.read()
                    row.update(status=response.status, finalUrl=response.url, bytes=len(content),
                               cache=response.headers.get('x-vercel-cache'), contentType=response.headers.get('content-type'))
                oid = blob_id(content)
                lf_oid = blob_id(content.replace(b'\r\n', b'\n')) if Path(file).suffix in ('.html', '.css', '.js', '.txt', '.xml', '.svg') else oid
                row.update(actualGitBlob=oid, matchesCommit=tree[file] in (oid, lf_oid), attempts=attempt + 1)
                row['passed'] = row['status'] == 200 and row['matchesCommit'] and urlsplit(row['finalUrl']).hostname == urlsplit(DOMAIN).hostname
                if file == 'sitemap.xml':
                    row['urls'] = sum(n.tag.endswith('}loc') for n in ET.fromstring(content).iter())
                    row['passed'] &= row['urls'] == 9988
                if file == 'rss.xml':
                    row['items'] = len(ET.fromstring(content).findall('.//item'))
                    row['passed'] &= row['items'] == 49
                return row
            except Exception as err:
                row.update(passed=False, error=type(err).__name__ + ': ' + str(err))
        return row

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(verify, targets.items()))
    private = []
    for route in ('tools/data/branches/snapshot.json', 'tools/BRANCH_EDITORIAL_HANDOFF_2026-09-13.md', '.git/config', '.env.local',
                  '지점안내/서울/명일점/명일동수학학원/'):
        try:
            with urlopen(DOMAIN + '/' + quote(route, safe='/'), timeout=25) as response:
                status = response.status
        except HTTPError as err:
            status = err.code
        except Exception as err:
            status = type(err).__name__
        private.append({'path': route, 'status': status, 'passed': status in (403, 404)})
    failures = [x for x in results + private if not x['passed']]
    report = {'site': DOMAIN, 'commit': commit, 'verifiedAtUtc': datetime.now(timezone.utc).isoformat(),
              'passed': not failures, 'publicChecks': len(results), 'branchPages': len(generation['paths']),
              'branchAssets': len(assets), 'legacySamplePages': 8, 'negativeChecks': len(private),
              'failures': failures, 'resources': results, 'private': private}
    out = ROOT / 'tools/reports/branches/production-verification.json'
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in ('resources', 'private')}, ensure_ascii=False, indent=2))
    raise SystemExit(1 if failures else 0)


if __name__ == '__main__':
    main()
