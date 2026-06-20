# МАССО — Мультиагентная система ситуативного обучения

Адаптивная образовательная платформа с динамической LLM-генерацией уникальных практических сценариев, изолированными учебными средами Docker/Kubernetes и автоматической верификацией через трёх LangGraph-агентов.  
Документация: `docs/ТЗ.pdf` (требования), `docs/ТП.pdf` (архитектура, модели данных, API, макеты).

---

## Стек (зафиксированные версии из ТЗ)

| Слой | Технологии |
|------|-----------|
| Backend | Python 3.13.x · FastAPI 0.136.x · Pydantic 2.13.x · SQLAlchemy 2.0.x · Alembic |
| Quality | pytest · ruff · mypy |
| Agents | LangGraph 1.1.x · LangChain Core 1.3.x |
| Frontend | Node.js 24 LTS · Next.js 16.2.x · React 19.2.x · TypeScript 6.0 |
| UI-компоненты | xterm.js · Monaco Editor · Recharts |
| Данные | PostgreSQL 18.x · Neo4j 5.26 LTS · ChromaDB 1.5.x · Redis 8.x |
| Инфраструктура | Docker Engine 29.x · Docker Compose v5 · Kubernetes 1.35/1.36 · Nginx |
| Наблюдаемость | Prometheus 3.x · Grafana |

---

## Архитектурные компоненты

| Компонент | Ответственность |
|-----------|----------------|
| **Frontend** | Next.js App Router, 4 роли: student / teacher / methodist / admin |
| **Backend/API** | FastAPI REST + WebSocket, OpenAPI, Auth/RBAC |
| **LangGraph Orchestrator** | Конвейер: профиль → генерация → сессия → инцидент → проверка → отчёт |
| **ProfileAgent** | Neo4j-граф компетенций, выявление дефицитов навыков, ранжирование по приоритетам |
| **ScenarioAgent** | Генерация легенд/артефактов/checks через LLM Gateway, валидация достижимости, ChromaDB-дедупликация (cosine ≥ 0.90 → отказ) |
| **AssessmentAgent** | ≤3 подсказки/сессию (штраф −10% каждая), динамические инциденты ≤5 мин, запуск Verification Engine |
| **LLM Gateway** | Provider-agnostic адаптер: external → local (Ollama/vLLM) → template fallback; переключение без остановки сессий |
| **Sandbox Manager** | Docker/Compose/K8s без привилегий, --cap-drop ALL, deny-by-default сеть, очистка ≤30 сек |
| **Verification Engine** | docker inspect/exec/healthcheck для ИТ-сценариев; rule_match + cosine similarity (порог 0.85) для документных |
| **PostgreSQL** | Пользователи, роли, сессии, события, результаты, отчёты, audit_logs, llm_providers, sandbox_profiles |
| **Neo4j** | Узлы: User, Skill, Domain, Scenario; рёбра: HAS_SKILL, REQUIRES, TARGETS, BELONGS_TO |
| **ChromaDB** | Коллекции: scenario_legends, knowledge_docs, hint_examples, prompt_templates, accepted_solutions |
| **Redis** | Очереди (Streams), статусы сессий (TTL), rate-limit, счётчики подсказок, Pub/Sub для WS |
| **Monitoring & Audit** | Prometheus-метрики, Grafana, audit_logs, security_events, трассировка trace_id |

---

## Целевая структура репозитория

