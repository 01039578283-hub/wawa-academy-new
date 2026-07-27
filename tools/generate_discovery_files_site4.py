from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from email.utils import format_datetime
from pathlib import Path
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
DOMAIN = "https://xn--ol5ba64b839b.com"
RSS_URL = f"{DOMAIN}/rss.xml"
RSS_LINK = (
    f'  <link rel="alternate" type="application/rss+xml" '
    f'title="와와학습코칭학원 학습정보 RSS" href="{RSS_URL}">\n'
)
RSS_DISCOVERY_PAGES = [
    ROOT / "index.html",
    ROOT / "학습가이드" / "index.html",
    *(ROOT / "전국센터" / name / "index.html" for name in (
        "수학학원", "영어학원", "영수학원", "초등학생학원", "중학생학원", "고등학생학원"
    )),
]
CORE_RSS_PAGES = [
    ROOT / "학습가이드" / "index.html",
    ROOT / "학습가이드" / "시험기간-학습계획" / "index.html",
    ROOT / "학습가이드" / "오답관리-루틴" / "index.html",
    ROOT / "학습가이드" / "학부모상담-준비" / "index.html",
    ROOT / "학습코칭" / "index.html",
    ROOT / "과목별코칭" / "index.html",
    ROOT / "학년별코칭" / "index.html",
    *(ROOT / "전국센터" / name / "index.html" for name in (
        "수학학원", "영어학원", "영수학원", "초등학생학원", "중학생학원", "고등학생학원"
    )),
]
RECENT_DETAIL_LIMIT = 24


def git_output(args: list[str]) -> bytes:
    return subprocess.check_output(["git", "-c", "core.quotepath=false", *args], cwd=ROOT)


def git_modified_times() -> dict[str, datetime]:
    output = git_output(["log", "--format=@@%cI", "--name-only", "--no-renames", "--", "*.html"])
    current: datetime | None = None
    result: dict[str, datetime] = {}
    for raw_line in output.decode("utf-8", errors="strict").splitlines():
        line = raw_line.strip()
        if line.startswith("@@"):
            current = datetime.fromisoformat(line[2:])
        elif line and current and line not in result:
            result[line.replace("\\", "/")] = current
    return result


def dirty_html_paths() -> set[str]:
    commands = [
        ["diff", "--name-only", "-z"],
        ["diff", "--cached", "--name-only", "-z"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    ]
    result: set[str] = set()
    for command in commands:
        for raw_path in git_output(command).split(b"\0"):
            if raw_path:
                path = raw_path.decode("utf-8", errors="strict").replace("\\", "/")
                if path.endswith(".html"):
                    result.add(path)
    return result


def ensure_rss_discovery() -> int:
    changed = 0
    for path in RSS_DISCOVERY_PAGES:
        source = path.read_text(encoding="utf-8", errors="strict")
        if 'type="application/rss+xml"' in source:
            continue
        updated = source.replace("</head>", RSS_LINK + "</head>", 1)
        if updated == source:
            raise RuntimeError(f"head 요소를 찾을 수 없습니다: {path}")
        path.write_text(updated, encoding="utf-8")
        changed += 1
    return changed


def page_metadata(path: Path) -> tuple[str, str, str]:
    source = path.read_text(encoding="utf-8", errors="strict")
    title_match = re.search(r"<title>(.*?)</title>", source, re.S | re.I)
    desc_match = re.search(r'<meta name="description" content="([^"]*)"', source, re.I)
    canonical_match = re.search(r'<link rel="canonical" href="([^"]+)"', source, re.I)
    if not title_match or not desc_match or not canonical_match:
        raise RuntimeError(f"필수 메타데이터 누락: {path}")
    title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", title_match.group(1))).strip()
    return title, desc_match.group(1).strip(), canonical_match.group(1).strip()


def all_pages() -> list[Path]:
    return sorted(
        (path for path in ROOT.rglob("index.html") if ".git" not in path.parts),
        key=lambda path: (len(path.relative_to(ROOT).parts), path.as_posix()),
    )


def collect_records() -> tuple[list[dict], dict[str, datetime]]:
    ensure_rss_discovery()
    history = git_modified_times()
    dirty = dirty_html_paths()
    now = datetime.now().astimezone()
    records = []
    modified_by_path: dict[str, datetime] = {}
    canonical_seen: set[str] = set()
    for path in all_pages():
        relative = path.relative_to(ROOT).as_posix()
        title, description, canonical = page_metadata(path)
        if canonical in canonical_seen:
            raise RuntimeError(f"canonical 중복: {canonical}")
        canonical_seen.add(canonical)
        modified = now if relative in dirty else history.get(relative)
        if modified is None:
            raise RuntimeError(f"Git 수정일을 확인할 수 없습니다: {relative}")
        modified_by_path[relative] = modified
        records.append(
            {
                "path": path,
                "relative": relative,
                "title": title,
                "description": description,
                "canonical": canonical,
                "modified": modified,
            }
        )
    return records, modified_by_path


def write_sitemap(records: list[dict]) -> None:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for record in records:
        lines.extend(
            [
                "  <url>",
                f"    <loc>{escape(record['canonical'])}</loc>",
                f"    <lastmod>{record['modified'].date().isoformat()}</lastmod>",
                "  </url>",
            ]
        )
    lines.append("</urlset>")
    (ROOT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def rss_selection(records: list[dict]) -> list[dict]:
    by_path = {record["path"]: record for record in records}
    selected = [by_path[path] for path in CORE_RSS_PAGES]
    selected_urls = {record["canonical"] for record in selected}
    detail_candidates = [
        record
        for record in records
        if record["relative"].startswith("전국센터/")
        and len(record["path"].relative_to(ROOT).parts) >= 4
        and record["canonical"] not in selected_urls
    ]
    detail_candidates.sort(key=lambda record: (record["modified"], record["relative"]), reverse=True)
    selected.extend(detail_candidates[:RECENT_DETAIL_LIMIT])
    return sorted(selected, key=lambda record: (record["modified"], record["relative"]), reverse=True)


def write_rss(records: list[dict]) -> int:
    selected = rss_selection(records)
    build_time = max(record["modified"] for record in selected)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">',
        "  <channel>",
        "    <title>와와학습코칭학원 학습정보</title>",
        f"    <link>{DOMAIN}/</link>",
        "    <description>학습가이드와 최근 보강된 지역별 학습코칭 안내를 선별해 제공합니다.</description>",
        "    <language>ko-KR</language>",
        f"    <lastBuildDate>{format_datetime(build_time)}</lastBuildDate>",
        f'    <atom:link href="{RSS_URL}" rel="self" type="application/rss+xml" />',
    ]
    for record in selected:
        lines.extend(
            [
                "    <item>",
                f"      <title>{escape(record['title'])}</title>",
                f"      <link>{escape(record['canonical'])}</link>",
                f'      <guid isPermaLink="true">{escape(record["canonical"])}</guid>',
                f"      <description>{escape(record['description'])}</description>",
                f"      <pubDate>{format_datetime(record['modified'])}</pubDate>",
                "    </item>",
            ]
        )
    lines.extend(["  </channel>", "</rss>"])
    (ROOT / "rss.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(selected)


def main() -> None:
    records, _ = collect_records()
    write_sitemap(records)
    rss_items = write_rss(records)
    print(
        json.dumps(
            {
                "sitemap_urls": len(records),
                "sitemap_lastmods": len(records),
                "rss_items": rss_items,
                "rss_discovery_pages": len(RSS_DISCOVERY_PAGES),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
