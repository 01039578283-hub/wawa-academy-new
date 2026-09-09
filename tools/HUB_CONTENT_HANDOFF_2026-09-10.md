# 와와학원.com 허브 내용 보강

## 범위

- 기준 커밋: c7202d0b6aad32f8e79b6816de23496c2e9eb572.
- 전국센터 1개 + 직속 과목·학년 허브 24개 + 과목별코칭/학년별코칭 2개 = 27개.
- 지역·경기 시군구 중간 허브 840개와 동네 상세 8,904개를 포함한 나머지 HTML 9,751개는 이번 작업에서 수정하지 않는다.
- 기존 title/H1/canonical/og:url, 연락처, 검색 목적지와 지역 연결 구조를 보존한다.

## 구현

- `enrich_top_hubs_site4.py`: 지정한 27개만 후처리한다. 과거 전체 원고 생성기를 실행하지 않는다.
- `data/hub-guides/subject-copy.json`: 과목형은 개념·문항·평가, 학년운영형은 과제·시간·복습을 중심으로 작성한 별도 원고. 81개 주제 섹션, 162개 문단, 고유 FAQ 81개.
- `data/hub-guides/center-examples.json`: source15 자료와 site4 기존 상세를 대조한 35개 예시 카탈로그 및 840개 실제 목적지. 화면에는 허브당 3개만 선택한다.
- 학교급별 실제 학년만 표시하고, 영수는 두 과목의 공통 학년을 확인한다. 조건부 수업 설명을 무조건 수업 가능으로 바꾸지 않는다.
- 옥계동·복산동·온천동은 주소말미가 불완전해 카탈로그는 보존하되 신규 예시 후보에서 제외했다. 주소를 추정해서 수정하지 않는다.
- 공통 학습 공간 사진 2개를 새 공유 경로에 추가했다. 실제 특정지점 사진으로 표기하지 않고, 접기·자르기 없이 전체 비율로 표시한다.
- 실제 화면의 FAQ 135쌍과 FAQPage 동기화, hasPart/mentions/센터 공통 @id 연결. 전국센터는 CollectionPage/ItemList 중심으로 정리했다.
- 수정 대상의 동작하지 않는 `?s=` SearchAction과 검증되지 않은 공통 운영시간 표시는 정리했다. 다른 페이지의 구조화 데이터는 건드리지 않았다.
- 모바일 제목 26~28px, 본문 16px, 빠른이동 2열과 44px 이상 주요 버튼. 기존 연락 방식과 3열 모바일 상담 바 유지.
- 원래의 분류 검색/동네 자동완성/상세 이동 기능과 `[hidden]` 상태를 유지한다.

## 재생성·검사

BeautifulSoup가 있는 Python 환경에서 실행:

```powershell
python tools/enrich_top_hubs_site4.py --date 2026-09-10
```

재실행 결과 changed 0 확인. 새 공개 수정일이 있을 때만 실제 시각으로 다음 명령을 실행한다:

```powershell
python tools/refresh_enriched_hub_discovery.py --modified '2026-09-10T07:04:00+09:00'
```

이 도구는 기존 sitemap 9,778 URL/RSS 32개 목록을 유지하면서 해당 27개 항목의 설명·수정일만 갱신한다. 오래된 discovery 생성기는 HTML 속성 순서에 의존하므로 이번 범위는 전용 갱신 도구를 사용한다.

검사/배포 결과는 비공개 `tools/reports/hub-enrichment/` 폴더에 기록한다. 상세 원본 대조·검수 자료는 Desktop/CodexData/tmp/site4-hub-enrichment-2026-09-10에 보관한다. 이 문서와 tools 전체는 기존 .vercelignore에 따라 공개 배포에서 제외한다.
