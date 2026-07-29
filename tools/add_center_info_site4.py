from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"

SUFFIXES = {
    "수학학원": ["초등수학학원", "중등수학학원", "고등수학학원", "수학학원"],
    "영어학원": ["초등영어학원", "중등영어학원", "고등영어학원", "영어학원"],
    "영수학원": ["초등영수학원", "중등영수학원", "고등영수학원", "영수학원"],
    "초등학생학원": ["초등학생수학학원", "초등학생영어학원", "초등학생영수학원", "초등학생학원"],
    "중학생학원": ["중학생수학학원", "중학생영어학원", "중학생영수학원", "중학생학원"],
    "고등학생학원": ["고등학생수학학원", "고등학생영어학원", "고등학생영수학원", "고등학생학원"],
}


def load_center_info() -> dict[str, dict]:
    with open(Path(__file__).parent / "center_info.json", encoding="utf-8") as f:
        raw = json.load(f)
    return {k.replace(" ", ""): v for k, v in raw.items()}


def extract_dong(category: str, leaf_name: str) -> str | None:
    for suf in SUFFIXES[category]:
        if leaf_name.endswith(suf):
            return leaf_name[: -len(suf)]
    return None


def target_files() -> list[Path]:
    return sorted(
        path
        for path in CENTER_ROOT.glob("*/*/index.html")
        if 'data-intent-role="' in path.read_text(encoding="utf-8", errors="ignore")
    )


def schools_or_placeholder(value: str) -> list[str]:
    value = (value or "").strip()
    if not value:
        return ["정보 준비중"]
    return [s.strip() for s in value.split(",") if s.strip()]


def render_pills(schools: list[str]) -> str:
    return "".join(f"<span>{html.escape(s)}</span>" for s in schools)


def render_location_section(branch: dict) -> str:
    address = html.escape(branch["센터 주소"])
    reg_name = html.escape(branch["교육지원청명칭"])
    reg_no = html.escape(branch["교육지원청 등록번호"])
    elem = render_pills(schools_or_placeholder(branch["타깃학교\n(초)"]))
    middle = render_pills(schools_or_placeholder(branch["타깃학교\n(중)"]))
    high = render_pills(schools_or_placeholder(branch["타깃학교\n(고)"]))
    return f"""
    <section class="section muted" aria-label="센터 위치 및 등록 정보">
      <div class="wrap two-col">
        <article class="info-card">
          <span class="card-tag">LOCATION</span>
          <h3>센터 위치 안내</h3>
          <p><strong>주소</strong><br>{address}</p>
          <p><strong>등록정보</strong><br>{reg_name} · {reg_no}</p>
        </article>
        <article class="info-card">
          <span class="card-tag">TARGET SCHOOLS</span>
          <h3>주요 타깃학교(이외 학교도 수업 가능)</h3>
          <p><strong>초등</strong></p>
          <div class="pill-list">{elem}</div>
          <p><strong>중등</strong></p>
          <div class="pill-list">{middle}</div>
          <p><strong>고등</strong></p>
          <div class="pill-list">{high}</div>
        </article>
      </div>
    </section>
"""


def process_page(page_dir: Path, center_info: dict[str, dict]) -> bool:
    category = page_dir.parent.name
    leaf = page_dir.name
    dong = extract_dong(category, leaf)
    branch = center_info[dong.replace(" ", "")]

    path = page_dir / "index.html"
    source = path.read_text(encoding="utf-8", errors="ignore")
    if 'aria-label="센터 위치 및 등록 정보"' in source:
        return False
    updated = source

    # 1) JSON-LD: add address + identifier to EducationalOrganization node
    m = re.search(r'<script type="application/ld\+json">(.*?)</script>', updated, re.S)
    data = json.loads(m.group(1))
    graph = data["@graph"]
    org = None
    for node in graph:
        t = node.get("@type")
        types = t if isinstance(t, list) else [t]
        if "EducationalOrganization" in types:
            org = node
            break

    org["address"] = {
        "@type": "PostalAddress",
        "streetAddress": branch["센터 주소"],
        "addressRegion": branch["지역"],
        "addressLocality": branch["시or구"],
        "addressCountry": "KR",
    }
    org["identifier"] = {
        "@type": "PropertyValue",
        "propertyID": "교육지원청 등록번호",
        "value": branch["교육지원청 등록번호"],
    }

    rendered = '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "</script>"
    updated = updated[: m.start()] + rendered + updated[m.end():]

    # 2) Visible section: insert right before the seo-geo-enhancement block (present on every detail page)
    section_html = render_location_section(branch)
    anchor = "<!-- seo-geo-enhancement:start -->"
    if anchor not in updated:
        raise RuntimeError(f"anchor not found: {path}")
    updated = updated.replace(anchor, section_html + "\n    " + anchor, 1)

    if updated != source:
        path.write_text(updated, encoding="utf-8")
        return True
    return False


def main() -> None:
    center_info = load_center_info()
    targets = target_files()
    changed = 0
    errors = 0
    for f in targets:
        try:
            if process_page(f.parent, center_info):
                changed += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"ERROR {f}: {exc}")
    print(json.dumps({"targets": len(targets), "changed": changed, "errors": errors}, ensure_ascii=False))


if __name__ == "__main__":
    main()
