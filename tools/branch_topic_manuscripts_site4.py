"""Strict, read-only parsing of the six owner-supplied school-level ZIPs."""
from __future__ import annotations
from collections import Counter
from copy import deepcopy
from io import BytesIO
from pathlib import Path, PurePosixPath
import hashlib
import re
import stat
import unicodedata
from zipfile import ZipFile

TOPICS = ('고등학생 수학학원', '고등학생 영어학원', '중학생 수학학원',
          '중학생 영어학원', '초등학생 수학학원', '초등학생 영어학원')
BLOCKS = ('페이지타이틀', '메타설명', '본문', 'FAQ', '학부모후기', 'JSON-LD 요약')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def norm(value):
    return re.sub(r'\s+', ' ', value).strip()


def parse(raw, member, topic):
    text = re.sub(r'\r+\n', '\n', raw.decode('utf-8-sig')).replace('\r', '\n')
    assert '\x00' not in text, member
    labels = list(re.finditer(r'^\[([^\]\n]+)\][ \t]*$', text, re.M))
    assert tuple(m[1] for m in labels) == BLOCKS and not text[:labels[0].start()].strip(), member
    data = {m[1]: text[m.end():labels[i+1].start() if i+1<len(labels) else len(text)].strip()
            for i, m in enumerate(labels)}
    assert all(data.values()), member
    title = norm(data['페이지타이틀'])
    assert title == PurePosixPath(member).stem and title.endswith(' ' + topic), member
    locality = title[:-len(topic)-1]
    assert locality and not re.search(r'[/\\?#\x00-\x1f]', locality), member
    headings = list(re.finditer(r'^##[ \t]+(.+?)[ \t]*$', data['본문'], re.M))
    assert len(headings) >= 3, member
    intro = norm(data['본문'][:headings[0].start()])
    assert intro, member
    sections = []
    for i, h in enumerate(headings):
        body = data['본문'][h.end():headings[i+1].start() if i+1<len(headings) else len(data['본문'])]
        paragraphs = [norm(p) for p in re.split(r'\n\s*\n', body) if p.strip()]
        assert paragraphs and all(paragraphs), member
        sections.append({'heading': norm(h[1]), 'paragraphs': paragraphs})
    assert len({s['heading'] for s in sections}) == len(sections), member
    faq = []
    cursor = 0
    pattern = r'^Q(\d+)\.[ \t]*(.+?)\n\s*A(\d*)\.[ \t]*(.*?)(?=^Q\d+\.|\Z)'
    for i, f in enumerate(re.finditer(pattern, data['FAQ'], re.M | re.S), 1):
        assert not data['FAQ'][cursor:f.start()].strip(), member
        assert f[1] == str(i) and f[3] in ('', str(i)), member
        q, a = norm(f[2]), norm(f[4])
        assert q and a and not re.search(r'\nA\d*\.', f[4]), member
        faq.append({'question': q, 'answer': a})
        cursor = f.end()
    assert faq and not data['FAQ'][cursor:].strip(), member
    assert len({f['question'] for f in faq}) == len(faq), member
    case = data['학부모후기']
    case = re.sub(r'^※[^\n]*(?:\n|$)', '', case).strip()
    return {'topic': topic, 'stage': topic.split()[0], 'subject': topic.split()[1].removesuffix('학원'),
            'locality': locality, 'title': title, 'meta': norm(data['메타설명']), 'intro': intro,
            'sections': sections, 'faq': faq, 'cases': [norm(p) for p in re.split(r'\n\s*\n', case) if p.strip()],
            'schemaSummary': norm(data['JSON-LD 요약']), 'sourceMember': member, 'sourceSha256': sha(raw)}


def load_archive(path, topic):
    assert topic in TOPICS
    raw = Path(path).read_bytes()
    assert 0 < len(raw) <= 32*1024*1024, path
    result, names = [], set()
    with ZipFile(BytesIO(raw)) as z:
        assert len(z.infolist()) <= 512 and sum(i.file_size for i in z.infolist()) <= 16*1024*1024
        for info in z.infolist():
            member = unicodedata.normalize('NFC', info.filename)
            parts = PurePosixPath(member).parts
            assert not PurePosixPath(member).is_absolute() and all(p not in ('', '.', '..') for p in parts)
            assert not re.search(r'[\\:\x00-\x1f]', member) and not info.flag_bits & 1
            assert not stat.S_ISLNK(info.external_attr >> 16) and member not in names
            names.add(member)
            if info.is_dir():
                assert parts == (topic,)
                continue
            assert len(parts) in (1, 2) and (len(parts) == 1 or parts[0] == topic)
            assert member.endswith('.txt') and 0 < info.file_size <= 128*1024
            body = z.read(info)  # ZIP CRC is checked by zipfile; no extraction paths are used.
            assert len(body) == info.file_size
            rec = parse(body, member, topic)
            rec.update(sourceArchiveSha256=sha(raw), sourceCrc32=f'{info.CRC:08x}')
            result.append(rec)
    assert len(result) == len({r['locality'] for r in result}) == 371, path
    return sorted(result, key=lambda r: r['locality'])


def text_fields(m):
    yield 'meta', m['meta']
    yield 'intro', m['intro']
    for i, s in enumerate(m['sections']):
        yield f'sections.{i}.heading', s['heading']
        for j, p in enumerate(s['paragraphs']):
            yield f'sections.{i}.paragraphs.{j}', p
    for i, f in enumerate(m['faq']):
        for k in ('question', 'answer'):
            yield f'faq.{i}.{k}', f[k]
    for i, p in enumerate(m['cases']):
        yield f'cases.{i}', p
