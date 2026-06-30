# Hermes Agent Hub / WPS Software Requirements Specification v2.0

**Document Title:** Hermes Agent Hub — e2e Minimal Collector + Auth/API/CI Quality Gate Edition  
**Related Project:** WPS(Work Processing Stack)  
**Version:** v2.0 Draft  
**Baseline Replaced:** Hermes Agent Hub / WPS SRS v1.7 — e2e Minimal Collector + Testing & Quality Gate Edition  
**작성일:** 2026-06-26  
**상태:** Draft for Review / Codex Implementation Preparation  

---

## 1. 문서 목적

본 문서는 기존 WPS v1.5의 “Minimal Internal Messenger” 중심 요구사항을 재검토하고, v1.7 Draft에서 확인된 인증/API/품질 게이트 공백을 보완하여, 1단계 구현 목표를 **Hermes Agent Hub e2e Minimal Collector**로 재정의한 Software Requirements Specification이다.

v2.0의 핵심 목표는 v1.6에서 정의한 **Hermes Agent에서 발생하는 request / response / message / session 이벤트를 수집하고 관찰할 수 있는 최소 e2e 기반**을 유지하면서, 구현자가 바로 따를 수 있는 Agent 인증, Admin API, idempotency, GitHub Actions 기반 CI, 점진적 quality gate 기준을 명확히 하는 것이다.

이를 통해 다음 목적을 달성한다.

1. Hermes Agent가 실제로 어떤 요청과 응답을 생성하는지 관찰한다.
2. Hermes Agent의 request/response/message를 1차적으로 SQLite DB에 저장한다.
3. Admin 화면에서 Agent, 사용자, 기간, 키워드 기준으로 메시지를 검색하고 확인한다.
4. 수집된 데이터를 debugging, 사용패턴 분석, 향후 학습데이터 가공의 원천 데이터로 활용한다.
5. 향후 WPS의 보고 Chatroom, 업무지시, 완료확인, 회장 Agent 요약 기능을 구축하기 위한 기반을 마련한다.
6. GitHub Actions 기반 자동 테스트와 coverage 측정을 도입하되, 초기에는 차단보다 관찰과 개선을 우선한다.

---

## 2. 배경 및 변경 사유

### 2.1 기존 방향

v1.5에서는 WPS를 다음과 같이 정의하였다.

- 회장님 보고 전용 Report Chatroom
- 회장님 업무지시용 Instruction Chatroom
- Reporter / Chairman / Admin 권한 체계
- Hermes Agent와 연동되는 Minimal Internal Messenger

### 2.2 변경된 방향

추가 검토 결과, Hermes Agent와의 정확한 연동 방식이 아직 확정되지 않았고, Hermes Agent의 plugin, gateway, hook, session storage 구조를 먼저 파악하는 것이 더 중요하다고 판단하였다.

따라서 v1.6에서 우선순위를 다음과 같이 변경하였고, v1.7에서는 여기에 Testing & Quality Gate 요구사항을 추가하였다. v2.0에서는 v1.7 Review에서 발견된 인증/API/CI 정책 공백을 보완한다.

| 구분 | v1.5 | v1.6/v1.7 | v2.0 |
|---|---|---|---|
| 1차 목표 | Minimal Internal Messenger | Hermes Agent message 수집/관찰 | 구현 가능한 Minimal Collector 계약 확정 |
| 핵심 데이터 | Chatroom message | Hermes request/response/session/event | Hermes event + 인증/API/idempotency metadata |
| 주요 사용자 | Reporter, Chairman, Admin | Admin 중심 | Admin 중심 + Agent API principal |
| 화면 | Report Chatroom, Instruction Chatroom | Message Explorer, Agent Registry | Message/Event Explorer, Agent Registry |
| 업무지시 처리 | 일부 포함 | 후순위 | 후순위 |
| 완료확인 | 일부 포함 | 후순위 | 후순위 |
| Hermes 연동 | REST/API 전제 | Gateway/Hook/state.db/plugin 방식 검토 후 선택 | Gateway Hook 우선, state.db sync fallback |
| 품질 관리 | 명시 약함 | Testing & Quality Gate 추가 | GitHub Actions + 점진적 Quality Gate |

### 2.3 v1.6의 핵심 관점

v1.6은 업무처리 시스템이 아니라 **관측 시스템**이다.

> Hermes Agent Hub v1.6은 Hermes Agent의 request/response/message를 수집하여 SQLite에 저장하고, Admin이 이를 검색·필터링·확인할 수 있도록 하는 최소 e2e Collector 시스템이다.


### 2.4 v2.0 추가 변경 사항

v2.0에서는 v1.7의 Hermes Agent Hub e2e Minimal Collector 범위와 Testing & Quality Gate 방향은 유지하되, 실제 구현자가 API와 운영 정책을 일관되게 적용할 수 있도록 다음 사항을 보완한다.

v2.0의 추가 목적은 다음과 같다.

1. 기능 추가보다 코드 구조 검토와 refactoring을 우선한다.
2. 모든 기능 추가, 변경, bug fix 이후 자동화된 unit testing과 regression testing을 수행한다.
3. SQLite 연동 기능은 항상 독립적인 test database를 초기화한 후 검증한다.
4. Web UI는 Playwright 기반 smoke/regression testing 대상으로 관리한다.
5. pytest, pytest-cov 기반 coverage 기준을 명확히 한다.
6. Agent API 인증은 `Authorization: Bearer <api_token>` 방식을 기본으로 한다.
7. Admin API의 최소 계약을 명시하여 Agent 등록, token 발급, 매핑, 비활성화, 검색 기능 구현 기준을 고정한다.
8. message/event ingest는 idempotency key와 명시적 중복 처리 기준을 사용한다.
9. GitHub Actions를 기본 CI로 사용한다.
10. Quality Gate는 초기 개발 속도를 막는 hard block이 아니라, warning/report 기반으로 시작하여 점진적으로 목표 기준을 달성한다.


---

## 3. 참고한 Hermes Agent 구조 요약

본 문서는 Hermes Agent의 현재 공개 문서 구조를 기반으로 다음 사항을 전제로 한다.

### 3.1 Messaging Gateway

Hermes Agent는 Telegram, Discord, Slack, WhatsApp, Signal, Email, Mattermost, Matrix, Teams, LINE 등 다양한 플랫폼과 연결되는 Messaging Gateway를 제공한다. Gateway는 단일 background process로 동작하며, platform adapter가 메시지를 수신하고 per-chat session store를 통해 AIAgent로 dispatch하는 구조를 가진다.

### 3.2 Gateway Internals

Gateway 내부는 다음과 같은 구조를 가진다.

- `gateway/run.py`: GatewayRunner main loop, slash command, message dispatch
- `gateway/session.py`: SessionStore, conversation persistence
- `gateway/delivery.py`: outbound message delivery
- `gateway/hooks.py`: hook discovery, loading, lifecycle event dispatch
- `gateway/platforms/`: platform adapter

Gateway message flow는 platform adapter가 raw event를 `MessageEvent`로 normalize하고, `_handle_message()`를 통해 AIAgent 실행 및 response delivery로 이어지는 구조로 이해한다.

### 3.3 Session Storage

Hermes Agent는 `~/.hermes/state.db` SQLite DB를 사용하여 session metadata, full message history, model configuration을 저장한다. 주요 테이블은 `sessions`, `messages`, `messages_fts`, `messages_fts_trigram`, `state_meta`, `schema_version` 등이다.

### 3.4 Event Hooks

Hermes Agent는 Gateway hooks, Plugin hooks, Shell hooks를 제공한다. Gateway hooks는 `~/.hermes/hooks/<hook-name>/HOOK.yaml` 및 `handler.py` 방식으로 구성되며, `agent:start`, `agent:end`, `agent:step`, `command:*` 등의 이벤트를 구독할 수 있다.

---

## 4. v2.0 범위

### 4.1 In Scope

v2.0에서 구현해야 할 범위는 다음과 같다.

1. Hermes Agent Hub FastAPI 서버
2. SQLite 기반 Hub DB
3. Admin seed 계정
4. Agent 등록/인증 API
5. Agent heartbeat API
6. Message/Event ingest API
7. Hermes request/response/message raw payload 저장
8. Message normalization
9. Request/response pair 식별 구조
10. Admin Message Explorer 화면
11. Agent 목록 및 매핑 화면
12. 날짜 기반 검색
13. Agent / 사용자 / platform / message role / keyword 필터
14. JSON raw payload 상세보기
15. Export 후보 기능 정의
16. Hermes 연동 방식 검토 및 1차 연동 방식 선택 기준 문서화
17. Agent API token 인증 및 권한 처리
18. Admin API 최소 계약 정의 및 구현
19. Ingest idempotency 및 중복 방지 정책 구현
20. GitHub Actions 기반 CI workflow 도입
21. Coverage/quality report 기반 점진적 quality gate 운영

