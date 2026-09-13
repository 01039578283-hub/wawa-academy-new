"""Stage only the approved course/practice/review release, preserving other work."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = 'ec6fd5d1b7b119fc960a13720b052ad10cf9f951'
REPORT = ROOT / 'tools/reports/branch-reviews'


def git(*args, **kwargs):
    return subprocess.check_output(['git', '-c', 'core.safecrlf=false', *args], cwd=ROOT, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', action='store_true')
    args = parser.parse_args()
    assert git('rev-parse', 'HEAD').decode().strip() == BASE
    assert git('branch', '--show-current').decode().strip() == 'main'
    assert not git('diff', '--cached', '--name-only'), 'Preserve pre-existing staged work'
    audit_paths = ['branch-topics/audit.json', 'branches/audit.json',
                   'branch-verification/implementation-audit.json', 'branch-reviews/implementation-audit.json']
    audits = [json.loads((ROOT / 'tools/reports' / p).read_text(encoding='utf8')) for p in audit_paths]
    assert all(a['status'] == 'PASS' and not a['errors'] for a in audits)
    assert len(audits[0]['http']) == 2226 and audits[1]['legacyCheckPerformed']
    assert hashlib.sha256((ROOT / 'tools/data/branch-reviews/published-reviews.json').read_bytes()).hexdigest() == '9d70cb530734c8a100d75fc15276d0e0791029a8218e9d97d93d84f2551a2b4d'

    changed = git('diff', '--name-only', '-z', BASE).decode('utf8').rstrip('\0').split('\0')
    public = sorted(p for p in changed if p.startswith('지점안내/') and p.endswith('/index.html'))
    assert len(public) == 947
    assert {len(Path(p).parts): sum(len(Path(q).parts) == len(Path(p).parts) for q in public) for p in public} == {2: 1, 3: 4, 4: 103, 5: 839}
    private = ['tools/' + p for p in [
        'audit_branch_pages_site4.py', 'audit_branch_topics_site4.py',
        'branch_templates_site4.py', 'generate_branch_pages_site4.py', 'generate_branch_topics_site4.py',
        'audit_branch_reviews_site4.py', 'audit_branch_verified_facts_site4.py',
        'branch_reviews_site4.py', 'branch_verified_facts_site4.py',
        'test_branch_reviews_site4.py', 'test_branch_verified_facts_site4.py',
        'export_branch_verification_followup_site4.py',
        'prepare_owner_reviews_release_site4.py', 'verify_owner_reviews_release_site4.py',
        'BRANCH_OWNER_REVIEWS_2026-09-13.md', 'BRANCH_VERIFIED_FACTS_2026-09-13.md',
        'data/branch-topics/display-manuscripts.json', 'data/branch-topics/manifest.json',
        'data/branch-verification/actual-practices.json', 'data/branch-verification/owner-course-confirmation.json',
        'data/branch-reviews/published-reviews.json',
        'reports/branch-topics/generation.json', 'reports/branches/editorial-plan.json',
        'reports/branch-reviews/browser.json', 'reports/branch-reviews/REVIEW_QA.md',
        'reports/branch-reviews/OWNER_SCOPE_QA.md', 'reports/branch-reviews/release-plan.json',
    ]] + ['tools/reports/' + p for p in audit_paths]
    plan = {
        'site': 'https://xn--ol5ba64b839b.com', 'baselineCommit': BASE,
        'repository': '01039578283-hub/wawa-academy-new', 'branch': 'main',
        'projectId': 'prj_5xJteXuVXwQyrN3PVELCNmr2w6ZI',
        'approval': 'User explicitly requested deployment after local course confirmation and published reviews.',
        'publicFiles': public, 'privateFiles': sorted(private),
        'auditChecks': [a['checks'] for a in audits],
        'researchHandling': 'Raw workbook notes, scraped source pages, and unrelated prior release records remain local and unstaged. Source-dependent audits use that retained local evidence. Rendering requires only the curated datasets included here.',
        'hosting': 'Existing GitHub main integration to Vercel; no DNS or billing changes.',
    }
    (REPORT / 'release-plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    selected = sorted(set(public + private))
    secret = re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,}|-----BEGIN (?:RSA |OPENSSH )?PRIVATE KEY-----)')
    for p in selected:
        raw = (ROOT / p).read_bytes()
        assert len(raw) < 95_000_000, p
        assert not secret.search(raw), 'Possible credential in selected file: ' + p
    if args.stage:
        git('add', '--pathspec-from-file=-', '--pathspec-file-nul', input=('\0'.join(selected) + '\0').encode())
        staged = set(git('diff', '--cached', '--name-only', '-z').decode('utf8').rstrip('\0').split('\0'))
        assert staged == set(selected), {'unexpected': sorted(staged - set(selected)), 'missing': sorted(set(selected) - staged)}
        git('diff', '--cached', '--check')
    print(json.dumps({'public': len(public), 'private': len(private), 'total': len(selected), 'staged': args.stage}))


if __name__ == '__main__':
    main()
