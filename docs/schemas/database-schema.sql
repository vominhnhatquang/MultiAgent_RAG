-- ============================================================
-- RAG Chatbot 10GB - PostgreSQL 16 + pgvector Database Schema
-- Author: Alpha (System Architect)
-- Version: 1.0 (All phases combined, evolution markers noted)
-- ============================================================

-- ============================================================
-- EXTENSIONS
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";    -- UUID generation
CREATE EXTENSION IF NOT EXISTS "vector";       -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS "pg_trgm";      -- Trigram index for fuzzy search

-- ============================================================
-- PHASE 1: CORE TABLES
-- ============================================================

-- Documents: uploaded files metadata
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    file_type VARCHAR(20) NOT NULL,             -- pdf, docx, md
    file_size_bytes BIGINT NOT NULL,
    file_hash VARCHAR(64),                       -- SHA-256 for dedup
    status VARCHAR(20) NOT NULL DEFAULT 'processing',
        -- processing: being ingested
        -- indexed: ready for search
        -- error: ingestion failed
        -- deleted: soft delete
    chunk_count INTEGER DEFAULT 0,
    error_message TEXT,                           -- if status = error
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_documents_status
        CHECK (status IN ('processing', 'indexed', 'error', 'deleted')),
    CONSTRAINT chk_documents_file_type
        CHECK (file_type IN ('pdf', 'docx', 'md', 'txt'))
);

CREATE INDEX idx_documents_status ON documents(status);
CREATE INDEX idx_documents_created_at ON documents(created_at DESC);
CREATE UNIQUE INDEX idx_documents_file_hash ON documents(file_hash)
    WHERE file_hash IS NOT NULL AND status != 'deleted';

-- Chunks: text chunks with embeddings
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding VECTOR(768),                       -- nomic-embed-text dimension
    chunk_index INTEGER NOT NULL,                -- order within document
    page_number INTEGER,                         -- source page (PDF)
    token_count INTEGER,
    char_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_chunks_index CHECK (chunk_index >= 0)
);

CREATE INDEX idx_chunks_document_id ON chunks(document_id);
CREATE INDEX idx_chunks_page ON chunks(document_id, page_number);

-- pgvector index for similarity search (fallback when Qdrant unavailable)
CREATE INDEX idx_chunks_embedding ON chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Chat sessions
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255),                          -- auto-generated or user-set
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_sessions_updated_at ON sessions(updated_at DESC);

-- Chat messages
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(10) NOT NULL,                   -- user, assistant, system
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_messages_role CHECK (role IN ('user', 'assistant', 'system'))
);

CREATE INDEX idx_messages_session_id ON messages(session_id);
CREATE INDEX idx_messages_created_at ON messages(session_id, created_at);

-- ============================================================
-- PHASE 2: INTELLIGENCE ADDITIONS
-- ============================================================

-- Add mode to sessions (strict/general)
ALTER TABLE sessions ADD COLUMN mode VARCHAR(10) NOT NULL DEFAULT 'strict';
ALTER TABLE sessions ADD CONSTRAINT chk_sessions_mode
    CHECK (mode IN ('strict', 'general'));

-- Add metadata to chunks (section, keywords, language)
ALTER TABLE chunks ADD COLUMN metadata JSONB DEFAULT '{}';
-- metadata schema:
-- {
--   "section": "Chapter 2: Methods",
--   "keywords": ["regression", "analysis"],
--   "language": "en"
-- }

-- GIN index on chunk metadata for filtering
CREATE INDEX idx_chunks_metadata ON chunks USING GIN (metadata);

-- BM25 full-text search index
CREATE INDEX idx_chunks_content_fts ON chunks
    USING GIN (to_tsvector('simple', content));

-- Add source references to messages
ALTER TABLE messages ADD COLUMN sources JSONB;
-- sources schema:
-- [
--   {"doc_id": "uuid", "filename": "report.pdf", "page": 5, "score": 0.85},
--   {"doc_id": "uuid", "filename": "data.pdf", "page": 12, "score": 0.78}
-- ]

-- Add model info to assistant messages
ALTER TABLE messages ADD COLUMN model_used VARCHAR(50);
-- e.g., "gemma2:2b", "llama3.1:8b", "gemini-pro"

-- ============================================================
-- PHASE 3: PRODUCTION ADDITIONS
-- ============================================================

-- Memory tier management for sessions
ALTER TABLE sessions ADD COLUMN tier VARCHAR(10) NOT NULL DEFAULT 'hot';
ALTER TABLE sessions ADD CONSTRAINT chk_sessions_tier
    CHECK (tier IN ('hot', 'warm', 'cold'));

ALTER TABLE sessions ADD COLUMN archived_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE sessions ADD COLUMN message_count INTEGER DEFAULT 0;

CREATE INDEX idx_sessions_tier ON sessions(tier);
CREATE INDEX idx_sessions_archived ON sessions(archived_at)
    WHERE archived_at IS NOT NULL;

-- User feedback on messages
CREATE TABLE feedback (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    rating VARCHAR(10) NOT NULL,                 -- thumbs_up, thumbs_down
    comment TEXT,                                  -- optional user comment
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_feedback_rating CHECK (rating IN ('thumbs_up', 'thumbs_down')),
    CONSTRAINT uq_feedback_message UNIQUE (message_id)  -- 1 feedback per message
);

CREATE INDEX idx_feedback_session_id ON feedback(session_id);
CREATE INDEX idx_feedback_rating ON feedback(rating);

-- ============================================================
-- HELPER FUNCTIONS
-- ============================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- Auto-update session message_count
CREATE OR REPLACE FUNCTION update_message_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        UPDATE sessions SET message_count = message_count + 1
        WHERE id = NEW.session_id;
    ELSIF TG_OP = 'DELETE' THEN
        UPDATE sessions SET message_count = message_count - 1
        WHERE id = OLD.session_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_messages_count
    AFTER INSERT OR DELETE ON messages
    FOR EACH ROW EXECUTE FUNCTION update_message_count();

-- ============================================================
-- FULL-TEXT SEARCH HELPER
-- ============================================================

-- BM25-style search function
CREATE OR REPLACE FUNCTION search_chunks_bm25(
    query_text TEXT,
    doc_filter UUID DEFAULT NULL,
    result_limit INTEGER DEFAULT 5
)
RETURNS TABLE(
    chunk_id UUID,
    document_id UUID,
    content TEXT,
    page_number INTEGER,
    metadata JSONB,
    rank REAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id AS chunk_id,
        c.document_id,
        c.content,
        c.page_number,
        c.metadata,
        ts_rank_cd(
            to_tsvector('simple', c.content),
            plainto_tsquery('simple', query_text)
        ) AS rank
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    WHERE d.status = 'indexed'
        AND to_tsvector('simple', c.content) @@ plainto_tsquery('simple', query_text)
        AND (doc_filter IS NULL OR c.document_id = doc_filter)
    ORDER BY rank DESC
    LIMIT result_limit;
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- INITIAL DATA (for init.sql)
-- ============================================================

-- This schema is designed to be run via:
--   docker exec -i postgres psql -U raguser -d ragdb < database-schema.sql
-- Or via Alembic migrations in production.