### 4.2 Out of Scope

v2.0에서 제외하거나 후순위로 두는 기능은 다음과 같다.

1. 범용 Messenger
2. Report Chatroom / Instruction Chatroom의 본격 구현
3. Kanban Board
4. Card / Stack 상태 관리
5. 업무지시 완료 확인 workflow
6. 회장님 보고 자동 요약
7. Daily Summary 자동 생성
8. A2A Protocol 구현
9. Hermes Gateway Platform Adapter 신규 개발
10. 학습데이터 자동 정제
11. 개인정보 자동 마스킹
12. Vector Search 기반 semantic search의 필수 구현

단, 위 항목은 v2.1 이후 확장 후보로 남긴다.

---

## 5. 개발 환경

### 5.1 기본 개발 환경

| 항목 | 요구사항 |
|---|---|
| Backend | Python 3.11+ |
| Web Framework | FastAPI |
| DB | SQLite |
| Vector Extension | sqlite-vec 선택 적용 |
| Frontend | Bootstrap 5 기반 반응형 Web |
| Template | Jinja2 |
| Realtime | v2.0에서는 필수 아님. 필요 시 SSE 확장 |
| ORM | SQLAlchemy 또는 SQLModel 중 선택 |
| Auth | Cookie Session 기반 Admin Login 우선 |
| Deployment | 사내망 단일 서버 우선 |

### 5.2 sqlite-vec 적용 원칙

v2.0에서는 sqlite-vec를 필수 기능으로 구현하지 않아도 된다. 다만 향후 다음 기능을 위해 DB 구조 및 코드 구조에서 확장 가능성을 열어둔다.

- 유사 message 검색
- request/response clustering
- 학습데이터 후보 검색
- 보고/업무지시 semantic search
- 유사 장애/질문 pattern 분석

---

## 6. 사용자 및 권한

### 6.1 v2.0 사용자 유형

v2.0은 Admin 중심 시스템이다.

| Role | 설명 |
|---|---|
| ADMIN | Hermes Agent Hub 관리자. 모든 Agent, message, event 조회 가능 |
| AGENT | Hermes Agent 또는 Collector. API를 통해 message/event 전송 |
| VIEWER | 선택 사항. 읽기 전용 관리자 후보 |

### 6.2 Admin seed 계정

초기 설치 시 Admin 계정은 DB에 사전 입력되어야 한다.

예시:

```text
email: admin@company.com
role: ADMIN
password: 초기 설정값 또는 환경변수 기반
```

구현 시 평문 password 저장은 금지한다. `password_hash`를 사용해야 한다.

---

## 7. Hermes Agent 연결 및 인증

### 7.1 기본 원칙

Hermes Agent가 처음 Hermes Agent Hub에 연결될 때는 다음 정보를 Hub에 전달해야 한다.

- agent_id 또는 임시 agent_key
- profile_name
- hostname
- IP address
- owner_email 후보
- source/platform
- enrollment token 또는 API token

### 7.2 1안: Enrollment Token 기반 자동 등록

Admin이 Hub에서 사용자 email 기준으로 enrollment token을 발급한다.  
Hermes Agent 또는 Collector는 최초 연결 시 해당 token을 사용한다.

```env
HERMES_HUB_URL=http://hub.local:8000
HERMES_HUB_ENROLL_TOKEN=wps_enroll_xxxxx
HERMES_PROFILE_NAME=kim-teamlead
```

Hub는 token을 검증한 뒤 agent를 해당 사용자 계정과 매핑한다.

### 7.3 2안: UNMAPPED 등록 후 Admin 승인

Enrollment token 없이 Agent가 접속하면 `UNMAPPED` 상태로 등록한다.  
Admin은 Agent 목록 화면에서 해당 Agent를 확인한 후 사용자 email과 수동 매핑한다.

명시적으로 잘못된 enrollment token이 전달된 경우에는 `UNMAPPED`로 등록하지 않고 `401 Unauthorized` 또는 `403 Forbidden`으로 거부한다. 이는 잘못된 설정 또는 무작위 token 시도를 정상 Agent 후보로 저장하지 않기 위함이다.

### 7.4 권장 방식

v2.0에서는 두 방식을 모두 고려하되, 구현 우선순위는 다음으로 한다.

1. Enrollment Token 기반 자동 등록
2. Enrollment Token 없는 Agent는 UNMAPPED로 등록
3. Admin 수동 매핑

### 7.5 Agent API Token 사용 원칙

Agent enrollment가 성공하면 Hub는 Agent 전용 `api_token`을 1회 반환한다. Hub DB에는 token 원문을 저장하지 않고 `token_hash`만 저장한다.

Agent 또는 Collector는 enrollment 이후 모든 heartbeat, message ingest, event ingest 요청에 다음 HTTP header를 포함해야 한다.

```http
Authorization: Bearer hub_api_xxxxx
```

Token scope는 다음 기준을 따른다.

| Agent 상태 | 허용 API | 제한 API |
|---|---|---|
| ACTIVE | heartbeat, message ingest, event ingest | 없음 |
| UNMAPPED | heartbeat | message ingest, event ingest |
| DISABLED | 없음 | 모든 Agent API |

UNMAPPED Agent에는 제한된 API token을 발급할 수 있다. 이 token은 Admin이 Agent를 확인하고 매핑할 때까지 heartbeat 외 ingest 기능에는 사용할 수 없다.

Admin이 UNMAPPED Agent를 사용자 email과 매핑하면 해당 Agent의 기존 API token scope는
`AGENT_UNMAPPED`에서 `AGENT_ACTIVE`로 갱신한다. 이때 Agent는 새로운 token을 다시
발급받지 않고 기존 token으로 message/event ingest를 수행할 수 있다.

Admin이 Agent를 `DISABLED`로 전환하면 Agent 상태가 우선 적용되어 해당 Agent의 모든
Agent API 호출은 `403 Forbidden`으로 거부된다. 구현은 Agent 상태만으로 거부해도 되며,
운영 정책상 필요한 경우 연결된 API token의 `is_active`를 함께 false로 전환할 수 있다.

---

## 8. Hermes Agent 연동 방식 검토

### 8.1 후보 1: Gateway Event Hook 방식

Hermes Gateway Hook을 사용하여 `agent:start`, `agent:end`, `agent:step`, `command:*` 이벤트를 Hub로 전송한다.

#### 장점

- Hermes core source 수정 없음
- Gateway 메시지 흐름에 자연스럽게 연결 가능
- request/response 수집 목적에 적합
- HTTP POST 방식으로 Hub ingest API와 연결 가능

#### 단점

- Gateway 환경에서만 hook이 동작
- CLI 단독 사용까지 모두 포착하려면 Plugin Hook 또는 state.db sync가 추가 필요

#### v2.0 평가

1차 연동 후보로 가장 적합하다.

---

### 8.2 후보 2: Hermes `state.db` read-only sync 방식

Hermes의 `~/.hermes/state.db`를 read-only 방식으로 읽어 Hub로 동기화한다.

#### 장점

- Hermes core 수정 없음
- Hermes가 이미 저장한 session/message 전체를 수집 가능
- CLI와 Gateway session 모두 수집 가능할 가능성 있음

#### 단점

- 내부 DB schema 변경에 취약
- 실시간성이 낮음
- 각 Agent PC에 collector process 필요
- DB lock/WAL 처리 주의 필요

#### v2.0 평가

Fallback 또는 보완 방식으로 적합하다.

---

### 8.3 후보 3: Plugin Hook 방식

Hermes plugin hook을 사용하여 pre/post LLM call, pre/post tool call, session start/end 등을 수집한다.

#### 장점

- 세밀한 lifecycle 정보 수집 가능
- tool call, LLM call, session 이벤트 수집에 유리
- 학습데이터 가공 단계에 적합

#### 단점

- plugin 구조 이해와 설치가 필요
- 초기 e2e에서는 구현 부담이 상대적으로 큼

#### v2.0 평가

2단계 확장 후보로 유지한다.

---

### 8.4 후보 4: Webhook Adapter 방식

Hermes Webhook Adapter는 외부 시스템이 Hermes Gateway로 이벤트를 전달하는 데 적합하다.

#### 장점

- Hub → Hermes 방향 이벤트 전달에 적합
- 보고 요약 또는 지시 전달 단계에서 활용 가능

#### 단점

- Hermes → Hub 방향 message capture에는 직접적이지 않음

#### v2.0 평가

v2.0 message capture보다는 v2.1 이후 Hub-to-Hermes notification에 적합하다.

---

### 8.5 v2.0 연동 전략

