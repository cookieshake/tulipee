# YouTrack 이슈 생성 플로우

Tulipee가 채팅 메시지를 LLM 기반 멀티턴 대화로 받아 YouTrack 이슈(작업)를 만드는 방식입니다.

## 개요
- 트리거: Zulip 스트림 `youtrack`, 토픽 `create issue`에 올라온 메시지
- 핸들러: `tulipee/handlers/youtrack_create.py`
- 백엔드 서비스:
  - LLM: OpenRouter/OpenAI (`openai` SDK, `tulipee/utils/llm.py`)
  - YouTrack REST 클라이언트: `tulipee/utils/youtrack.py`
- 프로젝트 카탈로그: `tulipee/handlers/youtrack_projects.py`

## 설정
다음 환경 변수를 설정합니다(.env 또는 컨테이너 `-e`):
- `ZULIP_URL`, `API_KEY`, `EMAIL`
- `YOUTRACK_URL`, `YOUTRACK_TOKEN`
- LLM(권장): `OPENAI_API_KEY`, 선택 `OPENAI_BASE_URL`(기본 OpenRouter), `OPENAI_MODEL`, `OPENAI_HTTP_REFERER`, `OPENAI_APP_TITLE`

Docker 실행 예시:
```bash
docker run --rm \
  -e ZULIP_URL=... -e API_KEY=... -e EMAIL=... \
  -e YOUTRACK_URL=... -e YOUTRACK_TOKEN=... \
  -e OPENAI_API_KEY=... ghcr.io/<owner>/tulipee:latest
```

## 프로젝트 카탈로그
- 위치: `tulipee/handlers/youtrack_projects.py`
- `PROJECTS` 리스트에 `(id, key, name, description)`를 채워 넣으세요.
- LLM이 이 카탈로그를 받아 가장 적절한 프로젝트를 고르고, 핸들러가 `project_id`/`project_key`/`project_name`을 내부 ID로 해석(`resolve_project_id`)합니다.

## 대화 흐름(LLM 주도)
- 상태/히스토리 저장소:
  - 대화 히스토리: `chat_history` (`tulipee/utils/conversation.py`), 스트림/토픽/사용자 단위
  - 플로우 상태: `flow_store`(LLM이 유지/갱신할 임의 JSON)
- 턴 처리:
  - `issue_flow_turn()`(`tulipee/utils/llm.py`)가 최근 사용자 메시지, 이전 상태, 카탈로그, 히스토리를 받아 다음 JSON을 반환:
    - `reply`: 사용자에게 보낼 텍스트(사용자 언어 유지)
    - `intent`: `ask | create | cancel`
    - `issue`: 영어로 구조화된 이슈 `{ title, description, type, project_* }`
    - `state`: 다음 턴에 사용할 내부 상태
- 초안 미리보기:
  - 생성 전에는 봇이 Title/Type/Project, 짧은 Description을 포함한 “Draft preview”를 자동으로 붙여 확인을 돕습니다.
- 최종 생성:
  - `intent=create`일 때 `summary`, `description`, 해석된 `project_id`로 YouTrack에 생성하고, 필요한 경우 `Type`(기본 `Task`) 커스텀 필드를 설정합니다.

## LLM 계약과 제약
- 엄격한 JSON 스키마(`response_format=json_schema`) 적용:
  - 멀티턴: `ISSUE_FLOW_SCHEMA`
  - 단발 파서(폴백): `ISSUE_PARSE_SCHEMA`
- 견고한 파싱:
  - `_extract_json_object()`가 코드펜스 제거/중괄호 균형 등으로 모델 텍스트에서 JSON을 추출합니다.
- 간결성·형식:
  - Title/Description은 항상 영어(Reply는 사용자 언어).
  - 미니멀 템플릿 강제:
    - Objective(한 문장)
    - Subtasks(최대 3개, 한 줄씩)
    - Acceptance Criteria(최대 3개, 한 줄씩)
  - 상한: Title ≤ 80자, Description ≤ 800자.
  - 보안/프라이버시 우려로 생성 차단 금지(필요 시 한 줄 advisory만).

## YouTrack 연동
- 클라이언트: `tulipee/utils/youtrack.py`
  - `create_issue(summary, description, project_id, type_name=None)`
  - `type_name`이 주어지면 `customFields`의 “Type”을 설정(`Task`, `Bug` 등).
- 성공 시: `idReadable`와 링크(`{YOUTRACK_URL}/issue/{idReadable}`)를 스레드에 회신합니다.

## 예시 대화
사용자(한국어):
> 앱 온보딩 개선 작업 필요. 체크리스트와 수락 기준 간단히 잡아줘. 프로젝트는 APP.

봇(한국어 reply + 미리보기):
- “이렇게 진행할까요?”
- Draft preview:
  - Title: Improve onboarding (mobile)
  - Type: Task
  - Project: APP (Mobile App)
  - Description:
    ```
    Objective: Streamline first-run onboarding to reduce drop-off.
    Subtasks: [Update copy]; [Shorten steps]; [Add skip]
    Acceptance Criteria: [≤ 2 steps]; [CTR +10%]; [Error-free]
    ```

사용자: yes

봇:
- 생성 완료: APP-123 https://youtrack.example.com/issue/APP-123

## 관련 파일
- 핸들러: `tulipee/handlers/youtrack_create.py`
- LLM 플로우/스키마: `tulipee/utils/llm.py`
- YouTrack 클라이언트: `tulipee/utils/youtrack.py`
- 대화 저장소: `tulipee/utils/conversation.py`
- 프로젝트 카탈로그: `tulipee/handlers/youtrack_projects.py`

## 참고
- 모델이 JSON Schema를 완벽히 지원하지 않아도, 파서가 안전 추출을 시도하고 실패 시 오류를 알려줍니다.
- 더 짧은 출력을 원하면 `tulipee/utils/llm.py`의 하드 리밋/템플릿을 조정하세요.
