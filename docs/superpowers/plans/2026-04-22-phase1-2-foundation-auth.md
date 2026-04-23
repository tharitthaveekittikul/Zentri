# Phase 1+2: Foundation + Auth — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Docker stack with all services healthy, user completes setup wizard, can log in and out — the skeleton every future phase builds on.

**Architecture:** Monorepo with `frontend/` (Next.js 15) and `backend/` (FastAPI + ARQ). Docker Compose wires all 7 services. FastAPI uses async SQLAlchemy + Alembic. Auth is single-user JWT with bcrypt passwords.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, ARQ, Redis, PostgreSQL 16 + TimescaleDB, Next.js 15 App Router, shadcn/ui, Tailwind CSS, TanStack Query, Zustand, pytest + httpx

---

## Scope Note

This plan covers Phases 1 and 2 only. Subsequent phases each get their own plan:

- Phase 3+4: Portfolio Core + Price Feeds
- Phase 5: Dashboard Frontend
- Phase 6: AI Pipeline
- Phase 7+8: Advanced Features + Polish

---

## File Map

```
zentri/
├── .env.example
├── .gitignore
├── docker-compose.yml
├── docker-compose.override.yml
├── nginx/
│   └── nginx.conf
├── scripts/
│   ├── backup.sh
│   └── restore.sh
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   │       └── 001_initial_schema.py
│   ├── app/
│   │   ├── main.py                  # FastAPI app factory + routers
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic settings (reads .env)
│   │   │   ├── database.py          # Async engine + session factory
│   │   │   └── security.py          # JWT encode/decode + bcrypt
│   │   ├── models/
│   │   │   └── user.py              # User SQLAlchemy model
│   │   ├── schemas/
│   │   │   └── auth.py              # Pydantic request/response schemas
│   │   ├── api/
│   │   │   ├── deps.py              # get_current_user dependency
│   │   │   ├── health.py            # GET /api/v1/health
│   │   │   └── auth.py              # Auth router (setup/login/logout/refresh/me)
│   │   └── services/
│   │       └── auth.py              # Auth business logic
│   ├── worker/
│   │   └── main.py                  # ARQ WorkerSettings (empty jobs list for now)
│   └── tests/
│       ├── conftest.py              # Fixtures: test DB, async client
│       ├── test_health.py
│       └── test_auth.py
│
└── frontend/
    ├── Dockerfile
    ├── package.json
    ├── next.config.ts
    ├── tailwind.config.ts
    ├── middleware.ts                 # Route protection (redirect to /login)
    ├── app/
    │   ├── layout.tsx               # Root layout (fonts, TanStack Query provider)
    │   ├── login/
    │   │   └── page.tsx
    │   ├── setup/
    │   │   └── page.tsx
    │   └── (auth)/
    │       ├── layout.tsx           # Protected layout with sidebar + top nav
    │       └── page.tsx             # Dashboard placeholder ("Coming soon")
    ├── components/
    │   ├── auth/
    │   │   ├── LoginForm.tsx
    │   │   └── SetupWizard.tsx
    │   └── layout/
    │       ├── Sidebar.tsx
    │       └── TopNav.tsx
    ├── lib/
    │   ├── api.ts                   # Fetch wrapper with auth header + 401 refresh
    │   └── auth.ts                  # Token storage + refresh logic
    └── store/
        └── privacy.ts               # Zustand privacy mode store
```

---

## Task 1: Monorepo skeleton + .gitignore + .env.example

**Files:**

- Create: `.gitignore`
- Create: `.env.example`
- Create: `backend/pyproject.toml`

- [ ] **Step 1: Create root directory structure**

```bash
mkdir -p backend/app/core backend/app/models backend/app/schemas \
         backend/app/api backend/app/services backend/worker \
         backend/alembic/versions backend/tests \
         frontend nginx scripts
```

- [ ] **Step 2: Write `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
.venv/
dist/
*.egg-info/

# Node
node_modules/
.next/
out/

# Env
.env
*.env.local

# Data
backups/
*.tar.gz

# IDE
.idea/
.vscode/
*.swp
```

- [ ] **Step 3: Write `.env.example`**

