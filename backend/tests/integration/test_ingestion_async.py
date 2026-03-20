"""Integration tests for async document ingestion via Celery."""
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import settings


class TestAsyncIngestionFlow:
    """Tests for async document ingestion with Celery."""

    @pytest.fixture
    def valid_pdf_content(self) -> bytes:
        """Minimal valid PDF content for testing."""
        return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n0000000115 00000 n \ntrailer\n<< /Size 4 /Root 1 0 R >>\nstartxref\n193\n%%EOF"

    @pytest.mark.asyncio
    async def test_upload_dispatches_celery_task(self, valid_pdf_content: bytes):
        """
        Test upload with async_mode=true dispatches Celery task.
        
        Flow: Upload → Document created (status=queued) → Celery task dispatched → 202
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile

        # Create mock UploadFile
        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test_report.pdf"
        mock_file.read = AsyncMock(return_value=valid_pdf_content)

        # Mock session
        mock_session = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.created_at = "2024-01-01T00:00:00"
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("app.api.v1.documents.ingest_document") as mock_task, \
             patch("app.api.v1.documents.save_upload_file") as mock_save, \
             patch("app.api.v1.documents.check_duplicate", return_value=False), \
             patch("app.api.v1.documents.compute_file_hash", return_value="abc123"), \
             patch("app.api.v1.documents.Document") as mock_doc_class:

            # Configure mocks
            mock_save.return_value = Path("/tmp/test_upload.pdf")
            mock_task.delay = MagicMock()
            mock_doc_class.return_value = mock_doc

            response = await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=True,
            )

            # Verify response
            assert response.status == "queued"
            assert response.filename == "test_report.pdf"
            assert response.file_type == "pdf"

            # Verify Celery task was dispatched
            mock_task.delay.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_sync_mode_no_celery(self, valid_pdf_content: bytes):
        """
        Test upload with async_mode=false runs synchronous ingestion.
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(return_value=valid_pdf_content)

        mock_session = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.created_at = "2024-01-01T00:00:00"
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("app.api.v1.documents.run_ingestion") as mock_run, \
             patch("app.api.v1.documents.ingest_document") as mock_task, \
             patch("app.api.v1.documents.check_duplicate", return_value=False), \
             patch("app.api.v1.documents.compute_file_hash", return_value="abc123"), \
             patch("app.api.v1.documents.Document") as mock_doc_class:

            mock_run.return_value = 10  # chunk count
            mock_doc_class.return_value = mock_doc

            response = await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=False,
            )

            # Sync mode returns "processing" status
            assert response.status == "processing"

            # Celery task should NOT be dispatched
            mock_task.delay.assert_not_called()

            # Sync ingestion should be called
            mock_run.assert_called_once()


