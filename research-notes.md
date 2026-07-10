
## 삼일PwC: DART 재무 레드플래그 스크리너

**컨셉**: 금감원이 반기마다 공개하는 회계감리 지적사례를 룰셋으로 코드화 →
Codex가 DART Open API로 상장사 재무제표를 받아 자동 스크리닝.

**사용 장면**
```
회계사> "OO전자 최근 3개년 재무제표에서 감리 지적 패턴 레드플래그 점검해줘"

① DART API로 기업 고유번호 조회 → 3개년 전체 재무제표 수집
② 룰셋 적용: 매출채권 증가율 vs 매출 증가율 괴리(가공매출 패턴),
   영업이익-영업현금흐름 괴리, 재고자산 급증, 대손충당금 비율 이상,
   종속·관계기업 손상 미인식 징후, 주석 필수기재 누락 등 10여 개
   — 각 룰은 금감원 2025 하반기 지적사례 10건에 매핑
③ 레드플래그별 근거 수치 + 지적사례 유형 인용 리포트 생성
```

**구성**: 스킬 2개(`dart-screener` 메인 + `peer-compare` 동종업계 비교)
+ `scripts/dart_client.py` + `references/red-flag-rules.md`(룰↔지적사례↔출처 매핑)

**검증**: 과거 실제 분식·감리 지적 기업의 당시 재무제표 **백테스트** — 룰셋이 실제 사고를
잡아내는지 실데이터로 증명. 심사 AI도 DART API·금감원 사례를 직접 확인 가능.

**리스크**: DART API 키 필요(무료, 즉시 발급). 낮음.

**공개 근거 (URL 생존 확인)**
- DART Open API (무료 공개): https://opendart.fss.or.kr/intro/main.do
- 머니투데이 2026-06-28, 금감원 2025 하반기 감리 지적사례 10건: https://www.mt.co.kr/stock/2026/06/28/2026062723393537244
- 이투데이 2026-06-01, 삼일 포함 10개 법인 품질관리 감리 평균 지적 8건: https://www.etoday.co.kr/news/view/2589566
- 아시아경제 2023-04-14, 신외감법 후 감사보수 +84.1%·품질 개선 미입증: https://view.asiae.co.kr/article/2023041210055463302
- 파이낸셜뉴스, XBRL 확대에도 활용 도구 부재: https://www.fnnews.com/news/202409252022309788

**같은 기업 대안**: K-SOX RCM 점검 도구(금융위 공식 비용 수치 — 고도화 4,600만원 + 연 수감
4,000~4,600만원: https://www.fsc.go.kr/no010101/79041), 감사조서 필수항목 검사기(한공회 빅4
템플릿 배포: https://intn.co.kr/news/articleView.html?idxno=2013571)

## Codex 플러그인 스펙 요약 (공식 문서 확인 완료)

- 필수 파일: `.codex-plugin/plugin.json` (name kebab-case / version / description 필수)
- 스킬: `skills/<이름>/SKILL.md` — frontmatter에 `name`, `description` 필수.
  `$skill-name` 명시 호출 또는 암시적 자동 트리거
- MCP: `.mcp.json` (직접 서버 맵 또는 `mcp_servers` 래핑 둘 다 허용)
- 로컬 테스트: `.agents/plugins/marketplace.json` 작성 후
  `codex plugin marketplace add ./local-marketplace-root` → `/plugins`에서 설치
- 제약: 스킬 목록 초기 로딩 최대 ~8,000자 → description 앞쪽에 트리거 단어 배치
- 출처: https://developers.openai.com/codex/plugins , /codex/plugins/build , /codex/skills
