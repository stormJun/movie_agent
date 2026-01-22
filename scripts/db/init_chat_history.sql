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
    debug JSONB
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id_created_at
ON messages(conversation_id, created_at);

-- User feedback (thumb up/down) for analytics and future tuning.
CREATE TABLE IF NOT EXISTS feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id TEXT,
    query TEXT NOT NULL,
    is_positive BOOLEAN NOT NULL,
    thread_id TEXT NOT NULL,
    agent_type TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_feedback_thread_id_created_at
ON feedback(thread_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_feedback_created_at
ON feedback(created_at DESC);