class TestDocumentStatusProgression:
    """Tests for document status progression."""

    @pytest.fixture
    def valid_pdf_content(self) -> bytes:
        """Minimal valid PDF content."""
        return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\ntrailer\n<< /Root 1 0 R >>\nstartxref\n0\n%%EOF"

    @pytest.mark.asyncio
    async def test_status_queued_after_async_upload(self, valid_pdf_content: bytes):
        """
        Test document status is 'queued' immediately after async upload.
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "queued_test.pdf"
        mock_file.read = AsyncMock(return_value=valid_pdf_content)

        mock_session = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.created_at = "2024-01-01T00:00:00"
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("app.api.v1.documents.ingest_document") as mock_task, \
             patch("app.api.v1.documents.save_upload_file") as mock_save, \
             patch("app.api.v1.documents.check_duplicate", return_value=False), \
             patch("app.api.v1.documents.compute_file_hash", return_value="abc123"), \
             patch("app.api.v1.documents.Document") as mock_doc_class:

            mock_save.return_value = Path("/tmp/test.pdf")
            mock_task.delay = MagicMock()
            mock_doc_class.return_value = mock_doc

            response = await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=True,
            )

            # Should be queued (Celery task dispatched but not processed)
            assert response.status == "queued"


class TestDuplicateFileDetection:
    """Tests for duplicate file detection via SHA-256 hash."""

    @pytest.fixture
    def valid_pdf_content(self) -> bytes:
        """Minimal valid PDF content."""
        return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 1\ntrailer\n<< /Root 1 0 R >>\nstartxref\n0\n%%EOF"

    @pytest.mark.asyncio
    async def test_duplicate_file_rejected(self, valid_pdf_content: bytes):
        """
        Test uploading the same file content twice → duplicate error.
        
        Flow: Upload 1 → success → Upload 2 (same content) → 409 DUPLICATE_FILE
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile, HTTPException

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "duplicate.pdf"
        mock_file.read = AsyncMock(return_value=valid_pdf_content)

        mock_session = AsyncMock()

        with patch("app.api.v1.documents.check_duplicate", return_value=True), \
             patch("app.api.v1.documents.compute_file_hash", return_value="abc123"):

            # Should raise HTTPException with 409
            with pytest.raises(HTTPException) as exc_info:
                await upload_document(
                    file=mock_file,
                    session=mock_session,
                    async_mode=True,
                )

            assert exc_info.value.status_code == 409

    @pytest.mark.asyncio
    async def test_different_content_allowed(self, valid_pdf_content: bytes):
        """
        Test uploading different file content → succeeds.
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile

        content = valid_pdf_content + b"\n% Different content"

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "different.pdf"
        mock_file.read = AsyncMock(return_value=content)

        mock_session = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.created_at = "2024-01-01T00:00:00"
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("app.api.v1.documents.ingest_document") as mock_task, \
             patch("app.api.v1.documents.save_upload_file") as mock_save, \
             patch("app.api.v1.documents.check_duplicate", return_value=False), \
             patch("app.api.v1.documents.compute_file_hash", return_value="def456"), \
             patch("app.api.v1.documents.Document") as mock_doc_class:

            mock_save.return_value = Path("/tmp/test.pdf")
            mock_task.delay = MagicMock()
            mock_doc_class.return_value = mock_doc

            response = await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=True,
            )

            # Should succeed
            assert response.status == "queued"


class TestUnsupportedFileType:
    """Tests for unsupported file type handling."""

    @pytest.mark.asyncio
    async def test_unsupported_file_type_exe(self):
        """
        Test uploading unsupported file type (.exe) → 415.
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile, HTTPException

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "malware.exe"
        mock_file.read = AsyncMock(return_value=b"MZ...")

        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=True,
            )

        assert exc_info.value.status_code == 415

    @pytest.mark.asyncio
    async def test_unsupported_file_type_zip(self):
        """
        Test uploading unsupported file type (.zip) → 415.
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile, HTTPException

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "archive.zip"
        mock_file.read = AsyncMock(return_value=b"PK\x03\x04" + b"\x00" * 100)

        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=True,
            )

        assert exc_info.value.status_code == 415

    @pytest.mark.asyncio
    async def test_unsupported_file_type_js(self):
        """
        Test uploading unsupported file type (.js) → 415.
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile, HTTPException

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "script.js"
        mock_file.read = AsyncMock(return_value=b"console.log('test')")

        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=True,
            )

        assert exc_info.value.status_code == 415

    @pytest.mark.asyncio
    async def test_supported_file_type_pdf(self):
        """
        Test supported file type (PDF) is accepted.
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile

        content = b"%PDF-1.4\n1 0 obj\n<</Type/Catalog>>\nendobj\nxref\n0 1\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF"

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.pdf"
        mock_file.read = AsyncMock(return_value=content)

        mock_session = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.created_at = "2024-01-01T00:00:00"
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("app.api.v1.documents.ingest_document") as mock_task, \
             patch("app.api.v1.documents.save_upload_file") as mock_save, \
             patch("app.api.v1.documents.check_duplicate", return_value=False), \
             patch("app.api.v1.documents.compute_file_hash", return_value="abc123"), \
             patch("app.api.v1.documents.Document") as mock_doc_class:

            mock_save.return_value = Path("/tmp/test.pdf")
            mock_task.delay = MagicMock()
            mock_doc_class.return_value = mock_doc

            # Should not raise
            response = await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=True,
            )

            assert response.file_type == "pdf"

    @pytest.mark.asyncio
    async def test_supported_file_type_txt(self):
        """
        Test supported file type (TXT) is accepted.
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "test.txt"
        mock_file.read = AsyncMock(return_value=b"Test text content")

        mock_session = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.created_at = "2024-01-01T00:00:00"
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("app.api.v1.documents.ingest_document") as mock_task, \
             patch("app.api.v1.documents.save_upload_file") as mock_save, \
             patch("app.api.v1.documents.check_duplicate", return_value=False), \
             patch("app.api.v1.documents.compute_file_hash", return_value="abc123"), \
             patch("app.api.v1.documents.Document") as mock_doc_class:

            mock_save.return_value = Path("/tmp/test.txt")
            mock_task.delay = MagicMock()
            mock_doc_class.return_value = mock_doc

            response = await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=True,
            )

            assert response.file_type == "txt"


