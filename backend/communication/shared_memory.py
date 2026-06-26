"""Durable shared memory backed by PostgreSQL and Redis."""

from __future__ import annotations

import json
from typing import Any

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from backend.communication.message_types import FailureRecord, GenomeRecord

logger = structlog.get_logger(__name__)


class SharedMemory:
    """PostgreSQL is authoritative; Redis is an expiring state cache."""

    def __init__(
        self,
        redis_url: str,
        postgres_url: str,
        *,
        pool_size: int = 10,
        max_overflow: int = 20,
        create_schema: bool = True,
    ):
        self._redis_url = redis_url
        self._postgres_url = postgres_url
        self._pool_size = pool_size
        self._max_overflow = max_overflow
        self._create_schema = create_schema
        self._redis = None
        self._engine: AsyncEngine | None = None

    async def connect(self) -> None:
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(
            self._redis_url, decode_responses=True, health_check_interval=30
        )
        await self._redis.ping()
        self._engine = create_async_engine(
            self._postgres_url,
            pool_pre_ping=True,
            pool_size=self._pool_size,
            max_overflow=self._max_overflow,
        )
        async with self._engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        if self._create_schema:
            await self._ensure_schema()
        logger.info("shared_memory.connected")

    async def disconnect(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None

    async def _ensure_schema(self) -> None:
        engine = self._require_engine()
        statements = (
            """
            CREATE TABLE IF NOT EXISTS failure_memory (
                id UUID PRIMARY KEY,
                failure_type TEXT NOT NULL,
                root_cause TEXT NOT NULL,
                affected_code TEXT NOT NULL,
                fix_applied TEXT NOT NULL,
                agents_involved JSONB NOT NULL,
                severity SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 10),
                project_id TEXT NOT NULL,
                occurred_at TIMESTAMPTZ NOT NULL,
                tags JSONB NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS failure_memory_type_idx ON failure_memory (failure_type, severity DESC)",
            "CREATE INDEX IF NOT EXISTS failure_memory_tags_idx ON failure_memory USING GIN (tags)",
            """
            CREATE TABLE IF NOT EXISTS software_genomes (
                id UUID PRIMARY KEY,
                project_id TEXT NOT NULL,
                architecture_pattern TEXT NOT NULL,
                security_model TEXT NOT NULL,
                database_choice TEXT NOT NULL,
                deployment_target TEXT NOT NULL,
                performance_profile JSONB NOT NULL,
                success_rating DOUBLE PRECISION NOT NULL,
                created_at TIMESTAMPTZ NOT NULL
            )
            """,
            "CREATE INDEX IF NOT EXISTS software_genomes_lookup_idx ON software_genomes (architecture_pattern, database_choice, deployment_target, success_rating DESC)",
        )
        async with engine.begin() as connection:
            for statement in statements:
                await connection.execute(text(statement))

    async def set_state(self, key: str, value: Any, ttl: int = 3600) -> None:
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        redis = self._require_redis()
        await redis.set(
            f"state:{key}",
            json.dumps(value, separators=(",", ":"), default=str),
            ex=ttl,
        )

    async def get_state(self, key: str) -> Any | None:
        raw = await self._require_redis().get(f"state:{key}")
        return json.loads(raw) if raw is not None else None

    async def delete_state(self, key: str) -> None:
        await self._require_redis().delete(f"state:{key}")

    async def list_state_keys(self, pattern: str = "*") -> list[str]:
        redis = self._require_redis()
        keys: list[str] = []
        async for key in redis.scan_iter(match=f"state:{pattern}", count=500):
            keys.append(key.removeprefix("state:"))
        return keys

    async def record_failure(self, record: FailureRecord) -> None:
        query = text(
            """
            INSERT INTO failure_memory (
                id, failure_type, root_cause, affected_code, fix_applied,
                agents_involved, severity, project_id, occurred_at, tags
            ) VALUES (
                CAST(:id AS UUID), :failure_type, :root_cause, :affected_code,
                :fix_applied, CAST(:agents AS JSONB), :severity, :project_id,
                :occurred_at, CAST(:tags AS JSONB)
            )
            ON CONFLICT (id) DO UPDATE SET
                root_cause = EXCLUDED.root_cause,
                affected_code = EXCLUDED.affected_code,
                fix_applied = EXCLUDED.fix_applied,
                agents_involved = EXCLUDED.agents_involved,
                severity = EXCLUDED.severity,
                tags = EXCLUDED.tags
            """
        )
        async with self._require_engine().begin() as connection:
            await connection.execute(
                query,
                {
                    "id": record.id,
                    "failure_type": record.failure_type,
                    "root_cause": record.root_cause,
                    "affected_code": record.affected_code,
                    "fix_applied": record.fix_applied,
                    "agents": json.dumps(record.agents_involved),
                    "severity": record.severity,
                    "project_id": record.project_id,
                    "occurred_at": record.timestamp,
                    "tags": json.dumps(record.tags),
                },
            )

    async def search_failures(
        self,
        failure_type: str | None = None,
        tags: list[str] | None = None,
        min_severity: int = 1,
        limit: int = 10,
    ) -> list[FailureRecord]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        clauses = ["severity >= :min_severity"]
        params: dict[str, Any] = {"min_severity": min_severity, "limit": limit}
        if failure_type:
            clauses.append("failure_type = :failure_type")
            params["failure_type"] = failure_type
        if tags:
            clauses.append("tags ?| CAST(:tags AS TEXT[])")
            params["tags"] = tags
        query = text(
            f"""
            SELECT id, failure_type, root_cause, affected_code, fix_applied,
                   agents_involved, severity, project_id, occurred_at, tags
            FROM failure_memory
            WHERE {' AND '.join(clauses)}
            ORDER BY severity DESC, occurred_at DESC
            LIMIT :limit
            """
        )
        async with self._require_engine().connect() as connection:
            rows = (await connection.execute(query, params)).mappings().all()
        return [
            FailureRecord(
                id=str(row["id"]),
                failure_type=row["failure_type"],
                root_cause=row["root_cause"],
                affected_code=row["affected_code"],
                fix_applied=row["fix_applied"],
                agents_involved=row["agents_involved"],
                severity=row["severity"],
                project_id=row["project_id"],
                timestamp=row["occurred_at"],
                tags=row["tags"],
            )
            for row in rows
        ]

    async def get_similar_failures(
        self, description: str, limit: int = 5
    ) -> list[FailureRecord]:
        """Use PostgreSQL full-text ranking until an embedding provider is wired."""
        query = text(
            """
            SELECT id, failure_type, root_cause, affected_code, fix_applied,
                   agents_involved, severity, project_id, occurred_at, tags
            FROM failure_memory
            WHERE to_tsvector('english', failure_type || ' ' || root_cause || ' ' || affected_code)
                  @@ websearch_to_tsquery('english', :description)
            ORDER BY ts_rank(
                to_tsvector('english', failure_type || ' ' || root_cause || ' ' || affected_code),
                websearch_to_tsquery('english', :description)
            ) DESC, severity DESC
            LIMIT :limit
            """
        )
        async with self._require_engine().connect() as connection:
            rows = (
                await connection.execute(
                    query, {"description": description, "limit": limit}
                )
            ).mappings().all()
        return [
            FailureRecord(
                id=str(row["id"]),
                failure_type=row["failure_type"],
                root_cause=row["root_cause"],
                affected_code=row["affected_code"],
                fix_applied=row["fix_applied"],
                agents_involved=row["agents_involved"],
                severity=row["severity"],
                project_id=row["project_id"],
                timestamp=row["occurred_at"],
                tags=row["tags"],
            )
            for row in rows
        ]

    async def store_genome(self, genome: GenomeRecord) -> None:
        query = text(
            """
            INSERT INTO software_genomes (
                id, project_id, architecture_pattern, security_model,
                database_choice, deployment_target, performance_profile,
                success_rating, created_at
            ) VALUES (
                CAST(:id AS UUID), :project_id, :architecture, :security_model,
                :database, :deployment, CAST(:profile AS JSONB), :rating, :created_at
            )
            ON CONFLICT (id) DO UPDATE SET
                performance_profile = EXCLUDED.performance_profile,
                success_rating = EXCLUDED.success_rating
            """
        )
        async with self._require_engine().begin() as connection:
            await connection.execute(
                query,
                {
                    "id": genome.id,
                    "project_id": genome.project_id,
                    "architecture": genome.architecture_pattern,
                    "security_model": genome.security_model,
                    "database": genome.database_choice,
                    "deployment": genome.deployment_target,
                    "profile": json.dumps(genome.performance_profile),
                    "rating": genome.success_rating,
                    "created_at": genome.timestamp,
                },
            )

    async def find_similar_genomes(
        self,
        architecture: str = "",
        database: str = "",
        deployment: str = "",
        limit: int = 5,
    ) -> list[GenomeRecord]:
        clauses = ["1 = 1"]
        params: dict[str, Any] = {"limit": limit}
        for column, value in (
            ("architecture_pattern", architecture),
            ("database_choice", database),
            ("deployment_target", deployment),
        ):
            if value:
                clauses.append(f"{column} = :{column}")
                params[column] = value
        query = text(
            f"""
            SELECT * FROM software_genomes
            WHERE {' AND '.join(clauses)}
            ORDER BY success_rating DESC
            LIMIT :limit
            """
        )
        async with self._require_engine().connect() as connection:
            rows = (await connection.execute(query, params)).mappings().all()
        return [
            GenomeRecord(
                id=str(row["id"]),
                project_id=row["project_id"],
                architecture_pattern=row["architecture_pattern"],
                security_model=row["security_model"],
                database_choice=row["database_choice"],
                deployment_target=row["deployment_target"],
                performance_profile=row["performance_profile"],
                success_rating=row["success_rating"],
                timestamp=row["created_at"],
            )
            for row in rows
        ]

    async def get_stats(self) -> dict[str, int]:
        async with self._require_engine().connect() as connection:
            failures = await connection.scalar(text("SELECT count(*) FROM failure_memory"))
            genomes = await connection.scalar(text("SELECT count(*) FROM software_genomes"))
        state_keys = await self.list_state_keys()
        return {
            "failure_records": int(failures or 0),
            "genome_records": int(genomes or 0),
            "shared_state_keys": len(state_keys),
        }

    def _require_redis(self):
        if self._redis is None:
            raise RuntimeError("SharedMemory is not connected to Redis")
        return self._redis

    def _require_engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("SharedMemory is not connected to PostgreSQL")
        return self._engine
