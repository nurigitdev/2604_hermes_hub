# Hermes Agent Hub / WPS Software Requirements Specification v1.7

**Document Title:** Hermes Agent Hub — e2e Minimal Collector + Testing & Quality Gate Edition  
**Related Project:** WPS(Work Processing Stack)  
**Version:** v1.7 Draft  
**Baseline Replaced:** Hermes Agent Hub / WPS SRS v1.6 — e2e Minimal Collector Edition  
**작성일:** 2026-06-25  
**상태:** Draft for Review / Codex Implementation Preparation  

---

## 1. 문서 목적

본 문서는 기존 WPS v1.5의 “Minimal Internal Messenger” 중심 요구사항을 재검토하여, 1단계 구현 목표를 **Hermes Agent Hub e2e Minimal Collector**로 재정의한 Software Requirements Specification이다.

v1.7의 핵심 목표는 v1.6에서 정의한 **Hermes Agent에서 발생하는 request / response / message / session 이벤트를 수집하고 관찰할 수 있는 최소 e2e 기반**을 유지하면서, 구현 과정에서 자동화된 testing과 quality gate를 필수 개발 절차로 포함하는 것이다.

이를 통해 다음 목적을 달성한다.

1. Hermes Agent가 실제로 어떤 요청과 응답을 생성하는지 관찰한다.
2. Hermes Agent의 request/response/message를 1차적으로 SQLite DB에 저장한다.
3. Admin 화면에서 Agent, 사용자, 기간, 키워드 기준으로 메시지를 검색하고 확인한다.
4. 수집된 데이터를 debugging, 사용패턴 분석, 향후 학습데이터 가공의 원천 데이터로 활용한다.
5. 향후 WPS의 보고 Chatroom, 업무지시, 완료확인, 회장 Agent 요약 기능을 구축하기 위한 기반을 마련한다.

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

따라서 v1.6에서 우선순위를 다음과 같이 변경하였고, v1.7에서는 여기에 Testing & Quality Gate 요구사항을 추가한다.

| 구분 | v1.5 | v1.6 |
|---|---|---|
| 1차 목표 | Minimal Internal Messenger | Hermes Agent message 수집/관찰 |
| 핵심 데이터 | Chatroom message | Hermes request/response/session/event |
| 주요 사용자 | Reporter, Chairman, Admin | Admin 중심 |
| 화면 | Report Chatroom, Instruction Chatroom | Message Explorer, Agent Registry |
| 업무지시 처리 | 일부 포함 | 후순위 |
| 완료확인 | 일부 포함 | 후순위 |
| Hermes 연동 | REST/API 전제 | Gateway/Hook/state.db/plugin 방식 검토 후 선택 |

### 2.3 v1.6의 핵심 관점

v1.6은 업무처리 시스템이 아니라 **관측 시스템**이다.

> Hermes Agent Hub v1.6은 Hermes Agent의 request/response/message를 수집하여 SQLite에 저장하고, Admin이 이를 검색·필터링·확인할 수 있도록 하는 최소 e2e Collector 시스템이다.


### 2.4 v1.7 추가 변경 사항

v1.7에서는 v1.6의 Hermes Agent Hub e2e Minimal Collector 범위는 유지하되, 구현 단계에서 반드시 준수해야 할 **Testing & Quality Gate 요구사항**을 추가한다.

v1.7의 추가 목적은 다음과 같다.

1. 기능 추가보다 코드 구조 검토와 refactoring을 우선한다.
2. 모든 기능 추가, 변경, bug fix 이후 자동화된 unit testing과 regression testing을 수행한다.
3. SQLite 연동 기능은 항상 독립적인 test database를 초기화한 후 검증한다.
4. Web UI는 Playwright 기반 smoke/regression testing 대상으로 관리한다.
5. pytest, pytest-cov 기반 coverage 기준을 명확히 한다.
6. 단위 기능이 regression test를 통과한 후에만 GitHub commit/sync를 수행한다.


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

## 4. v1.6 범위

### 4.1 In Scope

v1.6에서 구현해야 할 범위는 다음과 같다.

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

### 4.2 Out of Scope

v1.6에서 제외하거나 후순위로 두는 기능은 다음과 같다.

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

단, 위 항목은 v1.7 이후 확장 후보로 남긴다.

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
| Realtime | v1.6에서는 필수 아님. 필요 시 SSE 확장 |
| ORM | SQLAlchemy 또는 SQLModel 중 선택 |
| Auth | Cookie Session 기반 Admin Login 우선 |
| Deployment | 사내망 단일 서버 우선 |

