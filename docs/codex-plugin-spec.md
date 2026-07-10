# OpenAI Codex 플러그인 공식 스펙 정리

> 출처: 공식 문서 3개를 직접 확인해 정리 (2026-07-10)
> - 개요: https://developers.openai.com/codex/plugins
> - 제작 가이드: https://developers.openai.com/codex/plugins/build
> - 스킬: https://developers.openai.com/codex/skills

## 1. 플러그인 폴더 구조

```
my-plugin/
├── .codex-plugin/
│   └── plugin.json          # 필수: 플러그인 매니페스트 (이 폴더엔 이 파일만)
├── skills/
│   └── my-skill/
│       └── SKILL.md         # 선택: 스킬 정의
├── hooks/
│   └── hooks.json           # 선택: 라이프사이클 훅
├── .app.json                # 선택: 앱/커넥터 매핑
├── .mcp.json                # 선택: MCP 서버 설정
└── assets/                  # 선택: 아이콘, 로고, 스크린샷
```

- 필수 파일은 `.codex-plugin/plugin.json` 하나뿐. 나머지 구성 요소는 플러그인 루트에 위치.
- 매니페스트 내 모든 경로는 루트 기준 상대 경로로 `./` 시작, 루트 밖 불가.

## 2. `.codex-plugin/plugin.json` 스키마

필수 필드: `name`(kebab-case, 안정적 식별자), `version`, `description`

선택 필드:
- 퍼블리셔 메타데이터: `author`(name/email/url 객체), `homepage`, `repository`, `license`, `keywords`
- 구성 요소 포인터: `skills`(스킬 디렉토리), `mcpServers`(`.mcp.json` 경로), `apps`(`.app.json` 경로), `hooks`(기본값 `hooks/hooks.json`, 배열 가능)
- `interface` 객체(표시용): `displayName`, `shortDescription`, `longDescription`, `developerName`, `category`, `capabilities`, `websiteURL`, `privacyPolicyURL`, `termsOfServiceURL`, `defaultPrompt`(문자열 배열), `brandColor`, `composerIcon`, `logo`, `screenshots`

최소 예시:
```json
{
  "name": "my-first-plugin",
  "version": "1.0.0",
  "description": "Reusable greeting workflow",
  "skills": "./skills/"
}
```

전체 예시:
```json
{
  "name": "my-plugin",
  "version": "0.1.0",
  "description": "Bundle reusable skills and app integrations.",
  "author": { "name": "Your team", "email": "team@example.com", "url": "https://example.com" },
  "homepage": "https://example.com/plugins/my-plugin",
  "repository": "https://github.com/example/my-plugin",
  "license": "MIT",
  "keywords": ["research", "crm"],
  "skills": "./skills/",
  "mcpServers": "./.mcp.json",
  "apps": "./.app.json",
  "hooks": "./hooks/hooks.json",
  "interface": {
    "displayName": "My Plugin",
    "shortDescription": "Reusable skills and apps",
    "longDescription": "Distribute skills and app integrations together.",
    "developerName": "Your team",
    "category": "Productivity",
    "capabilities": ["Read", "Write"],
    "defaultPrompt": ["Use My Plugin to summarize new CRM notes."],
    "brandColor": "#10A37F",
    "composerIcon": "./assets/icon.png",
    "logo": "./assets/logo.png",
    "screenshots": ["./assets/screenshot-1.png"]
  }
}
```

## 3. SKILL.md 작성 형식

스킬 디렉토리 구조:
```
my-skill/
  ├── SKILL.md            # 필수
  ├── scripts/            # 선택
  ├── references/         # 선택
  ├── assets/             # 선택
  └── agents/
      └── openai.yaml     # 선택 (추가 메타데이터)
```

SKILL.md — frontmatter 필수 필드는 `name`, `description`:
```markdown
---
name: hello
description: Greet the user with a friendly message.
---

Greet the user warmly and ask how you can help.
```

- `description`에는 **언제 트리거되어야/되지 말아야 하는지**를 명확히 쓰고, 핵심 유스케이스·트리거 단어를 앞쪽에 배치 (컨텍스트 제약으로 잘릴 수 있음).
- 본문은 에이전트에게 주는 지시문 (명령형 단계 + 명시적 입력/출력).

