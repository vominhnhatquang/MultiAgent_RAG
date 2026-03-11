"""Initial schema: documents, chunks, sessions, messages, feedback

Revision ID: 001
Revises:
Create Date: 2026-03-11

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    # documents
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("file_type", sa.String(20), nullable=False),
        sa.Column("file_size_bytes", sa.BigInteger, nullable=False),
        sa.Column("file_hash", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("chunk_count", sa.Integer, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("status IN ('processing','indexed','error','deleted')", name="chk_documents_status"),
        sa.CheckConstraint("file_type IN ('pdf','docx','md','txt')", name="chk_documents_file_type"),
    )
    op.create_index("idx_documents_status", "documents", ["status"])
    op.create_index("idx_documents_created_at", "documents", ["created_at"])
    op.execute(
        "CREATE UNIQUE INDEX idx_documents_file_hash ON documents(file_hash) "
        "WHERE file_hash IS NOT NULL AND status != 'deleted'"
    )

    # chunks
    op.create_table(
        "chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("embedding", sa.Text, nullable=True),   # placeholder; actual VECTOR type via raw SQL
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("page_number", sa.Integer, nullable=True),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("char_count", sa.Integer, nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("chunk_index >= 0", name="chk_chunks_index"),
    )
    # Replace placeholder embedding column with proper vector type
    op.execute("ALTER TABLE chunks DROP COLUMN embedding")
    op.execute("ALTER TABLE chunks ADD COLUMN embedding vector(768)")
    op.create_index("idx_chunks_document_id", "chunks", ["document_id"])
    op.create_index("idx_chunks_page", "chunks", ["document_id", "page_number"])
    op.execute("CREATE INDEX idx_chunks_metadata ON chunks USING GIN (metadata)")
    op.execute("CREATE INDEX idx_chunks_content_fts ON chunks USING GIN (to_tsvector('simple', content))")
    op.execute(
        "CREATE INDEX idx_chunks_embedding ON chunks "
        "USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # sessions
    op.create_table(
        "sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("title", sa.String(255), nullable=True),
        sa.Column("mode", sa.String(10), nullable=False, server_default="strict"),
        sa.Column("tier", sa.String(10), nullable=False, server_default="hot"),
        sa.Column("message_count", sa.Integer, server_default="0"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("mode IN ('strict','general')", name="chk_sessions_mode"),
        sa.CheckConstraint("tier IN ('hot','warm','cold')", name="chk_sessions_tier"),
    )
    op.create_index("idx_sessions_updated_at", "sessions", ["updated_at"])
    op.create_index("idx_sessions_tier", "sessions", ["tier"])

    # messages
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("sources", postgresql.JSONB, nullable=True),
        sa.Column("model_used", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("role IN ('user','assistant','system')", name="chk_messages_role"),
    )
    op.create_index("idx_messages_session_id", "messages", ["session_id"])
    op.create_index("idx_messages_created_at", "messages", ["session_id", "created_at"])

    # feedback
    op.create_table(
        "feedback",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.String(10), nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("rating IN ('thumbs_up','thumbs_down')", name="chk_feedback_rating"),
        sa.UniqueConstraint("message_id", name="uq_feedback_message"),
    )
    op.create_index("idx_feedback_session_id", "feedback", ["session_id"])
    op.create_index("idx_feedback_rating", "feedback", ["rating"])

    # triggers
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_documents_updated_at
        BEFORE UPDATE ON documents
        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
    """)
    op.execute("""
        CREATE TRIGGER trg_sessions_updated_at
        BEFORE UPDATE ON sessions
        FOR EACH ROW EXECUTE FUNCTION update_updated_at()
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION update_message_count()
        RETURNS TRIGGER AS $$
        BEGIN
            IF TG_OP = 'INSERT' THEN
                UPDATE sessions SET message_count = message_count + 1 WHERE id = NEW.session_id;
            ELSIF TG_OP = 'DELETE' THEN
                UPDATE sessions SET message_count = message_count - 1 WHERE id = OLD.session_id;
            END IF;
            RETURN NULL;
        END;
        $$ LANGUAGE plpgsql
    """)
    op.execute("""
        CREATE TRIGGER trg_messages_count
        AFTER INSERT OR DELETE ON messages
        FOR EACH ROW EXECUTE FUNCTION update_message_count()
    """)

    # BM25 search function
    op.execute("""
        CREATE OR REPLACE FUNCTION search_chunks_bm25(
            query_text TEXT,
            doc_filter UUID DEFAULT NULL,
            result_limit INTEGER DEFAULT 5
        )
        RETURNS TABLE(chunk_id UUID, document_id UUID, content TEXT, page_number INTEGER, metadata JSONB, rank REAL) AS $$
        BEGIN
            RETURN QUERY
            SELECT c.id, c.document_id, c.content, c.page_number, c.metadata,
                ts_rank_cd(to_tsvector('simple', c.content), plainto_tsquery('simple', query_text)) AS rank
            FROM chunks c
            JOIN documents d ON c.document_id = d.id
            WHERE d.status = 'indexed'
              AND to_tsvector('simple', c.content) @@ plainto_tsquery('simple', query_text)
              AND (doc_filter IS NULL OR c.document_id = doc_filter)
            ORDER BY rank DESC
            LIMIT result_limit;
        END;
        $$ LANGUAGE plpgsql
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_messages_count ON messages")
    op.execute("DROP TRIGGER IF EXISTS trg_sessions_updated_at ON sessions")
    op.execute("DROP TRIGGER IF EXISTS trg_documents_updated_at ON documents")
    op.execute("DROP FUNCTION IF EXISTS update_message_count()")
    op.execute("DROP FUNCTION IF EXISTS update_updated_at()")
    op.execute("DROP FUNCTION IF EXISTS search_chunks_bm25(TEXT, UUID, INTEGER)")
    op.drop_table("feedback")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("chunks")
    op.drop_table("documents")