### 5.2 sqlite-vec 적용 원칙

v1.6에서는 sqlite-vec를 필수 기능으로 구현하지 않아도 된다. 다만 향후 다음 기능을 위해 DB 구조 및 코드 구조에서 확장 가능성을 열어둔다.

- 유사 message 검색
- request/response clustering
- 학습데이터 후보 검색
- 보고/업무지시 semantic search
- 유사 장애/질문 pattern 분석

---

## 6. 사용자 및 권한

### 6.1 v1.6 사용자 유형

v1.6은 Admin 중심 시스템이다.

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

Token이 없는 Agent가 접속하면 `UNMAPPED` 상태로 등록한다.  
Admin은 Agent 목록 화면에서 해당 Agent를 확인한 후 사용자 email과 수동 매핑한다.

### 7.4 권장 방식

v1.6에서는 두 방식을 모두 고려하되, 구현 우선순위는 다음으로 한다.

1. Enrollment Token 기반 자동 등록
2. Token 없는 Agent는 UNMAPPED로 등록
3. Admin 수동 매핑

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

#### v1.6 평가

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

#### v1.6 평가

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

#### v1.6 평가

2단계 확장 후보로 유지한다.

---

### 8.4 후보 4: Webhook Adapter 방식

Hermes Webhook Adapter는 외부 시스템이 Hermes Gateway로 이벤트를 전달하는 데 적합하다.

#### 장점

- Hub → Hermes 방향 이벤트 전달에 적합
- 보고 요약 또는 지시 전달 단계에서 활용 가능

#### 단점

- Hermes → Hub 방향 message capture에는 직접적이지 않음

#### v1.6 평가

v1.6 message capture보다는 v1.7 이후 Hub-to-Hermes notification에 적합하다.

---

### 8.5 v1.6 연동 전략

v1.6에서는 다음 순서로 접근한다.

1. Hermes Gateway Hook 방식이 설정만으로 가능한지 우선 검증한다.
2. Gateway Hook 방식이 어렵거나 누락이 크면 state.db read-only sync collector를 병행한다.
3. 그래도 부족하면 Hermes Agent 소스의 gateway hook 또는 platform adapter 부분을 최소 수정한다.
4. Plugin Hook 및 전용 WPS Adapter 개발은 후순위로 둔다.

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
| status | TEXT | ACTIVE / UNMAPPED / DISABLED |
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
| owner_email | TEXT | 대상 email |
| agent_id | INTEGER NULL | 연결된 Agent |
| expires_at | DATETIME NULL | 만료일 |
| used_at | DATETIME NULL | 사용일 |
| is_active | INTEGER | 활성 여부 |
| created_at | DATETIME | 생성일 |

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

## 10. API 요구사항

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

---