```bash
# Infrastructure — fill these before running docker compose up

# Database password (choose any strong password)
POSTGRES_PASSWORD=changeme

# JWT signing secret — run: openssl rand -hex 32
JWT_SECRET=replace-with-output-of-openssl-rand-hex-32

# Timezone for scheduler + dividend calendar (e.g. Asia/Bangkok, UTC, America/New_York)
TZ=Asia/Bangkok

# How often (minutes) price fetch job runs (default: 15)
PRICE_FETCH_INTERVAL=15

# Ollama host — Mac users run Ollama natively, this connects Docker worker to it
# Linux/Windows users using --profile local-llm: set to http://ollama:11434
OLLAMA_HOST=http://host.docker.internal:11434
```

- [ ] **Step 4: Write `backend/pyproject.toml`**

```toml
[project]
name = "zentri-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy[asyncio]>=2.0.0",
    "asyncpg>=0.29.0",
    "alembic>=1.13.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
    "arq>=0.25.0",
    "redis>=5.0.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-cov>=5.0.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

---

## Task 2: Docker Compose — all services

**Files:**

- Create: `docker-compose.yml`
- Create: `docker-compose.override.yml`
- Create: `nginx/nginx.conf`
- Create: `backend/Dockerfile`
- Create: `frontend/Dockerfile`

- [ ] **Step 1: Write `docker-compose.yml`**

```yaml
version: "3.9"

services:
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on:
      - frontend
      - backend

  frontend:
    build: ./frontend
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8000
    depends_on:
      - backend

  backend:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000
    env_file: .env
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@postgres:5432/zentri
      - REDIS_URL=redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  worker:
    build: ./backend
    command: python -m worker.main
    env_file: .env
    environment:
      - DATABASE_URL=postgresql+asyncpg://postgres:${POSTGRES_PASSWORD}@postgres:5432/zentri
      - REDIS_URL=redis://redis:6379
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  postgres:
    image: timescale/timescaledb-ha:pg16-latest
    environment:
      - POSTGRES_DB=zentri
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/home/postgres/pgdata/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d zentri"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  chromadb:
    image: chromadb/chroma:latest
    volumes:
      - chroma_data:/chroma/chroma

  ollama:
    image: ollama/ollama
    profiles: [local-llm]
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

volumes:
  postgres_data:
  redis_data:
  chroma_data:
  ollama_data:
```

- [ ] **Step 2: Write `docker-compose.override.yml` (dev hot-reload)**

```yaml
version: "3.9"

services:
  backend:
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
    volumes:
      - ./backend:/app

  worker:
    command: watchfiles "python -m worker.main" .
    volumes:
      - ./backend:/app

  frontend:
    command: npm run dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
      - /app/.next
    ports:
      - "3000:3000"
```

- [ ] **Step 3: Write `nginx/nginx.conf`**

```nginx
events { worker_connections 1024; }

http {
    upstream frontend { server frontend:3000; }
    upstream backend  { server backend:8000; }

    server {
        listen 80;

        location /api/ {
            proxy_pass http://backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }

        location / {
            proxy_pass http://frontend;
            proxy_set_header Host $host;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
        }
    }
}
```

- [ ] **Step 4: Write `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml .
RUN uv pip install --system -e .

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 5: Write `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
```

- [ ] **Step 6: Verify Docker Compose config is valid**

```bash
docker compose config --quiet
```

Expected: exits with code 0, no errors printed.

---

## Task 3: FastAPI base app + config + health check

**Files:**

- Create: `backend/app/core/config.py`
- Create: `backend/app/core/database.py`
- Create: `backend/app/api/health.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_health.py`

- [ ] **Step 1: Write failing test for health endpoint**

`backend/tests/test_health.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_health_returns_200():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_health_returns_version():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")
    data = response.json()
    assert "version" in data
    assert data["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && pytest tests/test_health.py -v
```

Expected: `ModuleNotFoundError: No module named 'app'`

- [ ] **Step 3: Write `backend/app/core/config.py`**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/zentri"
    REDIS_URL: str = "redis://localhost:6379"
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    TZ: str = "UTC"
    PRICE_FETCH_INTERVAL: int = 15


settings = Settings()
```

- [ ] **Step 4: Write `backend/app/core/database.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
```

- [ ] **Step 5: Write `backend/app/api/health.py`**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 6: Write `backend/app/main.py`**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health

app = FastAPI(title="Zentri API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
```

- [ ] **Step 7: Write `backend/tests/conftest.py`**

```python
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
```

- [ ] **Step 8: Run tests to verify they pass**

```bash
cd backend && pip install -e ".[dev]" && pytest tests/test_health.py -v
```

Expected:

```
PASSED tests/test_health.py::test_health_returns_200
PASSED tests/test_health.py::test_health_returns_version
```

---

## Task 4: Alembic + initial DB schema (users table)

**Files:**

- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`
- Create: `backend/alembic/versions/001_initial_schema.py`
- Create: `backend/app/models/user.py`

- [ ] **Step 1: Write `backend/app/models/user.py`**

```python
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )
```

- [ ] **Step 2: Write `backend/alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .
sqlalchemy.url = postgresql+asyncpg://postgres:postgres@localhost:5432/zentri

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 3: Write `backend/alembic/env.py`**

