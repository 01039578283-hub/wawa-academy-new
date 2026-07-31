from __future__ import annotations

import argparse
import html
import json
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
CENTER_ROOT = ROOT / "전국센터"
COMMON_ROOT = ROOT / "assets" / "centers" / "common"
MAP_ROOT = ROOT / "assets" / "maps"

COMMON_STEMS = ("seoul", "local")
EXPECTED_DETAIL_PAGES = 8_904

REPRESENTATIVE_RE = re.compile(
    r'<img\b[^>]*\bdata-role="representative-image"[^>]*>',
    re.I,
)
LOCAL_MEDIA_RE = re.compile(
    r'(?P<indent>^[ \t]*)'
    r'(?:'
    r'<picture class="responsive-local-media">\s*'
    r'<source srcset="(?P<picture_prefix>(?:\.\./)+assets/centers/common/)'
    r'(?P<picture_stem>seoul|local)\.webp" type="image/webp">\s*'
    r'<img src="(?P=picture_prefix)(?P=picture_stem)\.jpg" '
    r'alt="(?P<picture_alt>[^"]*)"[^>]*>\s*</picture>'
    r'|'
    r'<img src="(?P<img_prefix>(?:\.\./)+assets/centers/common/)'
    r'(?P<img_stem>seoul|local)\.(?:jpg|webp)" '
    r'alt="(?P<img_alt>[^"]*)"[^>]*>'
    r')',
    re.I | re.M,
)
MAP_RE = re.compile(
    r'(?P<indent>^[ \t]*)<img src="(?P<src>(?:\.\./)+assets/maps/[^"]+)" '
    r'alt="(?P<alt>[^"]*)"[^>]*>',
    re.I | re.M,
)


@lru_cache(maxsize=None)
def common_dimensions(stem: str) -> tuple[int, int]:
    with Image.open(COMMON_ROOT / f"{stem}.jpg") as image:
        return image.size


@lru_cache(maxsize=None)
def image_dimensions(image_path: Path) -> tuple[int, int]:
    with Image.open(image_path) as image:
        return image.size


def map_dimensions(page: Path, src: str) -> tuple[int, int]:
    relative = Path(unquote(html.unescape(src)))
    image_path = (page.parent / relative).resolve()
    if MAP_ROOT.resolve() not in image_path.parents:
        raise RuntimeError(f"지도 경로가 assets/maps 밖을 가리킵니다: {page} -> {src}")
    if not image_path.is_file():
        raise FileNotFoundError(f"지도 이미지를 찾을 수 없습니다: {page} -> {image_path}")
    return image_dimensions(image_path)


def detail_pages() -> list[Path]:
    pages: list[Path] = []
    for page in CENTER_ROOT.rglob("index.html"):
        source = page.read_text(encoding="utf-8", errors="strict")
        if LOCAL_MEDIA_RE.search(source):
            pages.append(page)
    return sorted(pages)


def convert_common_assets() -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for stem in COMMON_STEMS:
        source = COMMON_ROOT / f"{stem}.jpg"
        target = COMMON_ROOT / f"{stem}.webp"
        with Image.open(source) as image:
            converted = image.convert("RGB")
            converted.save(target, "WEBP", quality=92, method=6)
            width, height = converted.size
        result[stem] = {
            "width": width,
            "height": height,
            "jpg_bytes": source.stat().st_size,
            "webp_bytes": target.stat().st_size,
        }
    return result


def local_media_replacement(match: re.Match[str]) -> str:
    indent = match.group("indent")
    prefix = match.group("picture_prefix") or match.group("img_prefix")
    stem = (match.group("picture_stem") or match.group("img_stem")).lower()
    alt = match.group("picture_alt") or match.group("img_alt")
    width, height = common_dimensions(stem)
    return (
        f'{indent}<picture class="responsive-local-media">\n'
        f'{indent}  <source srcset="{prefix}{stem}.webp" type="image/webp">\n'
        f'{indent}  <img src="{prefix}{stem}.jpg" alt="{alt}" '
        f'width="{width}" height="{height}" loading="lazy" decoding="async">\n'
        f"{indent}</picture>"
    )