### 10.2 Agent Enrollment API

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
  "status": "ACTIVE"
}
```

Token이 없거나 유효하지 않으면 `UNMAPPED` 상태로 등록될 수 있다.

---

### 10.3 Agent Heartbeat API

#### POST `/api/v1/agents/heartbeat`

Agent의 생존 상태를 Hub에 전송한다.

Request:

```json
{
  "agent_uid": "agent_20260625_0001",
  "profile_name": "kim-teamlead",
  "source": "gateway",
  "status": "running"
}
```

---

### 10.4 Message Ingest API

#### POST `/api/v1/messages/ingest`

Hermes request/response/message를 Hub에 저장한다.

Request:

```json
{
  "agent_uid": "agent_20260625_0001",
  "event_type": "agent:start",
  "source": "telegram",
  "session_key": "agent:main:telegram:private:123456789",
  "direction": "INBOUND",
  "role": "user",
  "content": "오늘 작업 내용을 정리해줘",
  "request_id": "req_abc123",
  "occurred_at": "2026-06-25T09:30:00+09:00",
  "raw_payload": {}
}
```

Response:

```json
{
  "ok": true,
  "message_id": 1001
}
```

---

### 10.5 Event Ingest API

#### POST `/api/v1/events/ingest`

Lifecycle event를 Hub에 저장한다.

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

---

### 10.6 Admin Search API

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

유효한 token 없이 접근한 Agent는 UNMAPPED 상태로 등록될 수 있어야 한다.

### FR-006 Agent-User 매핑

Admin은 UNMAPPED Agent를 사용자 email과 매핑할 수 있어야 한다.

### FR-007 Agent Heartbeat 저장

Agent는 주기적으로 heartbeat를 전송하고 Hub는 `last_seen_at`을 갱신해야 한다.

### FR-008 Message Ingest

Hub는 Hermes Agent에서 발생한 request/response/message를 API로 수신하여 DB에 저장해야 한다.

### FR-009 Raw Payload 저장

모든 ingest message/event는 원본 payload JSON을 저장해야 한다.

### FR-010 Normalized Field 저장

검색 및 필터링을 위해 source, role, event_type, content, occurred_at 등 normalized field를 저장해야 한다.

### FR-011 중복 Message 방지

동일 content_hash 또는 external_message_id 기준으로 중복 저장을 방지할 수 있어야 한다.

### FR-012 Request/Response Pair 연결

가능한 경우 request_id, parent_message_id 등을 사용하여 request와 response를 연결해야 한다.

### FR-013 Admin Message Search

Admin은 날짜, Agent, 사용자, source, role, keyword 기준으로 message를 검색할 수 있어야 한다.

### FR-014 Message Detail View

Admin은 message 상세와 raw JSON payload를 확인할 수 있어야 한다.

### FR-015 Event Search

Admin은 lifecycle event를 검색할 수 있어야 한다.

### FR-016 Export 후보

v1.6에서는 필수는 아니지만, message 검색 결과를 JSON 또는 CSV로 export할 수 있는 구조를 고려해야 한다.

### FR-017 Hermes 연동 방식 선택

개발 초기에 Gateway Hook, state.db sync, Plugin Hook 중 최소 1개 방식으로 e2e message 수집 PoC를 수행해야 한다.

---

## 13. 비기능 요구사항

### NFR-001 단순성

v1.6은 minimal e2e 구현을 목표로 하며, 업무처리 기능보다 message 수집/조회 기능을 우선한다.

### NFR-002 보안

- Admin password는 hash로 저장한다.
- Agent API token은 평문 저장하지 않고 hash 저장을 권장한다.
- API token이 없는 ingest 요청은 거부해야 한다.
- UNMAPPED 등록은 허용하더라도 message ingest는 제한할 수 있어야 한다.

### NFR-003 성능

- SQLite 기준 10만 건 수준의 message 검색을 초기 목표로 한다.
- 날짜 범위, agent_id, source, role, event_type에 index를 생성한다.
- keyword 검색은 SQLite FTS 또는 단순 LIKE에서 시작할 수 있다.

### NFR-004 신뢰성

- Hermes Hook 또는 Collector 전송 실패 시 로컬 임시 파일에 retry queue를 둘 수 있어야 한다.
- Hub API는 동일 message 재전송 시 idempotent하게 처리할 수 있어야 한다.

### NFR-005 확장성

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

### NFR-006 개인정보/민감정보

수집 데이터에는 업무상 민감정보가 포함될 수 있다. v1.6에서는 자동 마스킹이 필수는 아니지만, 향후 데이터 export 및 학습데이터 가공 단계에서 masking pipeline을 추가할 수 있어야 한다.

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

### 15.2 v1.6의 위치

v1.6은 WPS 업무처리 이전 단계이다.

```text
v1.6 Hermes Agent Hub
  → request/response/message 수집
  → debugging / observation
  → 학습데이터 후보 축적
  → v1.7 Report/Instruction Chatroom
  → v1.8 Work Item / Completion / Verification
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
- Agent enrollment
- Message ingest
- Event ingest
- Message Explorer

### Priority 2: Hermes 연동

- Gateway Hook handler 작성
- 또는 state.db sync collector 작성
- Agent enrollment token 설정
- e2e message 저장 확인

### Priority 3: Admin UX

- Agent Registry
- Message filter
- Raw payload detail
- Event Explorer
- Date-based search

### Priority 4: 확장 후보

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
5. 테스트를 통과하지 못한 코드는 GitHub commit 또는 main branch 동기화 대상이 될 수 없다.

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

### 17.9 GitHub Commit / Sync Quality Gate

단위 기능 구현 후 GitHub commit 및 동기화는 다음 조건을 만족한 경우에만 수행한다.

1. 관련 unit test 작성 완료
2. 전체 pytest regression test 통과
3. SQLite test database 기반 테스트 통과
4. 관련 Web UI 변경 시 Playwright smoke test 통과
5. pytest-cov coverage 기준 충족 또는 coverage 미달 사유 명시
6. lint 또는 format 적용
7. 주요 변경사항이 commit message에 명확히 기록됨

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
→ Git commit
→ GitHub sync
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
- regression test 실패 상태에서는 GitHub commit/sync를 수행하지 않아야 한다.

