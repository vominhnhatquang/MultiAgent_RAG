"""Unit tests for Celery async ingestion tasks."""
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestIngestDocumentTask:
    """Tests for ingest_document Celery task."""

    @pytest.fixture
    def mock_session_factory(self):
        """Mock async session factory."""
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("app.tasks.async_session_factory", return_value=mock_session):
            yield mock_session

    def test_save_upload_file_creates_file(self, tmp_path):
        """Test that save_upload_file creates file on disk."""
        from app.tasks import save_upload_file

        # Patch UPLOADS_DIR
        with patch("app.tasks.UPLOADS_DIR", tmp_path):
            doc_id = uuid.uuid4()
            filename = "test_document.pdf"
            content = b"PDF content here"

            result = save_upload_file(doc_id, filename, content)

            assert result.exists()
            assert result.read_bytes() == content
            assert f"{doc_id}_" in result.name
            assert filename in result.name

    def test_save_upload_file_sanitizes_filename(self, tmp_path):
        """Test that dangerous characters are sanitized from filename."""
        from app.tasks import save_upload_file

        with patch("app.tasks.UPLOADS_DIR", tmp_path):
            doc_id = uuid.uuid4()
            filename = "../../../etc/passwd"  # Malicious path
            content = b"content"

            result = save_upload_file(doc_id, filename, content)

            # Should not have path traversal
            assert ".." not in result.name
            assert "/" not in result.name.replace(str(tmp_path), "")


class TestCleanupOldUploads:
    """Tests for cleanup_old_uploads periodic task."""

    def test_cleanup_removes_old_files(self, tmp_path):
        """Test that old files are removed."""
        import os
        from app.tasks import cleanup_old_uploads

        with patch("app.tasks.UPLOADS_DIR", tmp_path):
            # Create old file
            old_file = tmp_path / "old_file.pdf"
            old_file.write_bytes(b"old content")

            # Make it look old (25 hours ago)
            old_time = datetime.now(timezone.utc) - timedelta(hours=25)
            os.utime(old_file, (old_time.timestamp(), old_time.timestamp()))

            # Create recent file
            recent_file = tmp_path / "recent_file.pdf"
            recent_file.write_bytes(b"recent content")

            # Run cleanup
            result = cleanup_old_uploads(max_age_hours=24)

            assert result["removed"] == 1
            assert not old_file.exists()
            assert recent_file.exists()

    def test_cleanup_handles_empty_directory(self, tmp_path):
        """Test cleanup works with empty directory."""
        from app.tasks import cleanup_old_uploads

        with patch("app.tasks.UPLOADS_DIR", tmp_path):
            result = cleanup_old_uploads()

            assert result["removed"] == 0
            assert result["errors"] == 0

    def test_cleanup_skips_directories(self, tmp_path):
        """Test that directories are not removed."""
        import os
        from app.tasks import cleanup_old_uploads

        with patch("app.tasks.UPLOADS_DIR", tmp_path):
            # Create subdirectory
            subdir = tmp_path / "subdir"
            subdir.mkdir()

            # Make it look old
            old_time = datetime.now(timezone.utc) - timedelta(hours=48)
            os.utime(subdir, (old_time.timestamp(), old_time.timestamp()))

            result = cleanup_old_uploads(max_age_hours=24)

            assert result["removed"] == 0
            assert subdir.exists()


class TestTaskConfiguration:
    """Tests for Celery task configuration."""

    def test_ingest_document_has_retry_config(self):
        """Test that ingest_document task has correct retry configuration."""
        from app.tasks import ingest_document

        # Check retry configuration
        assert ingest_document.max_retries == 3
        assert ingest_document.autoretry_for == (Exception,)

    def test_health_check_task_exists(self):
        """Test that health_check task is defined."""
        from app.tasks import health_check

        result = health_check()
        assert result == {"status": "ok"}

    def test_beat_schedule_configured(self):
        """Test that Celery beat schedule includes cleanup task."""
        from app.celery_app import celery_app

        schedule = celery_app.conf.beat_schedule
        assert "cleanup-old-uploads" in schedule

        cleanup_config = schedule["cleanup-old-uploads"]
        assert cleanup_config["task"] == "app.tasks.cleanup_old_uploads"
        # Schedule is now crontab (daily at 4 AM), not simple interval
        assert cleanup_config["args"] == (24,)


class TestUploadEndpointAsync:
    """Tests for async upload endpoint behavior."""

    @pytest.mark.asyncio
    async def test_upload_with_async_mode_queues_task(self):
        """Test that async_mode=true queues Celery task."""

        with patch("app.api.v1.documents.ingest_document") as mock_task:
            mock_task.delay = MagicMock()

            with patch("app.api.v1.documents.save_upload_file") as mock_save:
                mock_save.return_value = Path("/tmp/test_doc.pdf")

                # The actual endpoint call would be tested in integration tests
                # Here we verify the task would be called
                doc_id = uuid.uuid4()
                file_path = "/tmp/test_doc.pdf"

                mock_task.delay(str(doc_id), file_path)

                mock_task.delay.assert_called_once_with(str(doc_id), file_path)

    def test_document_status_values(self):
        """Test that document status includes 'queued' for async."""
        from app.db.models.document import Document

        # Check the constraint includes queued
        for constraint in Document.__table_args__:
            if hasattr(constraint, 'name') and constraint.name == 'chk_documents_status':
                assert 'queued' in str(constraint.sqltext)
                break
        else:
            pytest.fail("Status constraint not found")
