# 와와학원.com — 공식 자료 활용 모바일 업그레이드

## 상태와 작업 범위

- 작업: 2026-09-11 밤 시작, 2026-09-12 로컬 검증 완료. **미배포**.
- 실제 프로젝트: `C:\Users\1992k\Desktop\홈페이지 정리\새 홈페이지4`.
- 사이트: `https://xn--ol5ba64b839b.com` (와와학원.com).
- GitHub: `01039578283-hub/wawa-academy-new`, 기존 Vercel `wawa-coaching-site4`.
- 시작/종료 HEAD: `28a48fcd38db0ccad44918b7c17e42532bf763c9`. Git index 비어 있음. 커밋·push·배포·설정 변경 없음.
- 메인·학습코칭 2개, 전국센터 최상위 1개·직속 분류 24개·과목별코칭/학년별코칭 2개 = **29페이지**.
- 나머지 **9,749 HTML**은 수정하지 않았다. 동네 상세 8,904개와 지역 중간 허브 840개도 그대로다.
- 로컬: `http://127.0.0.1:8797/`. 해당 프로젝트에서 `python -m http.server 8797 --bind 127.0.0.1` 실행 중.
- 전국학원.com의 이전 미배포 작업(`새 홈페이지`, 포트 8796)과 별개다. 기본 cwd `홈페이지`도 이번 작업과 무관하다.

## 반영 내용

- 메인: 초중고 코칭 요약 → 과목·학년별 지역 안내 → 4C → 학습 공간 → AI 요약 → 공식 영상 → 학습가이드 → FAQ.
- 학습코칭: 4C 단계별 설명·질문, 플랜/학습/생활 관리, AI 영어/수학/국어/독서, 복습 기록 예시, 상담 준비, FAQ.
- 제작자 관점의 “홈페이지입니다”, “구조로 설계했습니다”, “FAQPage와 동일” 등 화면 문구를 방문자용 설명으로 교체.
- 기존 27허브의 과목·학년별 원고 81섹션, 실제 센터 정보, 지역 목록·검색·동네 목적지를 보존하고 서로 다른 코칭 요약 27개 추가.
- 각 요약에 해당 주제의 상세 설명으로 이동하는 링크 2개씩, 총 **54개**. 새 빠른 이동 “코칭·AI 활용” 추가.
- 이미지 9개·영상 썸네일 3개를 원본 바이트로 사용. 총 **1,826,093바이트**. 본문 사진을 숨기거나 접거나 자르지 않음.
- 영상은 YouTube 원본 링크 방식. 페이지에 iframe/동영상 플레이어 JS를 추가하지 않음.
- 모바일 본문 16px, 주요 버튼 44px 이상, 메뉴 4열, 목차 2열, 학습 카드 1열. 기존 하단 전화/문자/상담 버튼과 연락 목적지 유지.
- 새 CSS/짧은 앵커 보정 JS는 29페이지에만 로드한다. 기존 공용 CSS/JS는 바꾸지 않았다.
- 앵커는 주소의 해시를 남기며 즉시 이동하도록 구성. 이전 공용 smooth-scroll 리스너만 대상 페이지에서 우회한다.

## 사실과 구조화 데이터

- 공식 근거:
  - https://www.wawacenter.com/brand/wawacenter
  - https://www.wawacenter.com/intro/coachingSystem
  - https://www.wawacenter.com/intro/AISystem