v2.0에서는 다음 순서로 접근한다.

1. Hermes Gateway Hook 방식이 설정만으로 가능한지 우선 검증한다.
2. 실제 Gateway Hook handler를 작성하기 전에 Hub ingest payload contract를 smoke client로 검증한다.
3. Gateway Hook 방식이 어렵거나 누락이 크면 state.db read-only sync collector를 병행한다.
4. 그래도 부족하면 Hermes Agent 소스의 gateway hook 또는 platform adapter 부분을 최소 수정한다.
5. Plugin Hook 및 전용 WPS Adapter 개발은 후순위로 둔다.

### 8.6 Hermes Integration Smoke Client

실제 Hermes Agent 연동 전에는 smoke client로 Hub API 계약을 먼저 검증한다.

Smoke client는 다음 순서로 Hub API를 호출한다.

1. `POST /api/v1/agents/heartbeat`
2. `POST /api/v1/messages/ingest` request message
3. `POST /api/v1/messages/ingest` response message
4. `POST /api/v1/events/ingest`

response message는 request message 저장 결과의 `message_id`를 `parent_message_id`로 전달하여
Message Detail의 request/response pair 계약을 함께 검증한다.

필수 환경 변수:

- `HERMES_HUB_URL`
- `HERMES_AGENT_UID`
- `HERMES_API_TOKEN`

선택 환경 변수:

- `HERMES_SMOKE_PROFILE_NAME`
- `HERMES_SMOKE_HOSTNAME`
- `HERMES_SMOKE_IP_ADDR`
- `HERMES_SMOKE_SOURCE`
- `HERMES_SMOKE_SESSION_KEY`
- `HERMES_SMOKE_REQUEST_ID`

`--dry-run`은 HTTP 전송 없이 payload만 출력하여 실제 Hermes Hook mapping을 조정할 때 사용한다.

### 8.7 Hermes Gateway Hook Handler PoC

Gateway Hook Handler PoC는 Hermes Gateway hook JSON을 Hub ingest API payload로 변환한다.

초기 handler는 다음 원칙을 따른다.

- `agent:start`, `agent:end`는 message ingest와 event ingest를 모두 생성한다.
- `agent:step`, `command:*` 등 기타 lifecycle hook은 event ingest로 저장한다.
- `request_id`, `session_key`, `source`, `content`는 Hermes payload의 여러 후보 field에서 느슨하게 추출한다.
- 원본 hook JSON은 항상 `raw_payload.hook_payload`에 보존한다.
- `parent_message_id`는 Hub 내부 message id로 전달된 경우에만 사용하고, 외부 parent id는 실제 payload 확인 후 별도 field로 보완한다.

Handler PoC는 `--dry-run`으로 mapping 결과만 출력할 수 있어야 하며, 실제 Gateway runtime 연결 전
sample payload를 사용해 Hub payload 계약을 검토하는 데 사용한다.

---

## 9. 주요 데이터 모델

### 9.1 users

관리자 및 향후 사용자 계정 테이블.

| Column | Type | 설명 |
|---|---|---|
| id | INTEGER PK | 내부 사용자 ID |
| email | TEXT UNIQUE | 회사 email 계정 |
| name | TEXT | 사용자 이름 |
| role | TEXT | ADMIN / VIEWER 등 |
| password_hash | TEXT | password hash |
| is_active | INTEGER | 활성 여부 |
| created_at | DATETIME | 생성일 |
| updated_at | DATETIME | 수정일 |

---

### 9.2 hermes_agents

Hub에 등록된 Hermes Agent 목록.

| Column | Type | 설명 |
|---|---|---|
| id | INTEGER PK | 내부 Agent ID |
| agent_uid | TEXT UNIQUE | Hub 기준 Agent UID |
| profile_name | TEXT | Hermes profile name |
| display_name | TEXT | Admin이 지정한 표시 이름 |
| owner_email | TEXT | 매핑된 사용자 email |
| hostname | TEXT | Agent PC hostname |
| ip_addr | TEXT | 최근 접속 IP |
| source | TEXT | Agent 연결 source. 예: gateway / collector |
| status | TEXT | ACTIVE / UNMAPPED / DISABLED |
| last_heartbeat_status | TEXT NULL | 마지막 heartbeat runtime status. 예: running / idle |
| last_seen_at | DATETIME | 최종 접속 시간 |
| created_at | DATETIME | 최초 등록 시간 |
| updated_at | DATETIME | 수정 시간 |

---

### 9.3 agent_tokens

Agent 등록 및 API 호출을 위한 token 관리 테이블.

| Column | Type | 설명 |
|---|---|---|
| id | INTEGER PK | token ID |
| token_hash | TEXT UNIQUE | token hash |
| token_type | TEXT | ENROLLMENT / API |
| scope | TEXT | ENROLL_AGENT / AGENT_ACTIVE / AGENT_UNMAPPED |
| owner_email | TEXT NULL | 대상 email. UNMAPPED API token은 NULL 가능 |
| agent_id | INTEGER NULL | 연결된 Agent |
| expires_at | DATETIME NULL | 만료일 |
| used_at | DATETIME NULL | 사용일 |
| is_active | INTEGER | 활성 여부 |
| created_at | DATETIME | 생성일 |
| updated_at | DATETIME | 수정일 |

---

### 9.4 agent_sessions

Hermes session 단위 정보.

| Column | Type | 설명 |
|---|---|---|
| id | INTEGER PK | 내부 session ID |
| agent_id | INTEGER FK | Hermes Agent ID |
| hermes_session_id | TEXT | Hermes session key/id |
| source | TEXT | cli / telegram / discord / slack / gateway 등 |
| chat_type | TEXT | private / group / thread 등 |
| chat_id | TEXT | 원본 chat id |
| model | TEXT | 사용 model |
| started_at | DATETIME | 시작일 |
| ended_at | DATETIME NULL | 종료일 |
| raw_payload | TEXT | 원본 session payload JSON |

---

### 9.5 agent_messages

수집된 request/response/message 본문.

| Column | Type | 설명 |
|---|---|---|
| id | INTEGER PK | 내부 message ID |
| agent_id | INTEGER FK | Hermes Agent ID |
| session_id | INTEGER FK NULL | Hub session ID |
| external_message_id | TEXT NULL | Hermes 원본 message id |
| idempotency_key | TEXT NULL | 재전송 중복 방지용 key |
| direction | TEXT | INBOUND / OUTBOUND / INTERNAL |
| role | TEXT | user / assistant / tool / system |
| event_type | TEXT | agent:start / agent:end / message / command 등 |
| content | TEXT | 메시지 본문 |
| content_hash | TEXT | 중복 방지용 hash |
| source | TEXT | cli / telegram / discord / slack 등 |
| request_id | TEXT NULL | request/response pair 식별 ID |
| parent_message_id | INTEGER NULL | pair 또는 thread 연결 |
| tool_name | TEXT NULL | tool call name |
| tool_calls_json | TEXT NULL | tool call JSON |
| raw_payload | TEXT | 원본 payload JSON |
| created_at | DATETIME | Hub 수신 시간 |
| occurred_at | DATETIME NULL | 원본 발생 시간 |

---

### 9.6 agent_events

message 외 lifecycle event 저장.

| Column | Type | 설명 |
|---|---|---|
| id | INTEGER PK | event ID |
| agent_id | INTEGER FK | Hermes Agent ID |
| event_type | TEXT | agent:start / agent:end / agent:step / command:* 등 |
| severity | TEXT | INFO / WARN / ERROR |
| summary | TEXT | 이벤트 요약 |
| raw_payload | TEXT | 원본 payload JSON |
| occurred_at | DATETIME NULL | 원본 발생 시간 |
| created_at | DATETIME | Hub 저장 시간 |

---

### 9.7 audit_logs

Admin 및 시스템 변경 이력.

| Column | Type | 설명 |
|---|---|---|
| id | INTEGER PK | audit ID |
| actor_user_id | INTEGER NULL | 수행 사용자 |
| action | TEXT | LOGIN / MAP_AGENT / DISABLE_AGENT 등 |
| target_type | TEXT | USER / AGENT / TOKEN / MESSAGE 등 |
| target_id | TEXT | 대상 ID |
| detail_json | TEXT | 상세 JSON |
| created_at | DATETIME | 생성일 |

---

### 9.8 주요 제약 조건 및 Index

v2.0 구현 시 다음 제약 조건과 index를 우선 적용한다.

