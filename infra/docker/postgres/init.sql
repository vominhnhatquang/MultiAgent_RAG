-- RAG Chatbot — PostgreSQL initialization
-- Runs once when the container is first created

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Configure PostgreSQL for memory efficiency
ALTER SYSTEM SET shared_buffers = '256MB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET maintenance_work_mem = '64MB';
ALTER SYSTEM SET max_connections = 20;
ALTER SYSTEM SET effective_cache_size = '512MB';
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET random_page_cost = 1.1;

-- Apply config changes
SELECT pg_reload_conf();

-- Create schema
CREATE SCHEMA IF NOT EXISTS rag;

-- Documents table
CREATE TABLE IF NOT EXISTS rag.documents (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,
    metadata    JSONB DEFAULT '{}',
    source_url  TEXT,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Chunks table with vector embeddings
CREATE TABLE IF NOT EXISTS rag.chunks (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES rag.documents(id) ON DELETE CASCADE,
    content     TEXT NOT NULL,
    embedding   vector(768),   -- nomic-embed-text dimension
    chunk_index INTEGER NOT NULL,
    metadata    JSONB DEFAULT '{}',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Conversations table
CREATE TABLE IF NOT EXISTS rag.conversations (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id    TEXT,
    title      TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Messages table
CREATE TABLE IF NOT EXISTS rag.messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES rag.conversations(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content         TEXT NOT NULL,
    metadata        JSONB DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON rag.chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON rag.chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON rag.documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON rag.messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON rag.documents USING gin(metadata);

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA rag TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA rag TO CURRENT_USER;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA rag TO CURRENT_USER;

\echo 'RAG database initialized successfully'
