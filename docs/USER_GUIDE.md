# RAG Chatbot — User Guide

## What is RAG Chatbot?

RAG Chatbot is an AI-powered document Q&A system. You upload your documents (PDF, DOCX, TXT, MD), and the chatbot answers questions based on their content. It runs entirely on your local machine — no data leaves your environment.

---

## Getting Started

### 1. Access the Application

After the system is running, open your browser:

| Page | URL | Purpose |
|------|-----|---------|
| Chat | http://localhost:3000/chat | Ask questions about your documents |
| Upload | http://localhost:3000/upload | Upload and manage documents |
| Admin | http://localhost:3000/admin | View system status and stats |

### 2. Upload Documents

1. Navigate to the **Upload** page
2. Drag and drop files into the upload zone, or click to browse
3. Supported formats: **PDF**, **DOCX**, **TXT**, **MD**
4. Maximum file size: **50 MB**
5. Wait for the progress bar to complete — status changes: `queued` → `processing` → `indexed`
6. Once indexed, your document is ready for Q&A

**Tips:**
- Duplicate files (same content) are detected automatically
- You can upload multiple files at once
- Larger files take longer to process (chunking + embedding)

### 3. Chat with Your Documents

1. Navigate to the **Chat** page
2. Type your question in the input box and press Enter
3. The AI streams its response token-by-token in real time
4. Source citations appear below the response showing which documents were used

---

## Chat Modes

The chatbot has two operating modes. Toggle between them using the **Mode Switch** in the sidebar.

### Strict Mode (Default)

- Only answers questions using content from your uploaded documents
- If no relevant information is found, responds with: *"Không có thông tin liên quan trong tài liệu"*
- Does not engage in casual conversation
- Best for: accurate, source-verified answers

### General Mode

- Answers questions using documents when available
- Falls back to general AI knowledge when documents don't contain the answer
- Responds to casual greetings and conversations
- Adds a disclaimer when answering without document context
- Best for: broader questions, exploratory use

---

## Understanding Responses

### Source Citations

When the chatbot finds relevant information, it shows expandable source cards:

- **Document name** — which file the information came from
- **Page number** — specific page reference
- **Relevance score** — how closely the source matches your question (higher = better)
- **Snippet** — a brief excerpt from the source

Click on a source card to expand/collapse the details.

### Response Types

| Indicator | Meaning |
|-----------|---------|
| Streaming text with sources | Answer found in your documents |
| "Không có thông tin..." | Strict mode: no relevant documents found |
| Answer with disclaimer | General mode: AI knowledge used (no document source) |
| Error message | System issue — try again or check system status |

---

## Feedback

Help improve the system by rating responses:

1. Click **thumbs up** or **thumbs down** on any AI response
2. Optionally add a text comment explaining your rating
3. Feedback is stored for quality improvement

---

## Session Management

### Sessions

- Each conversation is a **session** with its own history
- Sessions appear in the left sidebar, grouped by date: Today, Yesterday, Last 7 days, Older
- Click a session to resume the conversation
- Click **New Chat** to start a fresh session

### Session History

- The chatbot remembers the last 6 messages in each session for context
- Older messages are archived but the session remains accessible
- Delete a session by clicking the delete button in the sidebar

---

## Supported Languages

The chatbot works with documents and questions in:

- **Vietnamese** (primary)
- **English** (full support)
- Mixed Vietnamese/English documents and queries

---

## Troubleshooting

### Common Issues

| Problem | Solution |
|---------|----------|
| Upload fails | Check file size (max 50MB) and format (PDF/DOCX/TXT/MD) |
| "Không có thông tin" on valid questions | Try rephrasing your question; ensure the document was indexed successfully |
| Slow responses | Large models may need warm-up time; first query after restart is slower |
| Chat not streaming | Refresh the page; check if backend is running (Admin → Services) |
| Source scores are low | Your question may be too vague; try more specific terms from the document |

### System Status

Visit the **Admin** page (http://localhost:3000/admin) to check:

- **Services**: PostgreSQL, Qdrant, Redis, Ollama status
- **Stats**: Total documents, chunks, sessions
- **Memory**: Per-service RAM usage
- **Models**: Currently loaded AI models

If a service shows as unhealthy, contact your system administrator.

---

## Tips for Better Results

1. **Be specific** — "Chi phí gói Premium là bao nhiêu?" works better than "cho tôi biết về chi phí"
2. **Use document terminology** — match the exact terms used in your documents
3. **One question at a time** — the AI handles focused questions better than compound ones
4. **Check the mode** — use Strict mode for factual answers, General mode for exploration
5. **Review sources** — always verify the answer against the cited sources
6. **Upload clean documents** — well-structured documents with clear headings produce better results