---

## 18. Acceptance Criteria

### AC-001 Admin 로그인

초기 seed admin 계정으로 로그인할 수 있어야 한다.

### AC-002 Agent 등록

Hermes Agent 또는 Collector가 enrollment token으로 Hub에 등록되어야 한다.

### AC-003 Agent heartbeat

등록 Agent가 heartbeat를 보내면 Admin 화면에서 last_seen_at이 갱신되어야 한다.

### AC-004 Message ingest

Hermes Agent에서 발생한 sample request가 Hub DB의 `agent_messages`에 저장되어야 한다.

### AC-005 Response ingest

Hermes Agent에서 발생한 sample response가 Hub DB의 `agent_messages`에 저장되어야 한다.

### AC-006 Raw payload 확인

Admin은 Message Detail 화면에서 raw_payload JSON을 확인할 수 있어야 한다.

### AC-007 날짜 검색

Admin은 특정 날짜 범위의 message만 조회할 수 있어야 한다.

### AC-008 Agent 필터

Admin은 특정 Agent의 message만 조회할 수 있어야 한다.

### AC-009 Keyword 검색

Admin은 keyword 기준으로 message를 검색할 수 있어야 한다.

### AC-010 UNMAPPED Agent 확인

Token 없이 등록된 Agent는 UNMAPPED로 표시되고 Admin이 사용자 email과 매핑할 수 있어야 한다.

---

## 19. Open Issues

1. Hermes Gateway Hook 방식으로 request와 response를 충분히 포착할 수 있는가?
2. CLI 사용 시 Gateway Hook이 동작하지 않는 경우 Plugin Hook 또는 state.db sync가 필요한가?
3. Hermes `state.db` schema 변경 가능성을 어떻게 관리할 것인가?
4. Agent별 profile_name, SOUL.md identity, display name을 어떤 방식으로 수집할 것인가?
5. Admin 외 사용자를 v1.6에 포함할 것인가?
6. message content에 민감정보가 포함될 경우 v1.6에서 masking을 할 것인가?
7. request/response pair를 어떤 key로 안정적으로 연결할 것인가?
8. Gateway Hook 실패 시 local retry queue를 반드시 구현할 것인가?
9. sqlite-vec는 v1.6 필수인가, v1.7 이후인가?
10. 학습데이터 export 형식은 JSONL, CSV, Parquet 중 무엇을 우선할 것인가?

11. Playwright 테스트를 CI에서 실행할 것인가, local smoke test로만 시작할 것인가?
12. coverage 기준 미달 시 commit을 차단할 것인가, 경고로만 관리할 것인가?
13. sqlite-vec 연동 테스트를 v1.7 필수로 포함할 것인가, 향후 semantic search 단계에서 포함할 것인가?
14. GitHub Actions 또는 사내 CI 서버를 v1.7 범위에 포함할 것인가?

---

## 20. v1.8 이후 확장 방향

v1.6이 성공하면 다음 단계로 확장한다.

### v1.8 Report / Instruction Chatroom

- 고정 Report Chatroom
- 고정 Instruction Chatroom
- 회장 Agent 보고 요약 조회
- 직원 Agent 지시 조회

### v1.9 Work Item Processing

- message를 work item으로 변환
- 지시 상태: REQUESTED / IN_PROGRESS / DONE_REPORTED / VERIFIED
- 보고자 완료 처리
- 회장님 확인/반려

### v1.10 Summary / Learning Data

- Daily Summary
- 회장 Agent Brief
- 학습데이터 후보 tagging
- masking
- export

---

## 21. 결론

WPS v1.7은 기존 Messenger/Kanban 중심의 업무 시스템 구현을 잠시 뒤로 미루고, Hermes Agent와의 실제 연동 가능성을 검증하기 위한 **Hermes Agent Hub e2e Minimal Collector**를 기준으로 하되, 구현 품질 확보를 위한 **Testing & Quality Gate**를 추가한 버전으로 정의한다.

이 단계의 성공 기준은 단순하다.

> Hermes Agent에서 발생한 request/response/message가 Hub SQLite DB에 저장되고, Admin이 이를 검색·필터링·확인할 수 있어야 한다.

이 기반이 완성되면, 이후 보고 Chatroom, 업무지시, 완료보고, 회장님 확인, 학습데이터 가공 기능을 안정적으로 추가할 수 있다.
