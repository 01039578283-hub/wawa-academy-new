from __future__ import annotations

import html
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"
INFO_PATH = ROOT / "tools" / "center_info.json"
REGIONS = ["서울", "경기", "인천", "충청", "대전", "대구", "울산", "부산", "경상", "광주", "전라", "강원", "제주"]
HUB_NAMES = ["수학학원", "영어학원", "영수학원", "초등학생학원", "중학생학원", "고등학생학원"]
START_MARKER = "<!-- hub-directory-tools:start -->"
END_MARKER = "<!-- hub-directory-tools:end -->"
DIRECTORY_CLASS_PATTERN = re.compile(
    r"<section\b(?P<attrs>[^>]*class=\"[^\"]*(?:math-child-section|english-child-index|"
    r"combined-child-index|grade-child-index|math-level-child-index|english-level-child-index)[^\"]*\"[^>]*)>",
    re.I,
)


def normalize(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def load_centers() -> tuple[dict[str, dict], list[str]]:
    raw = json.loads(INFO_PATH.read_text(encoding="utf-8"))
    centers = {normalize(key).replace(" ", ""): value for key, value in raw.items()}
    return centers, sorted(centers, key=len, reverse=True)


def leaf_from_href(href: str) -> str:
    parts = [part for part in unquote(href).split("/") if part and part not in {"..", "."}]
    return parts[-1] if parts else ""


def find_dong(leaf: str, dong_names: list[str]) -> str:
    for dong in dong_names:
        if leaf.startswith(dong):
            return dong
    raise ValueError(f"센터정보에서 동네를 찾을 수 없습니다: {leaf}")


def clean_previous(source: str) -> str:
    source = re.sub(
        rf"\s*{re.escape(START_MARKER)}.*?{re.escape(END_MARKER)}\s*",
        "\n",
        source,
        flags=re.S,
    )
    source = source.replace(' data-hub-directory="true"', "")
    source = re.sub(r'\sdata-hub-item="true"', "", source)
    source = re.sub(r'\sdata-region="[^"]*"', "", source)
    source = re.sub(r'\sdata-district="[^"]*"', "", source)
    source = re.sub(r'\sdata-search="[^"]*"', "", source)
    return source


def toolbar(hub_name: str, counts: Counter[str], total: int) -> str:
    region_buttons = [
        f'<button type="button" class="hub-region-chip is-active" data-hub-region="all" aria-pressed="true">전체 <span>{total:,}</span></button>'
    ]
    for region in REGIONS:
        region_buttons.append(
            f'<button type="button" class="hub-region-chip" data-hub-region="{region}" aria-pressed="false">'
            f'{region} <span>{counts[region]:,}</span></button>'
        )
    buttons = "\n              ".join(region_buttons)
    return f'''{START_MARKER}
    <section class="section hub-directory-tools" data-hub-tools="true" aria-labelledby="hub-directory-title">
      <div class="wrap">
        <div class="hub-finder" role="search">
          <div class="hub-finder-heading">
            <div>
              <p class="eyebrow">ACADEMY DIRECTORY</p>
              <h2 id="hub-directory-title">{html.escape(hub_name)} 지역페이지 찾기</h2>
              <p>동네 이름을 검색하거나 광역지역을 선택한 뒤, 시·군·구 목록을 펼쳐 확인하세요.</p>
            </div>
            <strong class="hub-total-count">전체 {total:,}개 페이지</strong>
          </div>
          <div class="hub-search-row">
            <label for="hub-local-search">동네 또는 시·군·구 검색</label>
            <div class="hub-search-control">
              <input id="hub-local-search" type="search" inputmode="search" autocomplete="off"
                placeholder="예: 명일동, 강동구" aria-describedby="hub-search-status">
              <button type="button" class="hub-search-clear" data-hub-clear="true">검색 초기화</button>
            </div>
          </div>
          <div class="hub-region-filter" role="group" aria-label="광역지역 선택">
              {buttons}
          </div>
          <div class="hub-finder-footer">
            <p id="hub-search-status" class="hub-search-status" aria-live="polite">전체 {total:,}개 페이지를 표시합니다.</p>
            <div class="hub-fold-actions" aria-label="지역 목록 펼치기 설정">
              <button type="button" data-hub-expand="true">검색 결과 펼치기</button>
              <button type="button" data-hub-collapse="true">모두 접기</button>
            </div>
          </div>
        </div>
      </div>
    </section>
    {END_MARKER}'''


def enhance_hub(path: Path, centers: dict[str, dict], dong_names: list[str]) -> tuple[int, bool]:
    original = path.read_text(encoding="utf-8", errors="strict")
    source = clean_previous(original)
    first = DIRECTORY_CLASS_PATTERN.search(source)
    final_cta = source.find('<section class="final-cta"', first.start() if first else 0)
    if not first or final_cta < 0:
        raise RuntimeError(f"지역 링크 섹션 범위를 찾을 수 없습니다: {path}")

    prefix = source[: first.start()]
    directory = source[first.start() : final_cta]
    suffix = source[final_cta:]
    directory = DIRECTORY_CLASS_PATTERN.sub(
        lambda match: f'<section{match.group("attrs")} data-hub-directory="true">',
        directory,
    )

    counts: Counter[str] = Counter()
    item_count = 0

    def annotate_anchor(match: re.Match[str]) -> str:
        nonlocal item_count
        attrs = match.group("attrs")
        class_match = re.search(r'class="([^"]*)"', attrs)
        if not class_match or "mini-link" not in class_match.group(1).split():
            return match.group(0)
        href_match = re.search(r'href="([^"]+)"', attrs)
        if not href_match:
            return match.group(0)
        leaf = leaf_from_href(href_match.group(1))
        dong = find_dong(leaf, dong_names)
        branch = centers[dong]
        region = normalize(branch["지역"])
        district = normalize(branch["시or구"])
        label = normalize(re.sub(r"<[^>]+>", " ", match.group("label")))
        search_text = normalize(f"{label} {dong} {region} {district}")
        item_count += 1
        counts[region] += 1
        injected = (
            f'{attrs} data-hub-item="true" data-region="{html.escape(region, quote=True)}"'
            f' data-district="{html.escape(district, quote=True)}"'
            f' data-search="{html.escape(search_text, quote=True)}"'
        )
        return f'<a{injected}>{match.group("label")}</a>'

    directory = re.sub(
        r'<a\b(?P<attrs>[^>]*)>(?P<label>.*?)</a>',
        annotate_anchor,
        directory,
        flags=re.I | re.S,
    )
    if item_count != 1484:
        raise RuntimeError(f"{path.parent.name}: 지역 링크 {item_count}개 (예상 1484개)")
    missing_regions = [region for region in REGIONS if counts[region] == 0]
    if missing_regions:
        raise RuntimeError(f"{path.parent.name}: 광역지역 누락 {missing_regions}")

    updated = prefix + toolbar(path.parent.name, counts, item_count) + "\n" + directory + suffix
    if updated != original:
        path.write_text(updated, encoding="utf-8")
        return item_count, True
    return item_count, False


def main() -> None:
    centers, dong_names = load_centers()
    changed = 0
    total_links = 0
    for name in HUB_NAMES:
        count, did_change = enhance_hub(CENTER_ROOT / name / "index.html", centers, dong_names)
        total_links += count
        changed += int(did_change)
        print(f"{name}: links={count} changed={did_change}")
    print(json.dumps({"hubs": len(HUB_NAMES), "changed": changed, "links": total_links}, ensure_ascii=False))


if __name__ == "__main__":
    main()
