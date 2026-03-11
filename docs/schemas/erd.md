# Entity Relationship Diagram

**Author:** Alpha (System Architect)

```mermaid
erDiagram
    DOCUMENTS ||--o{ CHUNKS : "has many"
    SESSIONS ||--o{ MESSAGES : "has many"
    SESSIONS ||--o{ FEEDBACK : "has many"
    MESSAGES ||--o| FEEDBACK : "has one"

    DOCUMENTS {
        uuid id PK
        varchar filename
        varchar file_type
        bigint file_size_bytes
        varchar file_hash UK
        varchar status
        int chunk_count
        text error_message
        timestamptz created_at
        timestamptz updated_at
    }

    CHUNKS {
        uuid id PK
        uuid document_id FK
        text content
        vector embedding "768-dim"
        int chunk_index
        int page_number
        int token_count
        int char_count
        jsonb metadata
        timestamptz created_at
    }

    SESSIONS {
        uuid id PK
        varchar title
        varchar mode "strict/general"
        varchar tier "hot/warm/cold"
        int message_count
        timestamptz archived_at
        timestamptz created_at
        timestamptz updated_at
    }

    MESSAGES {
        uuid id PK
        uuid session_id FK
        varchar role "user/assistant/system"
        text content
        jsonb sources
        varchar model_used
        timestamptz created_at
    }

    FEEDBACK {
        uuid id PK
        uuid message_id FK UK
        uuid session_id FK
        varchar rating "thumbs_up/thumbs_down"
        text comment
        timestamptz created_at
    }
```