- AI 영어·수학 초1~고3, AI 국어 중1~고3, AI 독서 초1~중2는 **본사 프로그램 대상**으로 표시. 모든 센터의 개설·시간·비용을 보장하지 않는다.
- 본사/공통 공간 사진과 특정 지점 시설을 구분. 실제 성과·강사·시설·일정·교습비를 새로 추정하지 않았다.
- 메인·학습코칭 title/description 정리. 전체 대상의 canonical·og:url·기존 og:image·소유확인 태그·연락처 보존. 허브 title/H1/description도 그대로다.
- WebPage/Article(학습코칭)/FAQPage/BreadcrumbList, hasPart, mentions, articleSection, significantLink를 실제 본문·링크에 맞춤.
- 메인의 작동하지 않는 SearchAction, 확인되지 않은 공통 운영시간, 실제 엔티티가 없는 service 참조 정리. 허브 기존 CollectionPage·ItemList·센터 엔티티 유지.
- 업로드 날짜·길이를 확인하지 않은 VideoObject, 허위 별점/후기는 추가하지 않음.
- 실제 화면 FAQ **145개**와 JSON-LD를 일치시킴 (메인/코칭 각 5개, 기존 허브 135개).
- sitemap 9,778개 URL·순서 유지, 해당 29개 수정일만 갱신. RSS 기존 32개 항목을 유지하고 대상 28개 제목/설명/날짜 동기화. llms.txt에 실제 코칭 링크와 프로그램 대상·센터 확인 범위 추가.
- 네이버 표준 HTML 링크 및 독립적인 본문/메타 작성 원칙 참고: https://searchadvisor.naver.com/guide/seo-basic-intro
- SEO/AEO/GEO 구조 보완은 검색 순위·노출수·AI 인용을 보장하지 않는다.

## 재생성

입력 원고/요약/출처는 `tools/data/brand-upgrade-20260911/`에 있다. 실행 도구는 BeautifulSoup4가 필요하다. 이번 환경에는 글로벌 환경을 바꾸지 않고 다음 비공개 경로에 설치했다:

`C:\Users\1992k\Desktop\CodexData\tmp\wawa4-upgrade-deps`

```powershell
$env:PYTHONPATH = 'C:\Users\1992k\Desktop\CodexData\tmp\wawa4-upgrade-deps'
python -X utf8 tools/upgrade_brand_site4.py
python -X utf8 tools/audit_brand_upgrade_site4.py
```

- 초기 이미지 반입은 검증된 전국학원.com 로컬 원본에서 복사했다. 이후에는 본 프로젝트의 원본·매니페스트만으로 재실행 가능하다.
- 생성기는 29페이지 목록을 고정하고 핵심 페이지 최초 변경 시 기준 커밋을 검사한다.
- 기존 허브 생성기를 실행했다면 이 후처리를 마지막에 다시 실행할 것. 지역별 원고 생성기를 이번 변경에 사용할 필요가 없다.
- 재실행 `changed: 0` 확인. 수정일은 최초 실제 작업 시각(2026-09-12T00:00:31+09:00)을 유지한다.

## 검증 결과

- 자체 정적 검사 **542/542 PASS**: 변경 범위, 기존 센터/목록/문구·연락처 보존, 메타, HTML ID/중첩, JSON-LD 참조, FAQ, 내부 링크·앵커·파일, 원본 이미지 해시, sitemap/RSS.
- 로컬 HTTP **49개** (29페이지 + 이미지12 + CSS/JS/검색발견파일8) 모두 200 및 로컬 파일 바이트 일치.
- 29페이지 × 실제 CSS 폭 320/390/1280px = **87회** 배치 검사. 주요 6페이지 768px 추가, 총 **93회**. 가로 넘침·텍스트 잘림·주요 버튼 높이·이미지 비율 실패 0.
- **145 FAQ 전부** 마우스/터치 클릭으로 열기 → Enter로 닫기 정상.
- 허브별 **54개 상세 링크 전부** 실제 이동 및 앵커 도착 위치 정상.
- 전국센터 검색(초등 영어/고등수학), 결과 없음, 초기화(24종 복원), 동네 검색 결과 없음·Escape 초기화·명일동 고등수학 상세 이동 확인.
- 메인/코칭 이미지 **12개 전부 로드·원본 비율** 확인.
- 인터뷰 영상 카드에서 원본 YouTube 새 탭 이동, 공식 채널·제목·동영상 플레이어 표시 확인. 전체 영상 재생이나 성과 내용의 진위를 검증했다는 뜻은 아님.
- `git diff --check` 통과. 배포 전 별도 승인 필요.

검사 원본: `tools/reports/brand-upgrade/`의 static-audit.json, browser-layout.json, browser-faqs.json, browser-deep-links.json, browser-interactions.json, browser-media.json, generation.json.
이 문서·원고·검사 도구/결과는 기존 `.vercelignore`의 `tools/` 제외 규칙에 따라 공개 배포되지 않는다.
