"""Scope a release to the reviewed branch directory, never unrelated worktree edits."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASELINE = 'd39d417ef0f11a820e5b4ab2d0f755bac49a3e5b'


def git(*args, **kwargs):
    return subprocess.check_output(['git', '-c', 'core.safecrlf=false', *args], cwd=ROOT, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', action='store_true')
    args = parser.parse_args()
    assert git('rev-parse', 'HEAD').decode().strip() == BASELINE
    assert git('branch', '--show-current').decode().strip() == 'main'
    assert not git('diff', '--cached', '--name-only'), 'Preserve pre-existing staged changes'
    report = json.loads((ROOT / 'tools/reports/branches/audit.json').read_text(encoding='utf-8'))
    assert report['status'] == 'PASS' and report['legacyCheckPerformed'] and not report['errors']
    legacy = json.loads((ROOT / 'tools/data/branches/legacy-baseline.json').read_text(encoding='utf-8'))
    generation = json.loads((ROOT / 'tools/reports/branches/generation.json').read_text(encoding='utf-8'))
    assets = json.loads((ROOT / 'tools/data/branches/assets.json').read_text(encoding='utf-8'))
    html = list(legacy) + [p.strip('/') + '/index.html' for p in generation['paths']]
    public = html + [p.lstrip('/') for p in assets] + [
        'assets/branch-navigation.css', 'assets/branch-search.js', 'assets/branches.css', 'assets/branches-site4.css', 'sitemap.xml', 'rss.xml']
    private = ['tools/' + p for p in (
        'BRANCH_DIRECTORY_HANDOFF_2026-09-13.md', 'BRANCH_EDITORIAL_HANDOFF_2026-09-13.md',
        'branch_editorial_site4.py', 'branch_templates_site4.py', 'branch_site4_support.py',
        'import_branch_reference_site4.py', 'generate_branch_pages_site4.py',
        'audit_branch_pages_site4.py', 'audit_branch_editorial_site4.py',
        'test_branch_site4.py', 'test_branch_editorial_site4.py',
        'prepare_branch_release_site4.py', 'verify_branch_release_site4.py')]
    private += [p.relative_to(ROOT).as_posix() for folder in ('tools/data/branches', 'tools/reports/branches')
                for p in (ROOT / folder).glob('*.json') if p.name not in ('release-plan.json', 'production-verification.json', 'release.json', 'production-browser.json')]
    private.append('tools/reports/branches/release-plan.json')
    selected = sorted(set(public + private))
    largest = sorted([(p.stat().st_size, p.relative_to(ROOT).as_posix()) for p in (ROOT / 'assets/branches').rglob('*') if p.is_file()], reverse=True)[:3]
    plan = {'site': 'https://xn--ol5ba64b839b.com', 'baselineCommit': BASELINE,
            'repository': '01039578283-hub/wawa-academy-new', 'branch': 'main',
            'projectId': 'prj_5xJteXuVXwQyrN3PVELCNmr2w6ZI', 'teamId': 'team_BpURNiIrN8A3yrAtR4F7iqvf',
            'publicFiles': public, 'privateFiles': private, 'largestBranchAssets': largest,
            'approval': 'User requested deployment of the completed branch directory and mobile/editorial revisions.',
            'excludedPriorChanges': ['tools/BRAND_UPGRADE_HANDOFF_2026-09-12.md', 'tools/reports/brand-upgrade/production-browser.json', 'tools/reports/brand-upgrade/production-verification.json', 'tools/reports/brand-upgrade/release.json']}
    (ROOT / 'tools/reports/branches/release-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    assert all((ROOT / p).is_file() for p in selected)
    assert len(html) == 9988 and len(public) == 10440
    assert largest[0][0] < 95_000_000
    if args.stage:
        git('add', '--pathspec-from-file=-', '--pathspec-file-nul', input=('\0'.join(selected) + '\0').encode('utf-8'))
        staged = set(git('diff', '--cached', '--name-only', '-z').decode('utf-8').rstrip('\0').split('\0'))
        assert staged == set(selected), {'missing': sorted(set(selected) - staged), 'extra': sorted(staged - set(selected))}
        git('diff', '--cached', '--check')
    print(json.dumps({'publicFiles': len(public), 'privateFiles': len(private), 'selectedFiles': len(selected),
                      'branchPages': len(generation['paths']), 'legacyNavigationOnly': len(legacy), 'staged': args.stage}, indent=2))


if __name__ == '__main__':
    main()
