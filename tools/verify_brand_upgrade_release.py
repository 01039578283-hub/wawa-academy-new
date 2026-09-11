"""Read-only production check against a specified, committed site4 release.

No credentials are read. Reports contain hashes/statuses, never response bodies.
Unlike the pre-commit static audit, this also works with a clean working tree.
"""
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
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
DOMAIN = 'https://xn--ol5ba64b839b.com'


def blob(commit, path):
    return subprocess.run(['git', 'show', f'{commit}:{path}'], cwd=ROOT,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          check=True).stdout


class Assets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('img', 'script') and attrs.get('src'):
            self.urls.append(attrs['src'])
        if tag == 'link' and ('stylesheet' in attrs.get('rel', '')
                             or 'icon' in attrs.get('rel', '')):
            self.urls.append(attrs.get('href', ''))


def digest(content):
    return hashlib.sha256(content).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--commit', required=True)
    args = parser.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', args.commit], cwd=ROOT).decode().strip()
    generation = json.loads(blob(commit, 'tools/reports/brand-upgrade/generation.json'))
    paths = {row['path']: 'updated-page' for row in generation['targets']}
    for row in generation['targets']:
        assets = Assets()
        assets.feed(blob(commit, row['path']).decode('utf-8-sig'))
        for value in assets.urls:
            url = urlsplit(urljoin(row['url'], value))
            if url.hostname == urlsplit(DOMAIN).hostname:
                path = unquote(url.path).lstrip('/')
                if path:
                    paths.setdefault(path, 'page-asset')
    for path in ('sitemap.xml', 'rss.xml', 'llms.txt', 'robots.txt'):
        paths[path] = 'discovery'
    # Existing destinations and basic pages are deliberately outside edit scope.
    for path in ('전국센터/수학학원/명일동고등수학학원/index.html',
                 '상담문의/index.html', '학습가이드/index.html'):
        assert blob(commit, path) == blob(generation['baseline'], path), path
        paths[path] = 'unchanged-regression'

    jobs = []
    for path, kind in paths.items():
        route = path[:-10] if path.endswith('index.html') else path
        jobs.append((path, kind, DOMAIN + '/' + quote(route, safe='/'), blob(commit, path)))

    def verify(job):
        path, kind, url, expected = job
        result = {'path': path, 'kind': kind, 'url': url}
        try:
            request = Request(url, headers={'User-Agent': 'WawaReleaseVerification/1.0',
                                           'Cache-Control': 'no-cache', 'Accept-Encoding': 'identity'})
            with urlopen(request, timeout=40) as response:
                content = response.read()
                result.update(status=response.status, finalUrl=response.url,
                              bytes=len(content), cache=response.headers.get('x-vercel-cache'),
                              contentType=response.headers.get('content-type'))
            # Git's Windows checkout may differ only in text line endings.
            if Path(path).suffix in ('.html', '.txt', '.xml', '.js', '.css', '.svg'):
                content = content.replace(b'\r\n', b'\n')
                expected = expected.replace(b'\r\n', b'\n')
            result.update(expectedSha256=digest(expected), actualSha256=digest(content),
                          passed=result['status'] == 200 and content == expected
                          and urlsplit(result['finalUrl']).hostname == urlsplit(DOMAIN).hostname)
            if path == 'sitemap.xml':
                result['urls'] = len(ET.fromstring(content).findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url'))
                result['passed'] &= result['urls'] == 9778
            if path == 'rss.xml':
                result['items'] = len(ET.fromstring(content).findall('./channel/item'))
                result['passed'] &= result['items'] == 32
        except Exception as error:
            result.update(passed=False, error=f'{type(error).__name__}: {error}')
        return result

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(verify, jobs))
    private = []
    for path in ('tools/BRAND_UPGRADE_HANDOFF_2026-09-12.md', '.env.local', '.git/config'):
        try:
            with urlopen(DOMAIN + '/' + quote(path, safe='/'), timeout=25) as response:
                status = response.status
        except HTTPError as error:
            status = error.code
        except Exception as error:
            status = type(error).__name__
        private.append({'path': path, 'status': status, 'passed': status in (403, 404)})
    failed = [row for row in results + private if not row['passed']]
    report = {'domain': DOMAIN, 'commit': commit, 'verifiedAtUtc': datetime.now(timezone.utc).isoformat(),
              'updatedPages': len(generation['targets']), 'publicResources': len(results),
              'privateChecks': len(private), 'passed': not failed, 'failed': failed,
              'resources': results, 'private': private}
    output = ROOT / 'tools/reports/brand-upgrade/production-verification.json'
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key not in ('resources', 'private')},
                     ensure_ascii=False, indent=2))
    raise SystemExit(1 if failed else 0)


if __name__ == '__main__':
    main()