| 대상 | 제약/Index | 목적 |
|---|---|---|
| users | UNIQUE(email) | 동일 email 계정 중복 방지 |
| hermes_agents | UNIQUE(agent_uid) | Hub Agent 식별자 중복 방지 |
| agent_tokens | UNIQUE(token_hash) | token 재사용/중복 방지 |
| agent_sessions | UNIQUE(agent_id, source, hermes_session_id) | 동일 Hermes session 중복 방지 |
| agent_messages | UNIQUE(agent_id, source, external_message_id) WHERE external_message_id IS NOT NULL | 외부 message id 기반 중복 방지 |
| agent_messages | UNIQUE(agent_id, idempotency_key) WHERE idempotency_key IS NOT NULL | 재전송 idempotency 보장 |
| agent_messages | INDEX(agent_id, occurred_at) | Agent별 날짜 검색 |
| agent_messages | INDEX(source, role, event_type) | Message Explorer filter |
| agent_messages | INDEX(request_id) | request/response pair 조회 |
| agent_events | INDEX(agent_id, occurred_at, event_type) | Event Explorer 검색 |

`content_hash`는 중복 후보 탐지와 fallback 비교에 사용한다. 같은 사용자가 같은 문장을 여러 번 보낼 수 있으므로 `content_hash` 단독 unique constraint는 사용하지 않는다.

---

## 10. API 요구사항

### 10.0 공통 API 인증 및 응답 원칙

API 인증은 Admin Web/API와 Agent API를 분리한다.

| API 영역 | 인증 방식 | 설명 |
|---|---|---|
| Admin Web/API | Cookie Session | `/auth/login` 성공 후 server-side session 또는 signed cookie 사용 |
| Agent API | Bearer Token | `Authorization: Bearer <api_token>` header 사용 |
| Enrollment API | Enrollment Token | 최초 등록용 token. Bearer token은 아직 없음 |

Agent API 공통 header:

```http
Authorization: Bearer hub_api_xxxxx
Content-Type: application/json
```

공통 오류 응답:

| HTTP Status | 사용 조건 |
|---:|---|
| 400 | request body 또는 query parameter가 malformed인 경우 |
| 401 | 인증 정보가 없거나 token이 유효하지 않은 경우 |
| 403 | 인증은 되었지만 Agent 상태/scope상 허용되지 않는 경우 |
| 404 | 대상 Agent, message, event가 존재하지 않는 경우 |
| 409 | idempotency 또는 unique constraint 충돌이 발생한 경우 |
| 422 | validation은 통과했으나 domain rule을 만족하지 못한 경우 |

---

### 10.1 Admin Auth API

#### POST `/auth/login`

Admin login.

Request:

```json
{
  "email": "admin@company.com",
  "password": "password"
}
```

Response:

```json
{
  "ok": true,
  "role": "ADMIN"
}
```

### 10.2 Admin Agent Token API

#### POST `/admin/api/agent-tokens`

Admin이 특정 owner email 기준으로 enrollment token을 발급한다.

Request:

```json
{
  "owner_email": "kim@company.com",
  "expires_at": "2026-07-25T23:59:59+09:00"
}
```

Response:

```json
{
  "ok": true,
  "token": "wps_enroll_xxxxx",
  "token_type": "ENROLLMENT",
  "owner_email": "kim@company.com",
  "expires_at": "2026-07-25T23:59:59+09:00"
}
```

Token 원문은 이 응답에서만 노출한다. DB에는 `token_hash`만 저장한다.

---

### 10.3 Agent Enrollment API

#### POST `/api/v1/agents/enroll`

Hermes Agent 또는 Collector가 최초 등록을 요청한다.

Request:

```json
{
  "enrollment_token": "wps_enroll_xxxxx",
  "profile_name": "kim-teamlead",
  "hostname": "KIM-PC",
  "ip_addr": "192.168.0.25",
  "source": "gateway"
}
```

Response:

```json
{
  "agent_uid": "agent_20260625_0001",
  "api_token": "hub_api_xxxxx",
  "status": "ACTIVE",
  "scope": "AGENT_ACTIVE"
}
```

Enrollment token이 없으면 `UNMAPPED` 상태로 등록될 수 있다.

UNMAPPED Response:

```json
{
  "agent_uid": "agent_20260625_0002",
  "api_token": "hub_api_limited_xxxxx",
  "status": "UNMAPPED",
  "scope": "AGENT_UNMAPPED"
}
```

명시적으로 잘못된 enrollment token이 전달되면 `401 Unauthorized`로 거부한다.

---

### 10.4 Agent Heartbeat API

#### POST `/api/v1/agents/heartbeat`

Agent의 생존 상태를 Hub에 전송한다.

Required header:

```http
Authorization: Bearer hub_api_xxxxx
```

Request:

```json
{
  "agent_uid": "agent_20260625_0001",
  "profile_name": "kim-teamlead",
  "source": "gateway",
  "ip_addr": "192.168.0.25",
  "runtime_status": "running"
}
```

`runtime_status`는 Agent lifecycle 상태인 `ACTIVE / UNMAPPED / DISABLED`와 구분되는 heartbeat 시점의 실행 상태이다.

Response:

```json
{
  "ok": true,
  "agent_uid": "agent_20260625_0001",
  "last_seen_at": "2026-06-25T09:30:10+09:00"
}
```

---

### 10.5 Message Ingest API

#### POST `/api/v1/messages/ingest`

Hermes request/response/message를 Hub에 저장한다.

Required header:

```http
Authorization: Bearer hub_api_xxxxx
Idempotency-Key: msg_agent_20260625_0001_req_abc123_user_001
```

`Idempotency-Key` header는 권장 사항이며, request body의 `idempotency_key`로도 전달할 수 있다. 둘 다 전달되면 header 값을 우선한다.
저장 시에도 header 값이 effective `agent_messages.idempotency_key`가 된다.

`session_key`는 Hub DB의 `agent_sessions.hermes_session_id`로 저장한다. Hub는
`(agent_id, source, session_key)` 조합으로 기존 session을 조회하고, 없으면 새
`agent_sessions` row를 생성한 뒤 `agent_messages.session_id`에 연결한다.

`parent_message_id`는 Hub 내부 parent message id를 알고 있을 때만 전달하는 optional
field이다. Hermes 연동 후 외부 message id 기반 parent 관계가 필요하면 별도 field로
보완한다.

Request:

```json
{
  "agent_uid": "agent_20260625_0001",
  "idempotency_key": "msg_agent_20260625_0001_req_abc123_user_001",
  "external_message_id": "telegram_123456789_100",
  "event_type": "agent:start",
  "source": "telegram",
  "session_key": "agent:main:telegram:private:123456789",
  "direction": "INBOUND",
  "role": "user",
  "content": "오늘 작업 내용을 정리해줘",
  "request_id": "req_abc123",
  "parent_message_id": null,
  "occurred_at": "2026-06-25T09:30:00+09:00",
  "raw_payload": {}
}
```

Response:

```json
{
  "ok": true,
  "message_id": 1001,
  "duplicate": false
}
```

동일 `idempotency_key` 또는 동일 `external_message_id`가 재전송되면 기존 message를 반환한다.

Duplicate Response:

```json
{
  "ok": true,
  "message_id": 1001,
  "duplicate": true
}
```

UNMAPPED 또는 DISABLED Agent의 message ingest 요청은 `403 Forbidden`으로 거부한다.

---

### 10.6 Event Ingest API

#### POST `/api/v1/events/ingest`

Lifecycle event를 Hub에 저장한다.

Required header:

```http
Authorization: Bearer hub_api_xxxxx
```

Request:

```json
{
  "agent_uid": "agent_20260625_0001",
  "event_type": "agent:end",
  "severity": "INFO",
  "summary": "Agent response completed",
  "occurred_at": "2026-06-25T09:31:15+09:00",
  "raw_payload": {}
}
```

Response:

```json
{
  "ok": true,
  "event_id": 501
}
```

UNMAPPED 또는 DISABLED Agent의 event ingest 요청은 `403 Forbidden`으로 거부한다.

---

### 10.7 Admin Agent Registry API

#### GET `/admin/api/agents`

Admin Agent Registry 화면에서 Agent 목록을 조회한다.

Query:

- `status`
- `owner_email`
- `source`
- `keyword`
- `limit`
- `offset`

Response:

```json
{
  "items": [
    {
      "agent_uid": "agent_20260625_0001",
      "profile_name": "kim-teamlead",
      "display_name": "Kim Team Lead Agent",
      "owner_email": "kim@company.com",
      "hostname": "KIM-PC",
      "ip_addr": "192.168.0.25",
      "source": "gateway",
      "status": "ACTIVE",
      "last_seen_at": "2026-06-25T09:30:10+09:00"
    }
  ],
  "total": 1
}
```

#### PATCH `/admin/api/agents/{agent_uid}`

Agent 표시 이름을 수정한다. 사용자 email 매핑과 status 변경은 audit 의미가 분명하도록
각각 `map`, `disable` 전용 API로 처리한다.