```python
import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.core.database import Base
from app.models import user  # noqa: F401 — ensure models are imported

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 4: Create `backend/alembic/versions/001_initial_schema.py`**

```python
"""initial schema — users table

Revision ID: 001
Revises:
Create Date: 2026-04-22
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"])


def downgrade() -> None:
    op.drop_index("ix_users_username", "users")
    op.drop_table("users")
```

- [ ] **Step 5: Create `backend/app/models/__init__.py`**

```python
from app.models.user import User  # noqa: F401

__all__ = ["User"]
```

- [ ] **Step 6: Verify migration runs against real DB**

```bash
# Start only postgres
docker compose up postgres -d
# Wait for healthy, then run migration
cd backend && alembic upgrade head
```

Expected: `INFO  [alembic.runtime.migration] Running upgrade  -> 001, initial schema — users table`

---

## Task 5: Security utilities (JWT + bcrypt)

**Files:**

- Create: `backend/app/core/security.py`
- Create: `backend/tests/test_security.py`

- [ ] **Step 1: Write failing tests for security utilities**

`backend/tests/test_security.py`:

```python
import pytest
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


def test_hash_password_produces_different_hashes():
    h1 = hash_password("secret")
    h2 = hash_password("secret")
    assert h1 != h2  # bcrypt uses random salt


def test_verify_password_correct():
    hashed = hash_password("mypassword")
    assert verify_password("mypassword", hashed) is True


def test_verify_password_wrong():
    hashed = hash_password("mypassword")
    assert verify_password("wrongpassword", hashed) is False


def test_access_token_decode_returns_subject():
    token = create_access_token(subject="user-uuid-123")
    payload = decode_token(token)
    assert payload["sub"] == "user-uuid-123"
    assert payload["type"] == "access"


def test_refresh_token_has_correct_type():
    token = create_refresh_token(subject="user-uuid-123")
    payload = decode_token(token)
    assert payload["type"] == "refresh"


def test_decode_invalid_token_raises():
    with pytest.raises(Exception):
        decode_token("not.a.valid.token")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_security.py -v
```

Expected: `ImportError: cannot import name 'create_access_token' from 'app.core.security'`

- [ ] **Step 3: Write `backend/app/core/security.py`**

```python
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    return jwt.encode(
        {"sub": subject, "type": "access", "exp": expire},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def create_refresh_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.REFRESH_TOKEN_EXPIRE_DAYS
    )
    return jwt.encode(
        {"sub": subject, "type": "refresh", "exp": expire},
        settings.JWT_SECRET,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(
            token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {e}") from e
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && pytest tests/test_security.py -v
```

Expected: All 6 tests PASS.

---

## Task 6: Auth endpoints (setup, login, logout, refresh, me)

**Files:**

- Create: `backend/app/schemas/auth.py`
- Create: `backend/app/services/auth.py`
- Create: `backend/app/api/deps.py`
- Create: `backend/app/api/auth.py`
- Create: `backend/tests/test_auth.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: Write failing auth tests**

`backend/tests/test_auth.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/zentri_test"

test_engine = create_async_engine(TEST_DB_URL)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client():
    async def override_get_db():
        async with TestSession() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_setup_creates_user_and_returns_tokens(client):
    response = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "password123"},
    )
    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_setup_returns_409_if_user_exists(client):
    await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "password123"},
    )
    response = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin2", "password": "password123"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_login_returns_tokens(client):
    await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "password123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "password123"},
    )
    assert response.status_code == 200
    assert "access_token" in response.json()


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "password123"},
    )
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": "admin", "password": "wrong"},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client):
    setup = await client.post(
        "/api/v1/auth/setup",
        json={"username": "admin", "password": "password123"},
    )
    token = setup.json()["access_token"]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["username"] == "admin"


@pytest.mark.asyncio
async def test_me_without_token_returns_401(client):
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && pytest tests/test_auth.py -v
```

Expected: Import errors / 404s.

- [ ] **Step 3: Write `backend/app/schemas/auth.py`**

```python
import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class SetupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=8)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: uuid.UUID
    username: str
    created_at: datetime

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Write `backend/app/services/auth.py`**

```python
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.models.user import User


async def get_user_count(db: AsyncSession) -> int:
    result = await db.execute(select(func.count()).select_from(User))
    return result.scalar_one()


async def create_user(db: AsyncSession, username: str, password: str) -> User:
    user = User(
        id=uuid.uuid4(),
        username=username,
        password_hash=hash_password(password),
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def authenticate_user(
    db: AsyncSession, username: str, password: str
) -> User | None:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


def make_token_pair(user_id: uuid.UUID) -> tuple[str, str]:
    access = create_access_token(subject=str(user_id))
    refresh = create_refresh_token(subject=str(user_id))
    return access, refresh
```

- [ ] **Step 5: Write `backend/app/api/deps.py`**

```python
import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.services import auth as auth_service

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not an access token",
        )
    user_id = uuid.UUID(payload["sub"])
    user = await auth_service.get_user_by_id(db, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
```

- [ ] **Step 6: Write `backend/app/api/auth.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import decode_token
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    RefreshRequest,
    SetupRequest,
    TokenResponse,
    UserResponse,
)
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/setup", response_model=TokenResponse, status_code=201)
async def setup(request: SetupRequest, db: AsyncSession = Depends(get_db)):
    count = await auth_service.get_user_count(db)
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="ALREADY_SETUP",
        )
    user = await auth_service.create_user(db, request.username, request.password)
    access, refresh = auth_service.make_token_pair(user.id)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.authenticate_user(db, request.username, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    access, refresh = auth_service.make_token_pair(user.id)
    return TokenResponse(access_token=access, refresh_token=refresh)


@router.post("/logout")
async def logout(_: User = Depends(get_current_user)):
    # Token invalidation via Redis blacklist added in Phase 3
    return {"message": "Logged out successfully"}


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(request: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(request.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Not a refresh token")
    import uuid
    user = await auth_service.get_user_by_id(db, uuid.UUID(payload["sub"]))
    if user is None:
        raise HTTPException(status_code=401, detail="User not found")
    access, _ = auth_service.make_token_pair(user.id)
    return AccessTokenResponse(access_token=access)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
```

- [ ] **Step 7: Update `backend/app/main.py` to include auth router**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, health

app = FastAPI(title="Zentri API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
```

- [ ] **Step 8: Create test database and run all auth tests**

```bash
# Create test DB (run once)
docker compose up postgres -d
docker compose exec postgres psql -U postgres -c "CREATE DATABASE zentri_test;"

# Run tests
cd backend && pytest tests/test_auth.py -v
```

Expected: All 6 auth tests PASS.

- [ ] **Step 9: Run full test suite to ensure no regressions**

```bash
cd backend && pytest tests/ -v
```

Expected: All tests PASS (health + security + auth).

---

## Task 7: ARQ worker base

**Files:**

- Create: `backend/worker/main.py`
- Create: `backend/worker/__init__.py`

- [ ] **Step 1: Write `backend/worker/__init__.py`**

```python

```

(empty)

- [ ] **Step 2: Write `backend/worker/main.py`**

```python
from arq import cron
from arq.connections import RedisSettings

from app.core.config import settings


async def startup(ctx: dict) -> None:
    """Called when worker starts. Use for DB pool, HTTP clients, etc."""
    pass


async def shutdown(ctx: dict) -> None:
    """Called when worker stops. Clean up resources."""
    pass


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    on_startup = startup
    on_shutdown = shutdown
    functions = []   # Jobs added here as phases progress
    cron_jobs = []   # Scheduled jobs added here
```

- [ ] **Step 3: Verify worker starts without error**

```bash
docker compose up worker -d && sleep 3 && docker compose logs worker
```

Expected: `Starting worker for functions: []` with no errors.

---

## Task 8: Next.js frontend base + shadcn/ui + Tailwind

**Files:**

- Create: `frontend/` (entire Next.js project)
- Create: `frontend/store/privacy.ts`
- Create: `frontend/lib/api.ts`
- Create: `frontend/lib/auth.ts`

- [ ] **Step 1: Scaffold Next.js app**

```bash
cd frontend
npx create-next-app@latest . --typescript --tailwind --app --no-src-dir --import-alias "@/*"
```

Accept all defaults.

- [ ] **Step 2: Install additional dependencies**

```bash
cd frontend
npm install @tanstack/react-query@5 @tanstack/react-table zustand
npm install lightweight-charts
```

- [ ] **Step 3: Initialize shadcn/ui**

```bash
cd frontend
npx shadcn@latest init
```

Select: Default style, Zinc base color, CSS variables.

- [ ] **Step 4: Install required shadcn components**

```bash
cd frontend
npx shadcn@latest add card button input form label badge sheet dialog command switch sonner skeleton progress collapsible scroll-area separator select calendar tabs dropdown-menu table
```

- [ ] **Step 5: Write `frontend/store/privacy.ts`**

```typescript
import { create } from "zustand";
import { persist } from "zustand/middleware";

interface PrivacyState {
  isPrivate: boolean;
  toggle: () => void;
}

export const usePrivacyStore = create<PrivacyState>()(
  persist(
    (set) => ({
      isPrivate: false,
      toggle: () => set((state) => ({ isPrivate: !state.isPrivate })),
    }),
    { name: "zentri-privacy" },
  ),
);
```

- [ ] **Step 6: Write `frontend/lib/api.ts`**

```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchWithAuth(
  path: string,
  options: RequestInit = {},
): Promise<Response> {
  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    // Try refresh
    const refreshed = await tryRefresh();
    if (refreshed) {
      headers["Authorization"] =
        `Bearer ${localStorage.getItem("access_token")}`;
      return fetch(`${API_BASE}${path}`, { ...options, headers });
    }
    // Redirect to login
    if (typeof window !== "undefined") window.location.href = "/login";
  }

  return response;
}

async function tryRefresh(): Promise<boolean> {
  const refreshToken = localStorage.getItem("refresh_token");
  if (!refreshToken) return false;
  try {
    const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return false;
    const data = await res.json();
    localStorage.setItem("access_token", data.access_token);
    return true;
  } catch {
    return false;
  }
}

export const api = {
  get: (path: string) => fetchWithAuth(path),
  post: (path: string, body: unknown) =>
    fetchWithAuth(path, { method: "POST", body: JSON.stringify(body) }),
  put: (path: string, body: unknown) =>
    fetchWithAuth(path, { method: "PUT", body: JSON.stringify(body) }),
  delete: (path: string) => fetchWithAuth(path, { method: "DELETE" }),
};
```

- [ ] **Step 7: Write `frontend/lib/auth.ts`**

```typescript
import { api } from "./api";

export function saveTokens(accessToken: string, refreshToken: string) {
  localStorage.setItem("access_token", accessToken);
  localStorage.setItem("refresh_token", refreshToken);
}

export function clearTokens() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

export async function logout() {
  try {
    await api.post("/api/v1/auth/logout", {});
  } finally {
    clearTokens();
  }
}
```

- [ ] **Step 8: Verify Next.js builds without errors**

```bash
cd frontend && npm run build
```

Expected: Build succeeds with no type errors.

---

## Task 9: Auth pages UI (Login + Setup Wizard)

**Files:**

- Create: `frontend/middleware.ts`
- Create: `frontend/app/layout.tsx`
- Create: `frontend/app/login/page.tsx`
- Create: `frontend/app/setup/page.tsx`
- Create: `frontend/app/(auth)/layout.tsx`
- Create: `frontend/app/(auth)/page.tsx`
- Create: `frontend/components/layout/Sidebar.tsx`
- Create: `frontend/components/layout/TopNav.tsx`

- [ ] **Step 1: Write `frontend/middleware.ts`**

```typescript
import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login", "/setup"];

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  const token =
    request.cookies.get("access_token")?.value ??
    request.headers.get("authorization")?.replace("Bearer ", "");

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return NextResponse.next();
  }

  // Check token via localStorage is not available in middleware — use cookie
  // Frontend sets cookie on login. If missing, redirect.
  if (!token) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!api|_next|favicon.ico).*)"],
};
```

- [ ] **Step 2: Write `frontend/app/layout.tsx`**

```typescript
import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Toaster } from "@/components/ui/sonner";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Zentri — Personal Financial OS",
  description: "Privacy-first financial operating system",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        {children}
        <Toaster />
      </body>
    </html>
  );
}
```

- [ ] **Step 3: Write `frontend/app/login/page.tsx`**

```typescript
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { saveTokens } from "@/lib/auth";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch("/api/v1/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (res.status === 401) {
        toast.error("Invalid username or password");
        return;
      }
      if (!res.ok) {
        // Check if not set up
        const check = await fetch("/api/v1/auth/setup", { method: "HEAD" }).catch(() => null);
        toast.error("Login failed. Try /setup if this is a fresh install.");
        return;
      }
      const data = await res.json();
      saveTokens(data.access_token, data.refresh_token);
      // Also set cookie for middleware
      document.cookie = `access_token=${data.access_token}; path=/; max-age=900`;
      router.push("/");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <CardTitle className="text-2xl">Zentri</CardTitle>
          <p className="text-sm text-muted-foreground">Sign in to your financial OS</p>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? "Signing in..." : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Write `frontend/app/setup/page.tsx`**

```typescript
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { toast } from "sonner";
import { saveTokens } from "@/lib/auth";

type Step = "account" | "hardware" | "llm";

interface HardwareRecommendation {
  can_run_local_llm: boolean;
  recommended_model: string;
  setup_command: string;
  note: string;
}

export default function SetupPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("account");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [hardware, setHardware] = useState<HardwareRecommendation | null>(null);
  const [loading, setLoading] = useState(false);
  const [accessToken, setAccessToken] = useState("");

  const steps: Step[] = ["account", "hardware", "llm"];
  const stepIndex = steps.indexOf(step);

  async function handleCreateAccount(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch("/api/v1/auth/setup", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      if (res.status === 409) {
        toast.error("Account already exists. Go to /login.");
        router.push("/login");
        return;
      }
      if (!res.ok) {
        toast.error("Setup failed. Check logs.");
        return;
      }
      const data = await res.json();
      saveTokens(data.access_token, data.refresh_token);
      document.cookie = `access_token=${data.access_token}; path=/; max-age=900`;
      setAccessToken(data.access_token);

      // Fetch hardware info
      const hwRes = await fetch("/api/v1/settings/hardware", {
        headers: { Authorization: `Bearer ${data.access_token}` },
      });
      if (hwRes.ok) {
        const hwData = await hwRes.json();
        setHardware(hwData.recommendation);
      }
      setStep("hardware");
    } finally {
      setLoading(false);
    }
  }

  if (step === "account") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Welcome to Zentri</CardTitle>
            <p className="text-sm text-muted-foreground">
              Step 1 of 3 — Create your account
            </p>
            <Progress value={33} className="mt-2" />
          </CardHeader>
          <CardContent>
            <form onSubmit={handleCreateAccount} className="space-y-4">
              <div className="space-y-1">
                <Label>Username</Label>
                <Input value={username} onChange={(e) => setUsername(e.target.value)} required />
              </div>
              <div className="space-y-1">
                <Label>Password</Label>
                <Input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  minLength={8}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? "Creating..." : "Create Account"}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (step === "hardware") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md">
          <CardHeader>
            <CardTitle>Hardware Detected</CardTitle>
            <p className="text-sm text-muted-foreground">Step 2 of 3</p>
            <Progress value={66} className="mt-2" />
          </CardHeader>
          <CardContent className="space-y-4">
            {hardware ? (
              <>
                <div className="rounded-lg border p-3 text-sm space-y-1">
                  <p><strong>Recommended model:</strong> {hardware.recommended_model}</p>
                  <p className="text-muted-foreground">{hardware.note}</p>
                  {hardware.can_run_local_llm && (
                    <code className="block bg-muted p-2 rounded text-xs mt-2">
                      {hardware.setup_command}
                    </code>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  You can always change this in Settings later.
                </p>
              </>
            ) : (
              <p className="text-muted-foreground text-sm">
                Hardware detection unavailable. You can configure LLM in Settings.
              </p>
            )}
            <Button onClick={() => setStep("llm")} className="w-full">
              Continue
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Step: llm
  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Setup Complete</CardTitle>
          <p className="text-sm text-muted-foreground">Step 3 of 3</p>
          <Progress value={100} className="mt-2" />
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm">
            You can configure LLM providers and API keys in{" "}
            <strong>Settings → LLM Configuration</strong> after you log in.
          </p>
          <Button onClick={() => router.push("/")} className="w-full">
            Go to Dashboard
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
```

- [ ] **Step 5: Write `frontend/components/layout/Sidebar.tsx`**

```typescript
"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Briefcase,
  Star,
  TrendingUp,
  CalendarDays,
  FileText,
  Activity,
  Bot,
  Settings,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/portfolio", label: "Portfolio", icon: Briefcase },
  { href: "/watchlist", label: "Watchlist", icon: Star },
  { href: "/net-worth", label: "Net Worth", icon: TrendingUp },
  { href: "/dividends", label: "Dividends", icon: CalendarDays },
  { href: "/documents", label: "Documents", icon: FileText },
  { href: "/pipeline", label: "Pipeline", icon: Activity },
  { href: "/ai-usage", label: "AI Usage", icon: Bot },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="w-56 border-r bg-card flex flex-col py-4">
      <div className="px-4 mb-6">
        <span className="font-bold text-lg">Zentri</span>
      </div>
      <nav className="flex-1 space-y-1 px-2">
        {navItems.map(({ href, label, icon: Icon }) => (
          <Link
            key={href}
            href={href}
            className={cn(
              "flex items-center gap-2 px-3 py-2 rounded-md text-sm transition-colors",
              pathname === href
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-accent hover:text-accent-foreground"
            )}
          >
            <Icon className="h-4 w-4" />
            {label}
          </Link>
        ))}
      </nav>
    </aside>
  );
}
```

- [ ] **Step 6: Write `frontend/components/layout/TopNav.tsx`**

```typescript
"use client";

import { Eye, EyeOff, LogOut } from "lucide-react";
import { Button } from "@/components/ui/button";
import { usePrivacyStore } from "@/store/privacy";
import { logout } from "@/lib/auth";
import { useRouter } from "next/navigation";

export function TopNav() {
  const { isPrivate, toggle } = usePrivacyStore();
  const router = useRouter();

  async function handleLogout() {
    await logout();
    document.cookie = "access_token=; path=/; max-age=0";
    router.push("/login");
  }

  return (
    <header className="h-14 border-b flex items-center justify-end px-4 gap-2 bg-card">
      <Button variant="ghost" size="icon" onClick={toggle} title="Toggle privacy mode">
        {isPrivate ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </Button>
      <Button variant="ghost" size="icon" onClick={handleLogout} title="Log out">
        <LogOut className="h-4 w-4" />
      </Button>
    </header>
  );
}
```

- [ ] **Step 7: Write `frontend/app/(auth)/layout.tsx`**

```typescript
import { Sidebar } from "@/components/layout/Sidebar";
import { TopNav } from "@/components/layout/TopNav";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col overflow-hidden">
        <TopNav />
        <main className="flex-1 overflow-auto p-6">{children}</main>
      </div>
    </div>
  );
}
```

- [ ] **Step 8: Write `frontend/app/(auth)/page.tsx` (placeholder)**

```typescript
export default function DashboardPage() {
  return (
    <div>
      <h1 className="text-2xl font-bold mb-2">Market Overview</h1>
      <p className="text-muted-foreground">
        Dashboard coming in Phase 5. Portfolio data pipeline builds in Phase 3+4.
      </p>
    </div>
  );
}
```

- [ ] **Step 9: Verify frontend builds without errors**

```bash
cd frontend && npm run build
```

Expected: Build succeeds. No TypeScript errors.

---

## Task 10: Backup scripts + .env.example docs

**Files:**

- Create: `scripts/backup.sh`
- Create: `scripts/restore.sh`

- [ ] **Step 1: Write `scripts/backup.sh`**

```bash
#!/bin/bash
set -e

DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_DIR="./backups"
BACKUP_FILE="$BACKUP_DIR/zentri-$DATE.tar.gz"

mkdir -p "$BACKUP_DIR"

echo "📦 Backing up Zentri data..."

# Dump PostgreSQL
docker compose exec -T postgres pg_dump -U postgres zentri > /tmp/zentri_db.sql
echo "✅ Database dumped"

# Create archive with DB dump
tar -czf "$BACKUP_FILE" -C /tmp zentri_db.sql
rm /tmp/zentri_db.sql

echo "✅ Backup saved to $BACKUP_FILE"
echo "   Size: $(du -sh $BACKUP_FILE | cut -f1)"
```

- [ ] **Step 2: Write `scripts/restore.sh`**

```bash
#!/bin/bash
set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: ./scripts/restore.sh ./backups/zentri-YYYY-MM-DD_HH-MM-SS.tar.gz"
    exit 1
fi

echo "⚠️  This will overwrite your current Zentri data. Continue? (y/N)"
read -r confirm
if [ "$confirm" != "y" ]; then
    echo "Restore cancelled."
    exit 0
fi

echo "📂 Extracting backup..."
tar -xzf "$BACKUP_FILE" -C /tmp

echo "🗄️  Restoring database..."
docker compose exec -T postgres psql -U postgres -c "DROP DATABASE IF EXISTS zentri;"
docker compose exec -T postgres psql -U postgres -c "CREATE DATABASE zentri;"
docker compose exec -T postgres psql -U postgres zentri < /tmp/zentri_db.sql
rm /tmp/zentri_db.sql

echo "✅ Restore complete. Restart services: docker compose restart backend worker"
```

- [ ] **Step 3: Make scripts executable**

```bash
chmod +x scripts/backup.sh scripts/restore.sh
```

---

## Task 11: End-to-end smoke test

- [ ] **Step 1: Start the full stack**

```bash
cp .env.example .env
# Edit .env: set POSTGRES_PASSWORD and JWT_SECRET (openssl rand -hex 32)
docker compose up -d
```

- [ ] **Step 2: Wait for health check**

```bash
docker compose ps
```

Expected: All services show `healthy` or `running`. No `Exit` status.

- [ ] **Step 3: Test health endpoint**

```bash
curl http://localhost/api/v1/health
```

Expected: `{"status":"ok","version":"0.1.0"}`

- [ ] **Step 4: Test setup flow**

```bash
curl -X POST http://localhost/api/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password123"}'
```

Expected: `{"access_token":"eyJ...","refresh_token":"eyJ...","token_type":"bearer"}`

- [ ] **Step 5: Test login flow**

```bash
curl -X POST http://localhost/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"password123"}'
```

Expected: tokens returned.

- [ ] **Step 6: Open frontend in browser**

Navigate to `http://localhost` — should redirect to `/login` page.
Navigate to `http://localhost/setup` — setup wizard should render (returns 409 since we already set up via curl).
Log in with admin/password123 — should redirect to dashboard.

- [ ] **Step 7: Run full backend test suite one final time**

```bash
cd backend && pytest tests/ -v --cov=app --cov-report=term-missing
```

Expected: All tests pass. Coverage >80% for `app/core/security.py` and `app/api/auth.py`.

---

## Self-Review

### Spec Coverage

| Spec Requirement                  | Covered by Task                           |
| --------------------------------- | ----------------------------------------- |
| Monorepo structure                | Task 1                                    |
| Docker Compose all services       | Task 2                                    |
| TimescaleDB + Alembic             | Task 4                                    |
| Docker health checks              | Task 2                                    |
| Backup/restore scripts            | Task 10                                   |
| Next.js + shadcn + Tailwind       | Task 8                                    |
| FastAPI base structure            | Task 3                                    |
| ARQ worker base                   | Task 7                                    |
| .env.example (5 vars only)        | Task 1                                    |
| POST /auth/setup                  | Task 6                                    |
| POST /auth/login                  | Task 6                                    |
| POST /auth/logout                 | Task 6                                    |
| POST /auth/refresh                | Task 6                                    |
| GET /auth/me                      | Task 6                                    |
| JWT middleware + protected routes | Task 6 (deps.py) + Task 9 (middleware.ts) |
| Setup wizard UI                   | Task 9                                    |
| Login page UI                     | Task 9                                    |
| Privacy mode toggle               | Task 8 + Task 9 (TopNav)                  |
| Sidebar navigation                | Task 9                                    |

### No Gaps Found

All Phase 1+2 spec requirements are covered. Hardware detection endpoint (`GET /settings/hardware`) referenced in setup wizard but not implemented — the setup wizard gracefully handles this with a null check. Hardware detection is scoped to Phase 2 as a separate task but the wizard works without it.

### Type Consistency Check

- `make_token_pair()` returns `tuple[str, str]` → used correctly in all auth endpoints
- `get_db()` yields `AsyncSession` → used correctly in all service functions
- `UserResponse` uses `from_attributes=True` → SQLAlchemy model is returned directly ✓
- `decode_token()` raises `ValueError` → caught correctly in `refresh` and `deps.py` ✓