```
.github/workflows/ci.yml          # lint → typecheck → pytest → docker build → push → deploy

backend/
  pyproject.toml                  # зависимости + конфиг ruff/mypy/pytest
  app/
    api/            # Роутеры: auth, users, skills, scenarios, sessions, events, verification, reports, admin, ws
    agents/         # ProfileAgent, ScenarioAgent, AssessmentAgent (LangGraph StateGraph + typed State)
    core/           # config.py, security.py, deps.py, errors.py, metrics.py, response.py
    services/       # user_service, scenario_service, session_service, verification_service,
                    # incident_service, report_service, audit_service, security_service,
                    # terminal_service, event_publisher
    models/         # SQLAlchemy ORM: base, user, scenario, session, assessment, infra, audit
    schemas/        # Pydantic v2: common, auth, users, skills, scenarios, sessions,
                    # events, verification, reports, admin, websocket
    db/             # postgres.py, neo4j.py, neo4j_schema.py, chromadb.py, redis.py, seed.py
    llm/            # base.py, gateway.py, adapters/{openai,anthropic,ollama,template}_adapter.py
    sandbox/        # manager.py, images.py
    main.py
  alembic/
    versions/0001_initial_schema.py
  tests/
    unit/
    integration/    # Реальные БД, не моки
    smoke/          # E2E: полный lifecycle + SLA-assertions

frontend/
  app/              # Next.js 16 App Router
    (auth)/login/   # Экран входа
    (student)/      # dashboard/, sessions/[id]/, sessions/[id]/report/
    (teacher)/      # groups/, sessions/[id]/trace/
    (methodist)/    # graph/, templates/, reference/
    (admin)/        # users/, llm/, sandbox/, audit/, monitoring/
  components/
    workspace/      # Terminal (xterm.js), Editor (Monaco), EventLog
    charts/         # Recharts: SkillProgress, SessionMetrics
  lib/              # api.ts, types.ts, websocket.ts, auth-context.tsx

infra/
  docker/           # docker-compose.dev.yml (профили: default, test, monitoring, build)
                    # .env.example
  k8s/base/         # Kustomize базовые манифесты
  nginx/            # Reverse proxy конфиги
  backup/           # pg_backup.sh, neo4j_backup.sh, restore.sh
  prometheus.yml
  grafana/dashboards/masso.json

sandbox-images/     # devops-base/, security-base/, document-base/ (Dockerfiles с pinned digest, uid=1000)
```

---

## Команды разработки

> Команды `docker compose` работают начиная с Phase 0.3 (после создания `infra/docker/docker-compose.dev.yml`).

```bash
# Поднять все сервисы (БД + backend + frontend)
docker compose -f infra/docker/docker-compose.dev.yml up -d

# Backend dev
cd backend && uvicorn app.main:app --reload --port 8000

# Frontend dev
cd frontend && npm run dev

# Тесты
cd backend && pytest -x -q                    # unit + integration
cd backend && pytest tests/smoke/ -x -v       # E2E smoke (требует запущенных сервисов)
cd frontend && npm test

# Линтинг и типы
cd backend && ruff check . && mypy .
cd frontend && npx tsc --noEmit && npm run lint

# Миграции
cd backend && alembic upgrade head
cd backend && alembic revision --autogenerate -m "description"  # всегда проверять вручную перед коммитом
```

### Конфиг инструментов (backend/pyproject.toml)

```toml
[tool.ruff]
target-version = "py313"
line-length = 100
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.13"
strict = true
ignore_missing_imports = false

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
markers = ["smoke: end-to-end smoke tests requiring all services running"]
```

---

## API-конвенции

**REST-ответ** (все эндпоинты):
```json
{ "request_id": "uuid", "status": "success"|"error", "data": {}, "error": { "code": "SNAKE_CASE", "message": "На русском", "details": {} } }
```

**Корреляционные идентификаторы** — присутствуют в каждой записи событий: `session_id`, `scenario_id`, `user_id`, `trace_id`

**WebSocket-каналы**:
- `/ws/sessions/{id}/terminal` — stdin/stdout/stderr контейнера
- `/ws/sessions/{id}/events` — incident, hint, warning, security, check_status
- `/ws/sessions/{id}/status` — starting/ready/paused/checking/completed/failed
- `/ws/admin/monitoring` — queue, provider, sandbox, alert

**Коды ошибок**: `AUTH_INVALID_CREDENTIALS`, `AUTH_FORBIDDEN`, `SCENARIO_NOT_VALID`, `SESSION_NOT_READY`, `HINT_LIMIT_EXCEEDED`, `VERIFICATION_FAILED`, `LLM_PROVIDER_UNAVAILABLE`, `SANDBOX_LIMIT_EXCEEDED`, `REPORT_PERIOD_REQUIRED`, `VALIDATION_ERROR`

---

## Критические правила

### Sandbox-безопасность
- Каждый контейнер: `--no-new-privileges --cap-drop ALL` + лимиты CPU/RAM/storage + сетевая политика deny-by-default
- Сетевой доступ контейнера разрешается только через allowlist, если это явно требуется сценарием
- Попытки sandbox escape, privilege escalation, сетевого сканирования, обращения к запрещённым файлам — обязательно в `security_events`
- Обучающийся **никогда** не получает доступ к системным промптам, эталонным ответам, internal checks, данным чужих сессий