Request:

```json
{
  "display_name": "Kim Team Lead Agent"
}
```

#### POST `/admin/api/agents/{agent_uid}/map`

UNMAPPED Agent를 사용자 email에 매핑하고 상태를 `ACTIVE`로 전환한다.
연결된 API token scope는 `AGENT_ACTIVE`로 갱신한다.

Request:

```json
{
  "owner_email": "kim@company.com"
}
```

#### POST `/admin/api/agents/{agent_uid}/disable`

Agent를 `DISABLED` 상태로 전환하고 이후 Agent API 호출을 거부한다.
Agent 상태가 `DISABLED`이면 token 자체가 active 상태여도 heartbeat, message ingest,
event ingest는 모두 `403 Forbidden`으로 거부되어야 한다.

---

### 10.8 Admin Message Search API

#### GET `/admin/api/messages`

검색 조건:

- `date_from`
- `date_to`
- `agent_uid`
- `owner_email`
- `source`
- `role`
- `event_type`
- `keyword`
- `limit`
- `offset`

Response:

```json
{
  "items": [
    {
      "id": 1001,
      "occurred_at": "2026-06-25T09:30:00+09:00",
      "agent_uid": "agent_20260625_0001",
      "profile_name": "kim-teamlead",
      "owner_email": "kim@company.com",
      "source": "telegram",
      "role": "user",
      "event_type": "agent:start",
      "content_preview": "오늘 작업 내용을 정리해줘"
    }
  ],
  "total": 1
}
```

#### GET `/admin/api/messages/{message_id}`

Message 상세 화면에서 본문, raw payload, session, request/response pair, tool call 정보를 조회한다.

Request/Response pair 연결 규칙:

- `request_id`가 있으면 동일 Agent의 같은 `request_id`를 가진 message를 같은 pair 후보로 본다.
- `parent_message_id`가 있으면 해당 Hub message id를 직접 parent 후보로 본다.
- 현재 message를 `parent_message_id`로 참조하는 message는 직접 child 후보로 본다.
- Detail response의 `related_messages`는 현재 message를 제외하고, 위 후보를 중복 제거한 뒤 발생 시간 오름차순으로 반환한다.
- 실제 Hermes 연동 후 외부 parent id 형식이 확인되면 별도 external parent field 추가를 검토한다.

Response:

```json
{
  "id": 1001,
  "agent_uid": "agent_20260625_0001",
  "session_key": "agent:main:telegram:private:123456789",
  "request_id": "req_abc123",
  "parent_message_id": null,
  "role": "user",
  "direction": "INBOUND",
  "content": "오늘 작업 내용을 정리해줘",
  "tool_calls_json": null,
  "raw_payload": {},
  "related_messages": [
    {
      "id": 1002,
      "occurred_at": "2026-06-25T09:30:10+09:00",
      "request_id": "req_abc123",
      "parent_message_id": 1001,
      "role": "assistant",
      "direction": "OUTBOUND",
      "event_type": "agent:end",
      "content_preview": "정리 결과입니다"
    }
  ]
}
```

---

### 10.9 Admin Event Search API

#### GET `/admin/api/events`

Event Explorer 화면에서 lifecycle event를 검색한다.

검색 조건:

- `date_from`
- `date_to`
- `agent_uid`
- `severity`
- `event_type`
- `keyword`
- `limit`
- `offset`

Response:

```json
{
  "items": [
    {
      "id": 501,
      "occurred_at": "2026-06-25T09:31:15+09:00",
      "agent_uid": "agent_20260625_0001",
      "event_type": "agent:end",
      "severity": "INFO",
      "summary": "Agent response completed"
    }
  ],
  "total": 1
}
```

#### GET `/admin/api/events/{event_id}`

Event 상세 화면에서 lifecycle event 원문과 Agent 식별 정보를 조회한다.

Response:

```json
{
  "id": 501,
  "occurred_at": "2026-06-25T09:31:15+09:00",
  "agent_uid": "agent_20260625_0001",
  "profile_name": "kim-teamlead",
  "owner_email": "kim@company.com",
  "event_type": "agent:end",
  "severity": "INFO",
  "summary": "Agent response completed",
  "raw_payload": {
    "duration_ms": 1200
  }
}
```

---

### 10.10 Admin Dashboard Summary API

#### GET `/admin/api/dashboard/summary`

Admin Dashboard 첫 화면에서 필요한 운영 요약 지표를 조회한다.

집계 기준:

- 모든 시간 기준은 UTC calendar day와 UTC 현재 시각을 기준으로 한다.
- `messages_today_count`는 `occurred_at`이 오늘 UTC 00:00 이상, 내일 UTC 00:00 미만인 message 수이다.
- `events_last_24h_count`는 현재 시각 기준 최근 24시간 이내 event 수이다.
- `error_events_last_24h_count`는 최근 24시간 이내 event 중 `severity = "ERROR"`인 event 수이다.
- `occurred_at`이 없는 message/event는 시간 범위 집계에서 제외한다.

Response:

```json
{
  "total_agent_count": 10,
  "active_agent_count": 7,
  "unmapped_agent_count": 2,
  "messages_today_count": 34,
  "events_last_24h_count": 12,
  "error_events_last_24h_count": 1
}
```

---

## 11. 화면 요구사항

### 11.1 Login 화면

- Admin email 입력
- Password 입력
- Login button
- 오류 메시지 표시
- 반응형 Web

### 11.2 Admin Dashboard

Admin Dashboard는 다음 정보를 요약한다.

- 등록 Agent 수
- ACTIVE Agent 수
- UNMAPPED Agent 수
- 오늘 수집 message 수
- 최근 24시간 event 수
- 오류 event 수

v2.0 초기 Admin Web Shell은 `/admin/login`과 `/admin/dashboard`를 우선 제공한다.
Dashboard 첫 화면은 기존 Admin session cookie를 사용해 `/admin/api/me`와
`/admin/api/dashboard/summary`를 조회하며, 인증되지 않은 사용자는 login 화면으로 이동한다.
초기 화면은 Dashboard 요약 지표를 보여주는 데 집중하고, Agent Registry / Message Explorer /
Event Explorer는 이후 slice에서 같은 shell navigation 안에 확장한다.

### 11.3 Agent Registry 화면

Agent 목록은 다음 필드를 표시한다.

- No
- Agent UID
- Profile Name
- Display Name
- Owner Email
- Hostname
- IP Addr
- Status
- Last Seen
- Actions

Actions:

- 사용자 매핑
- 표시 이름 변경
- Agent 비활성화
- 상세 보기

v2.0 초기 Agent Registry Web View는 `/admin/agents`에서 제공한다. 화면은
`/admin/api/agents`를 사용해 status, owner email, source, keyword 필터를 적용하며,
각 row에서 display name 수정, owner email mapping, disable action을 수행할 수 있어야 한다.
상세 보기는 이후 slice에서 확장한다.

### 11.4 Message Explorer 화면

Admin은 수집된 message를 검색하고 확인할 수 있어야 한다.

검색 조건:

- 날짜 범위
- Agent
- Owner Email
- Source/Platform
- Role
- Event Type
- Keyword

목록 표시 항목:

- 발생 시간
- Agent
- Owner Email
- Source
- Role
- Event Type
- Content Preview

상세 화면:

- Message 본문
- Raw Payload JSON
- Session 정보
- Request/Response 연결 정보
- Tool Call 정보
- Event 정보

### 11.5 Event Explorer 화면

agent lifecycle event를 조회한다.

표시 항목:

- 발생 시간
- Agent
- Event Type
- Severity
- Summary
- Raw Payload

---

## 12. 기능 요구사항

### FR-001 Admin 계정 초기 생성

시스템 최초 실행 시 Admin 계정이 seed data로 생성되어야 한다.

### FR-002 Admin 로그인

Admin은 email/password로 로그인할 수 있어야 한다.

### FR-003 Agent Enrollment Token 발급

Admin은 특정 email 기준으로 Agent enrollment token을 발급할 수 있어야 한다.

### FR-004 Agent 최초 등록

Hermes Agent 또는 Collector는 Hub에 최초 등록할 수 있어야 한다.

### FR-005 UNMAPPED Agent 등록

Enrollment token 없이 접근한 Agent는 UNMAPPED 상태로 등록될 수 있어야 한다. 명시적으로 잘못된 token을 전달한 요청은 UNMAPPED로 저장하지 않고 인증 오류로 거부해야 한다.

### FR-006 Agent-User 매핑

Admin은 UNMAPPED Agent를 사용자 email과 매핑할 수 있어야 한다.

### FR-007 Agent Heartbeat 저장

