-- Chat history persistence (Router→Worker v3)
-- Requires pgcrypto for gen_random_uuid().

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, session_id)
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    citations JSONB,
    debug JSONB,
    completed BOOLEAN NOT NULL DEFAULT true,
    -- Stable per-turn identifier (aligns feedback/trace/references to the same turn).
    request_id TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id_created_at
ON messages(conversation_id, created_at);

-- Cursor pagination support for chat summary: (conversation_id, created_at, id)
CREATE INDEX IF NOT EXISTS idx_messages_conversation_created_id
ON messages(conversation_id, created_at, id);

-- Turn-level lookup (conversation_id + request_id).
CREATE INDEX IF NOT EXISTS idx_messages_conversation_request_id
ON messages(conversation_id, request_id);

-- User feedback (thumb up/down) for analytics and future tuning.
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id TEXT NOT NULL,
    query TEXT NOT NULL,
    is_positive BOOLEAN NOT NULL,
    thread_id TEXT NOT NULL,
    agent_type TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata JSONB
);

-- Ensure single feedback per message in a thread so UI can toggle/cancel.
CREATE UNIQUE INDEX IF NOT EXISTS idx_feedback_thread_message_id
ON feedback(thread_id, message_id);

CREATE INDEX IF NOT EXISTS idx_feedback_thread_id_created_at
ON feedback(thread_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feedback_created_at
ON feedback(created_at DESC);

-- Phase 1: sliding window + summary
CREATE TABLE IF NOT EXISTS conversation_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    summary_version INT NOT NULL DEFAULT 1,
    covered_through_message_id UUID,
    covered_through_created_at TIMESTAMP,
    covered_message_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(conversation_id)
);

CREATE INDEX IF NOT EXISTS idx_conversation_summaries_conversation_id
ON conversation_summaries(conversation_id);

-- Phase 2: Active Episodic Memory (semantic recall within a conversation)
-- Minimal baseline: store per-turn embeddings as JSONB (no pgvector required).
CREATE TABLE IF NOT EXISTS conversation_episodes (
    assistant_message_id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    user_message_id UUID NOT NULL,
    user_message TEXT NOT NULL,
    assistant_message TEXT NOT NULL,
    embedding JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conversation_episodes_conversation_created
ON conversation_episodes(conversation_id, created_at DESC);
