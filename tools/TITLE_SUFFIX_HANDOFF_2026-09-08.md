# 와와학원.com 본문 기반 타이틀 접미사

## 범위와 배포 연결

- 프로젝트: `새 홈페이지4`, 와와학원.com (`https://xn--ol5ba64b839b.com`).
- GitHub: `01039578283-hub/wawa-academy-new`, main.
- Vercel: `wawa-coaching-site4`, 기존 프로젝트·도메인 연결 유지.
- 기준 커밋: `79b8b74f402387a77d1624363dbbd415b387a12f`.
- 전국센터 최상위를 제외한 하위 9,768개: 상세 8,904개, 안내 허브 864개.
- 홈·상담문의·과목별코칭·학년별코칭·학습코칭·학습가이드 및 가이드 자식 페이지는 변경하지 않는다.
- 변경 범위는 `<title>`과 기존 OG/Twitter 제목 값, 연결된 RSS 항목의 제목뿐이다.
- 제목 앞부분·H1·본문·이미지·디자인·URL·JSON-LD는 보존한다.
- 사이트맵 9,778개 URL과 RSS 32개 항목의 링크·내용·날짜는 그대로 유지한다.

## 개별화 기준

- 해당 페이지의 실제 `seo-geo-section` 직접 답변과 학생 상황에서 근거를 추출한다.
- 센터 주소·학교 목록·후기·다른 페이지 추천 문구는 접미사의 학습 근거로 사용하지 않는다.
- 과목형 페이지는 개념·문항·평가 대비를, 학년형 페이지는 시간표·과제 이행·복습 관리를 우선한다.
- 수학/영어 단일 과목의 접미사는 해당 과목의 근거를 포함하고 반대 과목의 내용은 제외한다.
- 초등·중등에 수능/모의고사 제목을 붙이지 않는다.
- 카테고리 허브는 자신의 소개글, 지역 허브는 실제 지역 구성·동네 수를 요약한다.
- 같은 본문 주제에는 같은 접미사를 쓸 수 있다. 무작위 표현이나 근거 없는 사실로 고유성을 만들지 않는다.

## 검증과 재실행

- `python -X utf8 tools/personalize_title_suffixes.py`: 적용 계획 생성.
- `python -X utf8 tools/personalize_title_suffixes.py --write`: 제목 적용.
- `python -X utf8 tools/personalize_title_suffixes.py --check`: 재실행 일관성 확인.
- `python -X utf8 tools/test_title_suffixes.py`: 근거/학년/과목/학년형 우선순위 회귀검사.
- `python -X utf8 tools/verify_title_release.py`: 전체 제목, 실제 근거, 본문 보존, RSS·사이트맵 검사.
- `python -X utf8 tools/check_title_legacy_audits.py`: 기존 4개 배포 검사 실행.
- `python -X utf8 tools/verify_title_release.py --public`: 공개 URL의 유형별 표본 확인.
- 로컬 본문은 바이트 단위로 보존한다. Git/공개 서버와 비교할 때는 CRLF/LF 줄바꿈 차이만 정규화한다.
- 제목 처리 전 원고 생성·신뢰도 후처리를 다시 실행하지 않는다. 추후 원고를 재생성한 경우에는 원래 후처리 뒤 제목 처리를 마지막에 실행한다.
- 현재 페이지 수와 기준 커밋은 이번 작업 범위에 고정되어 있으므로, 페이지 추가 시 다음 작업 범위에 맞게 갱신한다.
- `title-suffix-audit.json`에 페이지별 변경 전/후 제목, 근거 문장, 보존 해시를 남긴다.
- 공개 배포 결과는 로컬 `tools/reports/title-suffix-release.json`과 `title-suffix-public-verification.json`에 기록한다.

## 이번 변경의 로컬 검증 결과

- 9,768개 전체 제목 변경 및 본문 보존 검사 통과, 실패 0건.
- 재실행 일관성 검사(`--check`) 통과. 같은 본문에 다시 실행해도 제목을 바꾸지 않는다.
- 회귀검사 8개와 기존 AEO/GEO·FAQ·최종검증·검색의도 검사 4종 모두 통과.
- 전체 타이틀 9,768개가 서로 다르며, 본문에 근거한 접미사는 444종이다. 전체 타이틀 길이는 24~43자다.
- RSS 32개 항목 중 대상 카테고리 제목 24개를 동기화했다.
- 예: `명일동 고등 수학학원 | 오답 풀이의 근거·계산 정확도 점검`.
- 예: `명일동 고등학생 수학학원 | 오답 재풀이 일정·계산 정확도 점검`.