Agent는 Bearer API token으로 인증한 뒤 주기적으로 heartbeat를 전송하고 Hub는 `last_seen_at`을 갱신해야 한다.

### FR-008 Message Ingest

Hub는 ACTIVE Agent에서 발생한 request/response/message를 Bearer API token 인증 후 수신하여 DB에 저장해야 한다.

### FR-009 Raw Payload 저장

모든 ingest message/event는 원본 payload JSON을 저장해야 한다.

### FR-010 Normalized Field 저장

검색 및 필터링을 위해 source, role, event_type, content, occurred_at 등 normalized field를 저장해야 한다.

### FR-011 중복 Message 방지

동일 `idempotency_key` 또는 동일 `external_message_id` 기준으로 중복 저장을 방지할 수 있어야 한다. `content_hash`는 중복 후보 탐지용으로만 사용한다.

### FR-012 Request/Response Pair 연결

가능한 경우 request_id, parent_message_id 등을 사용하여 request와 response를 연결해야 한다.
초기 구현은 Hub 내부 message id 기반 `parent_message_id`와 동일 Agent의 `request_id`를 사용하며,
Hermes 실제 연동 결과에 따라 external parent id 또는 platform thread id를 후속 field로 보완할 수 있어야 한다.

### FR-013 Admin Message Search

Admin은 날짜, Agent, 사용자, source, role, keyword 기준으로 message를 검색할 수 있어야 한다.

### FR-014 Message Detail View

Admin은 message 상세와 raw JSON payload를 확인할 수 있어야 한다.

### FR-015 Event Search

Admin은 lifecycle event를 검색할 수 있어야 한다.

### FR-016 Export 후보

v2.0에서는 필수는 아니지만, message 검색 결과를 JSON 또는 CSV로 export할 수 있는 구조를 고려해야 한다.

### FR-017 Hermes 연동 방식 선택

개발 초기에 Gateway Hook, state.db sync, Plugin Hook 중 최소 1개 방식으로 e2e message 수집 PoC를 수행해야 한다.
실제 Gateway Hook 작성 전에는 smoke client로 heartbeat, request/response message, lifecycle event payload 계약을 검증할 수 있어야 한다.
Gateway Hook Handler PoC는 Hermes hook payload를 Hub message/event ingest payload로 변환하고 원본 payload를 보존할 수 있어야 한다.

### FR-018 Admin Agent 관리 API

Admin은 API를 통해 Agent 목록 조회, 표시 이름 변경, 사용자 email 매핑, Agent 비활성화를 수행할 수 있어야 한다.

### FR-019 Admin Message/Event Detail API

Admin은 message/event 검색 결과에서 상세 API를 통해 raw payload를 확인할 수 있어야 한다.
Message 상세는 session, request/response pair, tool call 정보를 함께 제공하고, Event 상세는
lifecycle event 원문과 Agent 식별 정보를 제공해야 한다.

### FR-020 Admin Dashboard Summary API

Admin은 Dashboard 첫 화면에서 Agent 상태, 당일 message 수, 최근 event/error event 수를 요약 조회할 수 있어야 한다.

### FR-021 GitHub Actions CI

GitHub push 또는 pull request 발생 시 GitHub Actions에서 unit/regression/API smoke test와 coverage 측정을 수행할 수 있어야 한다.

---

## 13. 비기능 요구사항

### NFR-001 단순성

v2.0은 minimal e2e 구현을 목표로 하며, 업무처리 기능보다 message 수집/조회 기능을 우선한다.

### NFR-002 보안

- Admin password는 hash로 저장한다.
- Agent API token은 평문 저장하지 않고 hash 저장을 필수로 한다.
- API token이 없는 ingest 요청은 거부해야 한다.
- UNMAPPED 등록은 허용하더라도 message/event ingest는 거부해야 한다.
- 명시적으로 잘못된 enrollment token은 UNMAPPED로 저장하지 않고 인증 오류로 처리해야 한다.

### NFR-003 성능

- SQLite 기준 10만 건 수준의 message 검색을 초기 목표로 한다.
- 날짜 범위, agent_id, source, role, event_type에 index를 생성한다.
- keyword 검색은 SQLite FTS 또는 단순 LIKE에서 시작할 수 있다.

### NFR-004 신뢰성

- Hermes Hook 또는 Collector 전송 실패 시 로컬 임시 파일에 retry queue를 둘 수 있어야 한다.
- Hub API는 동일 message 재전송 시 `idempotency_key` 또는 `external_message_id` 기준으로 idempotent하게 처리할 수 있어야 한다.

### NFR-005 CI 및 Quality Gate

- GitHub Actions를 기본 CI로 사용한다.
- CI는 pytest unit/regression/API smoke test와 pytest-cov coverage 측정을 수행한다.
- Web UI 변경이 포함된 경우 Playwright smoke test를 CI 또는 local smoke test로 수행하고 결과를 기록한다.
- 초기 v2.0 단계에서는 coverage 미달이나 일부 non-critical smoke test 실패를 commit/push hard block으로 사용하지 않는다.
- 실패한 테스트와 coverage 미달은 GitHub Actions summary, commit note, issue, 또는 작업 로그에 명시하고 점진적으로 해소한다.
- 안정화 이후 main branch 보호 또는 required check 적용 여부를 별도 결정한다.

### NFR-006 확장성

향후 다음 기능으로 확장 가능해야 한다.

- Report Chatroom
- Instruction Chatroom
- 업무지시 Work Item
- 완료 보고
- 회장님 확인
- Daily Summary
- 학습데이터 정제
- sqlite-vec semantic search
- Hermes Gateway WPS Adapter

### NFR-007 개인정보/민감정보

수집 데이터에는 업무상 민감정보가 포함될 수 있다. v2.0에서는 자동 마스킹이 필수는 아니지만, 향후 데이터 export 및 학습데이터 가공 단계에서 masking pipeline을 추가할 수 있어야 한다.

---

## 14. Hermes Agent 이름/식별 정보 요구사항

Hermes Agent Hub는 Agent를 식별하기 위해 다음 정보를 관리해야 한다.

| 항목 | 설명 |
|---|---|
| agent_uid | Hub에서 발급한 고유 Agent ID |
| profile_name | Hermes profile name |
| display_name | Admin이 지정한 표시 이름 |
| owner_email | 사용자 email |
| hostname | 실행 Host |
| ip_addr | 최근 접속 IP |
| source | cli / telegram / discord / slack / gateway 등 |
| last_seen_at | 최종 접속 시각 |

Hermes profile 또는 SOUL.md 기반 이름 설정이 가능할 경우, 해당 값을 수집하여 `profile_name` 또는 `display_name`으로 활용한다.

---

## 15. WPS / A2A / Hermes Agent Hub 관계

### 15.1 A2A와의 차이

A2A는 Agent 간 요청과 응답을 직접 처리하는 Agent-to-Agent protocol이다.  
반면 WPS는 장기적으로 Human-in-the-loop 업무처리 체계가 필요하다.

예:

```text
회장 Agent → 보고자 Agent: 지시 전달
보고자 사람 → 업무 수행
보고자 Agent/사람 → 완료 보고
회장님/회장 Agent → 완료 확인
```

따라서 WPS는 단순 A2A가 아니라 다음 개념을 포함해야 한다.

- 사람이 업무 수행
- 사람이 완료 보고
- 회장님 또는 회장 Agent가 확인
- 완료 여부가 message response만으로 자동 결정되지 않음

### 15.2 v2.0의 위치

v2.0은 WPS 업무처리 이전 단계이다. v1.6/v1.7의 관측 시스템 방향을 유지하되, 실제 구현을 시작할 수 있도록 인증, Admin API, idempotency, CI/Quality Gate 기준을 보완한 버전이다.

```text
v2.0 Hermes Agent Hub
  → request/response/message 수집
  → debugging / observation
  → 학습데이터 후보 축적
  → v2.1 Report/Instruction Chatroom
  → v2.2 Work Item / Completion / Verification
```

---

## 16. 구현 우선순위

### Priority 0: 기술 검증

- Hermes Gateway Hook이 실제로 `agent:start`, `agent:end` 이벤트를 Hub로 전송할 수 있는지 확인
- Hermes `state.db` read-only sync 가능성 확인
- Hermes Agent profile_name / identity 정보 수집 가능성 확인

### Priority 1: Hub Core

- FastAPI 프로젝트 생성
- SQLite schema 생성
- Admin seed
- Login
- Agent API token 인증
- Agent enrollment
- Message ingest
- Event ingest
- Idempotency 처리
- Message Explorer

### Priority 2: Hermes 연동

- Smoke client로 Hub ingest payload contract 검증
- Gateway Hook handler PoC 작성
- 또는 state.db sync collector 작성
- Agent enrollment token 설정
- e2e message 저장 확인

