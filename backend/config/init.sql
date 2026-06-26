-- AI Civilization — PostgreSQL Schema Initialization
-- This runs automatically on first docker-compose up

-- Enable pgvector for embedding similarity search
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ── Failure Memory Network ──────────────────────────────────────────
-- Stores every bug, root cause, fix, and impact forever.
-- Component 10.

CREATE TABLE IF NOT EXISTS failure_memory (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    failure_type TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    affected_code TEXT NOT NULL,
    fix_applied TEXT NOT NULL,
    agents_involved JSONB NOT NULL DEFAULT '[]',
    severity SMALLINT NOT NULL CHECK (severity BETWEEN 1 AND 10),
    project_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    tags JSONB NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS failure_memory_type_idx ON failure_memory (failure_type, severity DESC);
CREATE INDEX IF NOT EXISTS failure_memory_severity_idx ON failure_memory (severity DESC);
CREATE INDEX IF NOT EXISTS failure_memory_tags_idx ON failure_memory USING GIN (tags);
CREATE INDEX IF NOT EXISTS failure_memory_fts_idx ON failure_memory
    USING GIN (to_tsvector('english', failure_type || ' ' || root_cause || ' ' || affected_code));

-- ── Software Genome Database ────────────────────────────────────────
-- Stores successful architecture patterns for future reuse.
-- Component 8.

CREATE TABLE IF NOT EXISTS software_genomes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id TEXT NOT NULL,
    architecture_pattern TEXT NOT NULL,
    security_model TEXT NOT NULL,
    database_choice TEXT NOT NULL,
    deployment_target TEXT NOT NULL,
    performance_profile JSONB NOT NULL DEFAULT '{}',
    success_rating DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS software_genomes_lookup_idx
    ON software_genomes (architecture_pattern, database_choice, deployment_target, success_rating DESC);
CREATE INDEX IF NOT EXISTS software_genomes_rating_idx ON software_genomes (success_rating DESC);

-- ── Agent Registry ──────────────────────────────────────────────────
-- Tracks all agents in the civilization.

CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    specialization TEXT NOT NULL,
    dna JSONB NOT NULL DEFAULT '{}',
    state TEXT NOT NULL DEFAULT 'idle',
    credits DOUBLE PRECISION NOT NULL DEFAULT 100.0,
    reputation DOUBLE PRECISION NOT NULL DEFAULT 50.0,
    tasks_completed INTEGER NOT NULL DEFAULT 0,
    tasks_failed INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS agents_specialization_idx ON agents (specialization);
CREATE INDEX IF NOT EXISTS agents_reputation_idx ON agents (reputation DESC);

-- ── Agent Transaction Log ───────────────────────────────────────────
-- Economic transactions between agents.

CREATE TABLE IF NOT EXISTS agent_transactions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID NOT NULL REFERENCES agents(id),
    amount DOUBLE PRECISION NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    tx_type TEXT NOT NULL CHECK (tx_type IN ('credit', 'debit', 'reputation')),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS agent_transactions_agent_idx ON agent_transactions (agent_id, timestamp DESC);

-- ── Projects Table ──────────────────────────────────────────────────
-- Project specifications and their status.

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    goal_id UUID,
    title TEXT NOT NULL,
    project_type TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'interpreted',
    spec JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS projects_status_idx ON projects (status);
CREATE INDEX IF NOT EXISTS projects_type_idx ON projects (project_type);