선택 메타데이터 `agents/openai.yaml`:
```yaml
interface:
  display_name: "Optional user-facing name"
  short_description: "Optional user-facing description"
  default_prompt: "Optional surrounding prompt to use the skill with"

policy:
  allow_implicit_invocation: false   # 기본값 true

dependencies:
  tools:
    - type: "mcp"
      value: "openaiDeveloperDocs"
      description: "OpenAI Docs MCP server"
      transport: "streamable_http"
      url: "https://developers.openai.com/mcp"
```

트리거 방식:
1. 명시적: `/skills` 커맨드 또는 `$skill-name` 멘션
2. 암시적: Codex가 작업 설명과 매칭되는 스킬 자동 선택 (`policy.allow_implicit_invocation`으로 제어)

스킬 로딩 위치 (우선순위 순): `$CWD/.agents/skills` → `$REPO_ROOT/.agents/skills` → `$HOME/.agents/skills` → `/etc/codex/skills` → 내장

## 4. `.mcp.json` / MCP 서버 연동

두 형식 모두 허용:
```json
{ "docs": { "command": "docs-mcp", "args": ["--stdio"] } }
```
```json
{ "mcp_servers": { "docs": { "command": "docs-mcp", "args": ["--stdio"] } } }
```

## 5. 설치 / 실행 / 테스트 (CLI)

```bash
# 로컬 마켓플레이스 등록 (로컬 테스트용)
codex plugin marketplace add ./local-marketplace-root

# 관리
codex plugin marketplace list
codex plugin marketplace upgrade [marketplace-name]
codex plugin marketplace remove marketplace-name
```

- `codex` 실행 후 `/plugins` → 플러그인 브라우저에서 "Install plugin", Space로 활성/비활성 토글
- 프롬프트에서 `@` 입력으로 플러그인/스킬 명시 호출, 또는 작업 설명 시 자동 선택
- 설치 경로: `~/.codex/plugins/cache/$MARKETPLACE_NAME/$PLUGIN_NAME/$VERSION/`
- 스캐폴딩: `@plugin-creator` 스킬, `$skill-creator` 스킬

로컬 테스트용 마켓플레이스 메타파일 — 위치: `$REPO_ROOT/.agents/plugins/marketplace.json` (또는 `~/.agents/plugins/marketplace.json`):
```json
{
  "name": "local-example-plugins",
  "interface": { "displayName": "Local Example Plugins" },
  "plugins": [
    {
      "name": "my-plugin",
      "source": { "source": "local", "path": "./plugins/my-plugin" },
      "policy": { "installation": "AVAILABLE", "authentication": "ON_INSTALL" },
      "category": "Productivity"
    }
  ]
}
```

- `installation` 정책 값: `AVAILABLE`, `INSTALLED_BY_DEFAULT`, `NOT_AVAILABLE`

## 6. 포함 가능한 구성 요소 (4종)

1. 스킬 (`skills/*/SKILL.md`)
2. MCP 서버 (`.mcp.json`)
3. 앱/커넥터 통합 (`.app.json` — ChatGPT 앱 연동)
4. 라이프사이클 훅 (`hooks/hooks.json`):
```json
{
  "hooks": {
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "python3 ${PLUGIN_ROOT}/hooks/session_start.py", "statusMessage": "Loading plugin context" } ] }
    ]
  }
}
```
- 훅 환경변수: `PLUGIN_ROOT`(설치 위치), `PLUGIN_DATA`(쓰기 가능 데이터 디렉토리)
- 커스텀 슬래시 커맨드는 문서에 없음 (스킬·앱·MCP·훅 4종만)

## 7. 제약사항 및 베스트 프랙티스

제약:
- 플러그인 이름 kebab-case, 매니페스트 경로는 `./` 시작 상대 경로만
- 훅은 비관리 코드 — 실행 전 사용자 신뢰 검토 필요
- **스킬 목록 초기 로딩은 컨텍스트의 2% (최대 약 8,000자)** — SKILL.md 전체는 스킬 선택 시에만 로드

베스트 프랙티스:
- 스킬은 좁고 집중된 범위로
- 스크립트보다 지시문(instructions) 우선
- 명령형 단계 + 명시적 입력/출력
- description 앞쪽에 트리거 단어·스코프 경계 배치, 실제 프롬프트로 트리거 테스트
