"""Run the existing site4 release checks without scanning Git internals.

Only ROOT.rglob('index.html') enumeration is replaced with the Git-visible site
inventory, including new untracked pages. No audit rules or page data change.
"""
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
from io import StringIO
import json
from pathlib import Path
import runpy
import subprocess
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
SCRIPTS=['audit_aeo_geo_individuality_site4.py','audit_faq_consistency_site4.py',
         'validate_final_site4.py','audit_intent_roles_site4.py']


def main():
    inventory=subprocess.run(['git','ls-files','--cached','--others','--exclude-standard','-z','*.html'],cwd=ROOT,check=True,capture_output=True).stdout.decode('utf-8').split('\0')
    paths=sorted({ROOT/p for p in inventory if p=='index.html' or p.endswith('/index.html')})
    if len(paths)!=9778:raise ValueError(f'Unexpected site inventory: {len(paths)}')
    original=Path.rglob
    def public_rglob(path,pattern,*args,**kwargs):
        if pattern=='index.html' and path.resolve()==ROOT:
            return iter(paths)
        return original(path,pattern,*args,**kwargs)
    results=[]
    for script in SCRIPTS:
        output=StringIO();code=0
        old_args=sys.argv[:]
        try:
            sys.argv=[str(ROOT/'tools'/script)]
            if 'faq_consistency' in script:sys.argv.append('--quiet')
            with patch.object(Path,'rglob',public_rglob),redirect_stdout(output),redirect_stderr(output):
                try:runpy.run_path(sys.argv[0],run_name='__main__')
                except SystemExit as exc:code=exc.code or 0
        except Exception as exc:
            code=1;output.write(repr(exc))
        finally:sys.argv=old_args
        results.append(dict(script=script,exitCode=code,output=output.getvalue()))
        print(script,'PASS' if code==0 else 'FAIL',flush=True)
        if code:print(output.getvalue()[-3500:],flush=True)
    report=ROOT/'tools/reports/title-suffix-legacy-verification.json'
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(dict(checkedAt=datetime.now(timezone.utc).isoformat(),
                     inventory=len(paths),results=results),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    if any(r['exitCode'] for r in results):raise SystemExit(1)
    print('SITE4_LEGACY_CHECKS_PASS')


if __name__=='__main__':main()