def transform_page(page: Path, source: str) -> str:
    representatives_before = REPRESENTATIVE_RE.findall(source)

    source, local_count = LOCAL_MEDIA_RE.subn(local_media_replacement, source, count=1)
    if local_count != 1:
        raise RuntimeError(f"본문 이미지가 정확히 1개가 아닙니다: {page} ({local_count})")

    def replace_map(match: re.Match[str]) -> str:
        width, height = map_dimensions(page, match.group("src"))
        return (
            f'{match.group("indent")}<img src="{match.group("src")}" '
            f'alt="{match.group("alt")}" width="{width}" height="{height}" '
            'loading="lazy" decoding="async">'
        )

    source, map_count = MAP_RE.subn(replace_map, source, count=1)
    if map_count != 1:
        raise RuntimeError(f"지도 이미지가 정확히 1개가 아닙니다: {page} ({map_count})")

    representatives_after = REPRESENTATIVE_RE.findall(source)
    if representatives_before != representatives_after:
        raise RuntimeError(f"숨김 대표이미지 태그가 변경되었습니다: {page}")
    return source


def audit(pages: list[Path]) -> dict[str, int]:
    counts = {
        "detail_pages": len(pages),
        "representative_images": 0,
        "optimized_local_media": 0,
        "dimensioned_maps": 0,
    }
    for page in pages:
        source = page.read_text(encoding="utf-8", errors="strict")
        counts["representative_images"] += len(REPRESENTATIVE_RE.findall(source))
        if '<picture class="responsive-local-media">' in source:
            counts["optimized_local_media"] += 1
        map_match = MAP_RE.search(source)
        if map_match and 'width="' in map_match.group(0) and 'decoding="async"' in map_match.group(0):
            counts["dimensioned_maps"] += 1
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "새 홈페이지4 상세페이지의 표시용 본문·지도 이미지를 최적화합니다. "
            "기본 실행은 감사만 하며 --apply를 지정해야 HTML을 변경합니다."
        )
    )
    parser.add_argument(
        "--convert-assets",
        action="store_true",
        help="seoul.jpg와 local.jpg를 품질 92 WebP로 변환합니다.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="8,904개 상세 HTML에 picture·크기·decoding 속성을 적용합니다.",
    )
    parser.add_argument(
        "--allow-page-count",
        type=int,
        default=EXPECTED_DETAIL_PAGES,
        help="안전 검증용 예상 상세페이지 수입니다.",
    )
    args = parser.parse_args()

    converted = convert_common_assets() if args.convert_assets else {}
    pages = detail_pages()
    if len(pages) != args.allow_page_count:
        raise RuntimeError(
            f"상세페이지 수가 예상과 다릅니다: {len(pages):,} != {args.allow_page_count:,}"
        )

    before = audit(pages)
    changed = 0
    if args.apply:
        for page in pages:
            source = page.read_text(encoding="utf-8", errors="strict")
            updated = transform_page(page, source)
            if updated != source:
                page.write_text(updated, encoding="utf-8", newline="\n")
                changed += 1

    after = audit(pages)
    if args.apply:
        if after["optimized_local_media"] != len(pages):
            raise RuntimeError("일부 상세페이지에 picture 요소가 적용되지 않았습니다.")
        if after["dimensioned_maps"] != len(pages):
            raise RuntimeError("일부 지도 이미지에 크기/decoding 속성이 적용되지 않았습니다.")
        if before["representative_images"] != after["representative_images"]:
            raise RuntimeError("숨김 대표이미지 개수가 변경되었습니다.")

    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "audit",
                "converted_assets": converted,
                "changed_pages": changed,
                "before": before,
                "after": after,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