### Priority 3: Admin UX

- Agent Registry
- Agent token 발급
- Agent mapping/disable
- Message filter
- Raw payload detail
- Event Explorer
- Date-based search

### Priority 4: CI / Quality Gate

- GitHub Actions workflow 작성
- pytest unit/regression/API smoke test 실행
- pytest-cov coverage report 생성
- Playwright smoke test 실행 경로 준비
- 실패/coverage 미달 사항을 warning/report로 기록

### Priority 5: 확장 후보

- Export
- sqlite-vec embedding
- Report Chatroom
- Instruction Chatroom
- Work Item 변환
- Daily Summary


---

## 17. Testing & Quality Gate Requirements

### 17.1 기본 품질 원칙

Hermes Agent Hub / WPS는 기능을 빠르게 추가하는 것보다, 변경 가능한 구조를 안정적으로 유지하는 것을 우선한다.

따라서 모든 개발 작업은 다음 원칙을 따른다.

1. 기능 추가 전에는 반드시 기존 코드 구조를 검토한다.
2. 코드 구조 변경(refactoring)이 필요한 경우, 기능 추가보다 refactoring을 우선한다.
3. refactoring은 기능 동작을 변경하지 않아야 하며, 기존 regression test를 통과해야 한다.
4. 단위 기능 추가, 기능 변경, bug fix, DB schema 변경, UI 변경이 발생하면 반드시 automated test를 수행한다.
5. 테스트 실패 또는 coverage 미달은 숨기지 않고 GitHub Actions summary, 작업 로그, issue 등에 기록한다.
6. v2.0 초기에는 Quality Gate를 hard block으로 사용하지 않고, warning/report 기반으로 운영하며 점진적으로 목표를 달성한다.
7. main branch 보호 또는 required check 적용은 테스트 안정화 이후 별도 결정한다.

### 17.2 Test Type

본 프로젝트는 다음 자동화 테스트를 수행한다.

| Test Type | 목적 | 도구 |
|---|---|---|
| Unit Testing | 함수, method, service, repository 단위 검증 | pytest |
| Regression Testing | 기존 기능의 재동작 보장 | pytest |
| Smoke Testing | 주요 화면/API가 최소 정상 동작하는지 확인 | pytest, Playwright |
| Web UI Testing | 로그인, Admin Message Explorer, Agent Registry 화면 검증 | Playwright |
| Coverage Measurement | statement/branch coverage 측정 | pytest-cov |

### 17.3 Unit Test 요구사항

새로운 method, function, service, repository, API endpoint를 추가할 때는 해당 기능의 unit test를 함께 작성해야 한다.

Unit test case 설계 시 다음 기법을 적용한다.

1. **Boundary Value Analysis**
   - 빈 문자열
   - 최소 길이 입력
   - 최대 길이 입력
   - 날짜 범위의 시작/종료 경계
   - page size, limit, offset 경계값

2. **Robustness Test Case**
   - null 또는 누락된 필드
   - 잘못된 email 형식
   - 잘못된 role 값
   - 잘못된 token
   - 존재하지 않는 agent_id
   - malformed JSON payload

3. **Worst Case Test Case**
   - 긴 message content
   - 대량 message 조회
   - 동일 agent의 반복 heartbeat
   - 동일 request_id 중복 ingest
   - 시간 범위가 큰 검색 요청

### 17.4 Regression Test 요구사항

소스코드 변경이 발생할 때마다 regression test를 수행해야 한다.

Regression test 대상 변경 유형은 다음과 같다.

1. 단위 기능 추가
2. 기능 변경
3. bug fix
4. DB schema 변경
5. API request/response schema 변경
6. UI template 변경
7. 인증/권한 로직 변경
8. Hermes Agent ingest 로직 변경
9. Message Explorer 검색/필터 로직 변경
10. Agent 등록/매핑 로직 변경

Regression test는 최소한 다음 기능을 포함해야 한다.

- Admin login
- Agent enrollment
- Agent heartbeat
- message ingest
- response ingest
- request/response pair 저장
- Agent list 조회
- Message Explorer 날짜 검색
- Agent/email/platform/role/keyword filter
- raw payload detail 조회
- 권한 없는 사용자 접근 차단

### 17.5 SQLite Test Database 요구사항

SQLite database와 연동하는 모든 기능은 production database를 직접 사용하지 않고, 별도 test database를 사용해야 한다.

요구사항은 다음과 같다.

1. 테스트 실행 전마다 test database 파일을 새로 초기화한다.
2. 테스트 실행 전 schema migration 또는 schema creation을 수행한다.
3. 테스트별로 필요한 seed data를 명시적으로 입력한다.
4. 테스트 종료 후 test database 파일은 삭제하거나 다음 테스트에서 재사용되지 않도록 격리한다.
5. test database 파일명은 production database와 명확히 구분한다.
6. pytest fixture를 사용하여 test database lifecycle을 관리한다.

예시 test database 파일명:

```text
/tmp/hermes_agent_hub_test.sqlite3
./tests/tmp/test_hub.sqlite3
```

권장 pytest fixture 구조:

```text
tests/conftest.py
- tmp_db_path fixture
- test_engine fixture
- db_session fixture
- test_client fixture
- seed_admin_user fixture
- seed_agent fixture
```

### 17.6 Web UI Test 요구사항

Web 화면 테스트는 Playwright를 사용한다.

Playwright 테스트 대상은 다음과 같다.

1. 로그인 화면 렌더링
2. Admin 로그인 성공
3. Admin 로그인 실패
4. Admin Dashboard 접근
5. Agent Registry 화면 조회
6. Message Explorer 화면 조회
7. 날짜 범위 검색 동작
8. Agent/email/platform/role filter 동작
9. keyword 검색 동작
10. Message Detail modal 또는 detail page 조회
11. responsive layout 기본 검증

Playwright smoke test는 최소한 다음 user journey를 포함해야 한다.

```text
Login as Admin
→ Open Admin Dashboard
→ Open Agent Registry
→ Open Message Explorer
→ Apply Date Filter
→ Open Message Detail
→ Logout
```

### 17.7 Coverage 목표

pytest-cov를 사용하여 source code statement coverage와 branch coverage를 측정한다.

목표 기준은 다음과 같다.

| Coverage Type | Target |
|---|---:|
| Statement Coverage | 90% 이상 |
| Branch Coverage | 85% 이상 |

Coverage 측정 대상은 다음을 포함한다.

- app services
- repositories
- API routers
- auth logic
- ingest logic
- search/filter logic
- DB model helper

Coverage 측정에서 제외 가능한 영역은 다음과 같다.

- migration script
- static file
- Bootstrap template 자체
- generated code
- test helper
- 외부 library wrapper 중 단순 pass-through 코드

권장 명령어 예시는 다음과 같다.

```bash
pytest --cov=app --cov-branch --cov-report=term-missing --cov-report=html
```

### 17.8 Test Directory Structure

권장 테스트 디렉토리 구조는 다음과 같다.

```text
tests/
  conftest.py
  unit/
    test_auth_service.py
    test_agent_service.py
    test_ingest_service.py
    test_message_service.py
    test_search_service.py
  api/
    test_auth_api.py
    test_agent_api.py
    test_ingest_api.py
    test_message_api.py
  regression/
    test_admin_message_explorer_regression.py
    test_agent_enrollment_regression.py
  smoke/
    test_smoke_api.py
  ui/
    test_admin_login.spec.py
    test_message_explorer.spec.py
```

### 17.9 GitHub Actions CI / Sync Quality Gate

GitHub Actions를 기본 CI로 사용한다. CI는 push 또는 pull request 발생 시 자동으로 실행되며, 초기에는 commit/push 차단보다 결과 가시화와 품질 개선을 우선한다.

권장 workflow 파일:

```text
.github/workflows/ci.yml
```

기본 CI job은 다음을 포함한다.

1. 관련 unit test 작성 완료
2. pytest unit/API/regression test 실행
3. SQLite test database 기반 테스트 통과
4. pytest-cov coverage 측정 및 report 생성
5. 관련 Web UI 변경 시 Playwright smoke test 실행 또는 local smoke 결과 기록
6. lint 또는 format 적용
7. 실패한 test, skipped test, coverage 미달 사유를 GitHub Actions summary 또는 작업 로그에 명확히 기록

v2.0 Quality Gate 단계:

| 단계 | 운영 방식 | 기준 |
|---|---|---|
| Level 0 | Report Only | 테스트/coverage를 실행하고 결과를 기록한다 |
| Level 1 | Warning Gate | 실패나 coverage 미달을 warning으로 표시하고 issue/task로 추적한다 |
| Level 2 | Soft Gate | release 후보 또는 main merge 전에는 주요 regression 실패를 해소한다 |
| Level 3 | Hard Gate 후보 | 테스트가 안정화된 후 required check 적용 여부를 결정한다 |