class TestFileSizeLimit:
    """Tests for file size limit enforcement."""

    @pytest.mark.asyncio
    async def test_file_too_large_rejected(self):
        """
        Test uploading file > 50MB → 413 FILE_TOO_LARGE.
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile, HTTPException

        # Create content larger than max size
        max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
        oversized_content = b"%PDF-1.4\n" + b"X" * (max_size_bytes + 1000)

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "huge_file.pdf"
        mock_file.read = AsyncMock(return_value=oversized_content)

        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=True,
            )

        assert exc_info.value.status_code == 413

    @pytest.mark.asyncio
    async def test_file_at_limit_accepted(self):
        """
        Test uploading file just under limit → accepted.
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile

        # Create content just under max size
        max_size_bytes = settings.max_upload_size_mb * 1024 * 1024
        pdf_header = b"%PDF-1.4\n1 0 obj\n<</Type/Catalog>>\nendobj\nxref\n0 1\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF"
        padding_size = max_size_bytes - len(pdf_header) - 100
        content = pdf_header + b"\n% " + b"X" * padding_size

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = "exact_size.pdf"
        mock_file.read = AsyncMock(return_value=content)

        mock_session = AsyncMock()
        mock_doc = MagicMock()
        mock_doc.id = uuid.uuid4()
        mock_doc.created_at = "2024-01-01T00:00:00"
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()
        mock_session.commit = AsyncMock()

        with patch("app.api.v1.documents.ingest_document") as mock_task, \
             patch("app.api.v1.documents.save_upload_file") as mock_save, \
             patch("app.api.v1.documents.check_duplicate", return_value=False), \
             patch("app.api.v1.documents.compute_file_hash", return_value="abc123"), \
             patch("app.api.v1.documents.Document") as mock_doc_class:

            mock_save.return_value = Path("/tmp/test.pdf")
            mock_task.delay = MagicMock()
            mock_doc_class.return_value = mock_doc

            # Should not raise
            response = await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=True,
            )

            assert response.status == "queued"


class TestMissingFile:
    """Tests for missing file handling."""

    @pytest.mark.asyncio
    async def test_empty_filename_rejected(self):
        """
        Test request with empty filename → 400.
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile, HTTPException

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = ""  # Empty filename
        mock_file.read = AsyncMock(return_value=b"test")

        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=True,
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_none_filename_rejected(self):
        """
        Test request with None filename → 400.
        """
        from app.api.v1.documents import upload_document
        from fastapi import UploadFile, HTTPException

        mock_file = MagicMock(spec=UploadFile)
        mock_file.filename = None
        mock_file.read = AsyncMock(return_value=b"test")

        mock_session = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await upload_document(
                file=mock_file,
                session=mock_session,
                async_mode=True,
            )

        assert exc_info.value.status_code == 400


class TestCeleryTaskExecution:
    """Tests for Celery task execution logic."""

    @pytest.mark.asyncio
    async def test_ingest_task_updates_document_status(self):
        """
        Test ingest_document task updates document status correctly.
        """
        from app.tasks import _mark_document_error

        doc_id = str(uuid.uuid4())

        # Mock database session
        mock_session = AsyncMock()

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        with patch("app.db.postgres.AsyncSessionLocal", return_value=mock_session_ctx):
            await _mark_document_error(doc_id, "Test error message")

            # Verify session.execute was called with update
            mock_session.execute.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_ingest_task_file_not_found(self):
        """
        Test ingest_document raises error for missing file.
        """
        from app.tasks import _run_ingest_async

        doc_id = str(uuid.uuid4())
        nonexistent_path = "/nonexistent/path/to/file.pdf"

        with pytest.raises(FileNotFoundError):
            await _run_ingest_async(doc_id, nonexistent_path)


class TestSaveUploadFile:
    """Tests for save_upload_file helper function."""

    def test_save_upload_file_sanitizes_filename(self, tmp_path):
        """
        Test save_upload_file sanitizes dangerous filenames.
        """
        from app.tasks import save_upload_file
        from app import tasks

        # Temporarily override UPLOADS_DIR for testing
        original_dir = tasks.UPLOADS_DIR
        try:
            tasks.UPLOADS_DIR = tmp_path
            tasks.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

            doc_id = uuid.uuid4()
            dangerous_filename = "../../../etc/passwd"
            content = b"test content"

            result_path = save_upload_file(doc_id, dangerous_filename, content)

            # Should NOT contain path traversal
            assert ".." not in str(result_path)
            assert str(result_path).startswith(str(tmp_path))

            # File should be saved
            assert result_path.exists()
            assert result_path.read_bytes() == content

        finally:
            tasks.UPLOADS_DIR = original_dir

    def test_save_upload_file_handles_backslash(self, tmp_path):
        """
        Test save_upload_file handles Windows-style paths.
        """
        from app.tasks import save_upload_file
        from app import tasks

        original_dir = tasks.UPLOADS_DIR
        try:
            tasks.UPLOADS_DIR = tmp_path
            tasks.UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

            doc_id = uuid.uuid4()
            windows_filename = "..\\..\\windows\\system32\\config"
            content = b"test"

            result_path = save_upload_file(doc_id, windows_filename, content)

            # Should NOT contain path traversal
            assert ".." not in str(result_path)
            assert result_path.exists()

        finally:
            tasks.UPLOADS_DIR = original_dir