### Секреты
- Никаких API-ключей, паролей БД, LLM-токенов в исходном коде
- Только через переменные окружения или secret storage; `.env` файлы не коммитить

### LLM Gateway
- Порядок fallback: external → local (Ollama/vLLM) → template-only
- Переключение режима не прерывает уже запущенные учебные сессии
- При недоступности всех LLM — использовать каталог утверждённых шаблонов, новые сценарии помечать `pending_generation`

### Хранение данных
- Учебные логи: ≥180 дней; `security_events`: ≥1 год; резервные копии PostgreSQL + Neo4j: ≥30 дней
- Все версии сценариев сохраняются (для воспроизведения результата сессии)
- Граф компетенций и оценки — аудитируются; альтернативный путь решения попадает в ChromaDB `accepted_solutions` только после подтверждения преподавателем/методистом

### Нефункциональные SLA
- Генерация сценария ≤120 сек; развёртывание среды ≤120 сек; проверка + отчёт ≤30 сек; очистка контейнеров ≤30 сек
- Доступность ≥99% в учебное время; RPO ≤24 ч; RTO ≤4 ч

### Имена таблиц PostgreSQL (канонические, из ТП §5 Рис. 21)

Каноническое имя — `learning_sessions` (не `sessions`). Таблица `agent_logs` в `.claude/agents/data.md` является артефактом — её **нет** в ТП, не создавать. Итого 14 таблиц:
`users`, `roles`, `user_roles`, `scenario_templates`, `scenario_runs`, `learning_sessions`, `session_events`, `hints`, `verification_results`, `reports`, `llm_providers`, `sandbox_profiles`, `audit_logs`, `security_events`

`session_events` обязана содержать 4 correlation-колонки: `session_id uuid`, `scenario_id uuid`, `user_id uuid`, `trace_id uuid`.

### Тесты
- Интеграционные тесты бьют в реальные БД, не моки (прецедент: мок-тесты не ловят проблемы миграций)
- Новый публичный API-контракт → тест обязателен до мержа

---

## Статус реализации (обновляется по ходу разработки)

| Фаза | Этапы | Статус |
|------|-------|--------|
| **Phase 0** | Scaffold: pyproject.toml, Next.js 16.2, docker-compose.dev.yml, sandbox Dockerfiles | ✅ Done |
| **Phase 1** | SQLAlchemy ORM (14 таблиц), Alembic 0001, DB clients, Neo4j constraints, Seed | ✅ Done |
| **Phase 2** | Pydantic schemas (11 файлов), FastAPI router stubs (10 + ws.py), 26 unit tests | ✅ Done |
| **Phase 3** | Auth/RBAC: JWT+bcrypt (security.py), deps (get_current_user/require_roles), auth routes (login/refresh/logout/me), user_service, audit_service, security_service; frontend: AuthProvider, login page, 401 interceptor | ✅ Done |
| **Phase 4** | LLM Gateway + ProfileAgent + ScenarioAgent + AssessmentAgent | 🔄 In progress |
| **Phase 5** | Sandbox Manager + WebSocket terminal + event channels | ⏳ Pending |
| **Phase 6** | Student/Teacher/Methodist/Admin UI | ⏳ Pending |
| **Phase 7** | Verification Engine + incidents + hints + reports | ⏳ Pending |
| **Phase 8** | Prometheus metrics + backup + CI/CD + smoke tests | ⏳ Pending |

**Деградированный старт (Phase 0–2):** `uvicorn app.main:app --reload --port 8000` стартует без БД —
каждый недоступный сервис логируется как WARNING, остальные endpoints возвращают `NOT_IMPLEMENTED`.
БД нужны начиная с Phase 3 (интеграционные тесты).

---

## Роли и права (RBAC)

| Код | Роль | Ключевые права |
|-----|------|---------------|
| `student` | Обучающийся | Запуск своих сценариев, подсказки, свои отчёты |
| `teacher` | Преподаватель | Просмотр групп, цифровой след, корректировка оценки с комментарием |
| `methodist` | Методист | Граф компетенций, шаблоны, checks, правила подсказок |
| `admin` | Администратор | Пользователи, роли, LLM-провайдеры, sandbox-профили, НСИ |
| `sysadmin` | Системный администратор | Инфраструктура, мониторинг, резервное копирование |