v2.0의 기본 운영 단계는 Level 0에서 시작하여 Level 1을 목표로 한다. Coverage 90%/85%는 목표값이며, 초기 개발 단계에서 commit/push를 차단하는 hard threshold로 사용하지 않는다.

권장 개발 흐름은 다음과 같다.

```text
코드 구조 검토
→ 필요 시 refactoring
→ unit test 작성 또는 보강
→ 기능 구현
→ unit test 실행
→ regression test 실행
→ coverage 측정
→ Playwright smoke test 실행(UI 변경 시)
→ 실패/미달 항목 기록
→ Git commit
→ GitHub sync
→ GitHub Actions 결과 확인
```

### 17.10 Refactoring 우선 원칙

다음 상황에서는 기능 추가보다 refactoring을 먼저 수행해야 한다.

1. API router에 business logic이 과도하게 포함된 경우
2. DB query가 template 또는 router에 직접 흩어져 있는 경우
3. 동일한 validation logic이 여러 곳에 중복된 경우
4. ingest 처리와 normalization 처리가 분리되어 있지 않은 경우
5. test 작성이 어려울 정도로 함수 책임이 큰 경우
6. auth/authorization logic이 endpoint별로 중복된 경우
7. Message Explorer filter 조건이 재사용 불가능한 구조인 경우

Refactoring 후에는 기존 regression test가 모두 통과해야 한다.

### 17.11 Acceptance Criteria for Testing

- 모든 신규 API endpoint는 pytest 기반 API test를 가져야 한다.
- 모든 신규 service method는 정상/경계/오류 test case를 가져야 한다.
- SQLite 연동 test는 독립 test database를 사용해야 한다.
- Admin 주요 화면은 Playwright smoke test 대상이어야 한다.
- statement coverage 90%, branch coverage 85%를 목표로 측정되어야 한다.
- v2.0 초기에는 regression test 실패 또는 coverage 미달을 commit/push hard block으로 사용하지 않는다.
- 실패/미달 항목은 GitHub Actions summary, issue, 작업 로그 중 하나에 기록되어야 한다.

---

## 18. Acceptance Criteria

### AC-001 Admin 로그인

초기 seed admin 계정으로 로그인할 수 있어야 한다.

### AC-002 Agent 등록

Hermes Agent 또는 Collector가 enrollment token으로 Hub에 등록되어야 한다.

명시적으로 잘못된 enrollment token을 전달한 등록 요청은 UNMAPPED로 저장되지 않고 인증 오류로 거부되어야 한다.

### AC-003 Agent heartbeat

등록 Agent가 Bearer API token으로 heartbeat를 보내면 Admin 화면에서 last_seen_at이 갱신되어야 한다.

### AC-004 Message ingest

ACTIVE Hermes Agent에서 발생한 sample request가 Bearer API token 인증 후 Hub DB의 `agent_messages`에 저장되어야 한다.

### AC-005 Response ingest

ACTIVE Hermes Agent에서 발생한 sample response가 Bearer API token 인증 후 Hub DB의 `agent_messages`에 저장되어야 한다.

### AC-006 Raw payload 확인

Admin은 Message Detail 화면에서 raw_payload JSON을 확인할 수 있어야 한다.

### AC-007 Request/Response Pair 확인

Admin은 Message Detail API에서 같은 `request_id` 또는 직접 parent/child 관계로 연결된 related message 목록을 확인할 수 있어야 한다.

### AC-008 날짜 검색

Admin은 특정 날짜 범위의 message만 조회할 수 있어야 한다.

### AC-009 Agent 필터

Admin은 특정 Agent의 message만 조회할 수 있어야 한다.

### AC-010 Keyword 검색

Admin은 keyword 기준으로 message를 검색할 수 있어야 한다.

### AC-011 UNMAPPED Agent 확인

Enrollment token 없이 등록된 Agent는 UNMAPPED로 표시되고 Admin이 사용자 email과 매핑할 수 있어야 한다.

### AC-012 Agent API 인증

Heartbeat, message ingest, event ingest는 `Authorization: Bearer <api_token>` header를 검증해야 한다. token이 없거나 유효하지 않은 요청은 거부되어야 한다.

### AC-013 UNMAPPED Agent ingest 제한

UNMAPPED Agent는 heartbeat만 허용되고 message/event ingest는 `403 Forbidden`으로 거부되어야 한다.

### AC-014 중복 ingest idempotency

동일 `idempotency_key` 또는 동일 `external_message_id`로 message ingest가 재전송되면 중복 row를 생성하지 않고 기존 message id를 반환해야 한다.

### AC-015 Admin Agent 관리

Admin은 enrollment token 발급, Agent 목록 조회, UNMAPPED Agent 매핑, 표시 이름 변경, Agent 비활성화를 수행할 수 있어야 한다.

### AC-016 Event 검색

Admin은 날짜, Agent, severity, event_type 기준으로 lifecycle event를 검색할 수 있어야 한다.

### AC-017 Event 상세 조회

Admin은 Event 검색 결과의 event id로 상세 API를 호출하여 summary와 raw_payload JSON을 확인할 수 있어야 한다.

### AC-018 Dashboard 요약 조회

Admin은 Dashboard Summary API로 전체/ACTIVE/UNMAPPED Agent 수와 오늘 message 수, 최근 24시간 event/error event 수를 확인할 수 있어야 한다.

### AC-019 GitHub Actions CI

GitHub push 또는 pull request 발생 시 GitHub Actions에서 pytest 기반 test와 coverage 측정이 실행되고 결과가 확인 가능해야 한다.

### AC-020 점진적 Quality Gate

Coverage 목표 미달 또는 non-critical smoke test 실패는 v2.0 초기에는 commit/push hard block이 아니라 warning/report로 기록되어야 한다.

---

## 19. Open Issues

1. Hermes Gateway Hook 방식으로 request와 response를 충분히 포착할 수 있는가?
2. CLI 사용 시 Gateway Hook이 동작하지 않는 경우 Plugin Hook 또는 state.db sync가 필요한가?
3. Hermes `state.db` schema 변경 가능성을 어떻게 관리할 것인가?
4. Agent별 profile_name, SOUL.md identity, display name을 어떤 방식으로 수집할 것인가?
5. Admin 외 사용자를 v2.0에 포함할 것인가?
6. message content에 민감정보가 포함될 경우 v2.0에서 masking을 할 것인가?
7. request/response pair를 어떤 key로 안정적으로 연결할 것인가?
8. Gateway Hook 실패 시 local retry queue를 반드시 구현할 것인가?
9. sqlite-vec는 v2.0 필수인가, v2.1 이후인가?
10. 학습데이터 export 형식은 JSONL, CSV, Parquet 중 무엇을 우선할 것인가?
11. Playwright 테스트를 GitHub Actions에서 항상 실행할 것인가, UI 변경 시 선택적으로 실행할 것인가?
12. sqlite-vec 연동 테스트를 v2.0 필수로 포함할 것인가, 향후 semantic search 단계에서 포함할 것인가?

---

## 20. v2.1 이후 확장 방향

v2.0이 성공하면 다음 단계로 확장한다.

### v2.1 Report / Instruction Chatroom

- 고정 Report Chatroom
- 고정 Instruction Chatroom
- 회장 Agent 보고 요약 조회
- 직원 Agent 지시 조회

### v2.2 Work Item Processing

- message를 work item으로 변환
- 지시 상태: REQUESTED / IN_PROGRESS / DONE_REPORTED / VERIFIED
- 보고자 완료 처리
- 회장님 확인/반려

### v2.3 Summary / Learning Data

- Daily Summary
- 회장 Agent Brief
- 학습데이터 후보 tagging
- masking
- export

---

## 21. 결론

WPS v2.0은 기존 Messenger/Kanban 중심의 업무 시스템 구현을 잠시 뒤로 미루고, Hermes Agent와의 실제 연동 가능성을 검증하기 위한 **Hermes Agent Hub e2e Minimal Collector**를 기준으로 하되, Agent 인증, Admin API, idempotency, GitHub Actions 기반 CI, 점진적 Quality Gate를 구현 기준으로 명확히 한 버전으로 정의한다.

이 단계의 성공 기준은 단순하다.

> ACTIVE Hermes Agent에서 발생한 request/response/message가 인증된 API를 통해 Hub SQLite DB에 저장되고, Admin이 이를 검색·필터링·확인할 수 있어야 한다.

이 기반이 완성되면, 이후 보고 Chatroom, 업무지시, 완료보고, 회장님 확인, 학습데이터 가공 기능을 안정적으로 추가할 수 있다.
