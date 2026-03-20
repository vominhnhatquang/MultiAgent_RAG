"""Unit tests for Session PATCH endpoint."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


class TestUpdateSession:
    """Tests for PATCH /sessions/{session_id} endpoint."""

    @pytest.mark.asyncio
    async def test_update_session_title_only(self):
        """Test updating only the session title."""
        from app.api.v1.chat import update_session, UpdateSessionRequest

        session_id = uuid.uuid4()

        # Mock session object
        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.title = "Old Title"
        mock_session.mode = "strict"
        mock_session.tier = "hot"
        mock_session.message_count = 5
        mock_session.created_at = "2024-01-01T00:00:00"
        mock_session.updated_at = "2024-01-01T00:00:00"

        # Mock DB result
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_session

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        body = UpdateSessionRequest(title="New Title")
        result = await update_session(session_id, body, mock_db)

        # Verify title was updated
        assert mock_session.title == "New Title"
        assert mock_session.mode == "strict"  # unchanged
        assert result.title == "New Title"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_session_mode_only(self):
        """Test updating only the session mode."""
        from app.api.v1.chat import update_session, UpdateSessionRequest

        session_id = uuid.uuid4()

        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.title = "Test Title"
        mock_session.mode = "strict"
        mock_session.tier = "hot"
        mock_session.message_count = 3
        mock_session.created_at = "2024-01-01T00:00:00"
        mock_session.updated_at = "2024-01-01T00:00:00"

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_session

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        body = UpdateSessionRequest(mode="general")
        result = await update_session(session_id, body, mock_db)

        # Verify mode was updated
        assert mock_session.mode == "general"
        assert mock_session.title == "Test Title"  # unchanged
        assert result.mode == "general"
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_session_both_fields(self):
        """Test updating both title and mode."""
        from app.api.v1.chat import update_session, UpdateSessionRequest

        session_id = uuid.uuid4()

        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.title = "Old Title"
        mock_session.mode = "strict"
        mock_session.tier = "warm"
        mock_session.message_count = 10
        mock_session.created_at = "2024-01-01T00:00:00"
        mock_session.updated_at = "2024-01-01T00:00:00"

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_session

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        body = UpdateSessionRequest(title="New Title", mode="general")
        result = await update_session(session_id, body, mock_db)

        # Verify both fields updated
        assert mock_session.title == "New Title"
        assert mock_session.mode == "general"
        assert result.title == "New Title"
        assert result.mode == "general"

    @pytest.mark.asyncio
    async def test_update_session_not_found(self):
        """Test updating non-existent session returns 404."""
        from app.api.v1.chat import update_session, UpdateSessionRequest
        from fastapi import HTTPException

        session_id = uuid.uuid4()

        # Mock DB returns None (session not found)
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        body = UpdateSessionRequest(title="New Title")

        with pytest.raises(HTTPException) as exc_info:
            await update_session(session_id, body, mock_db)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_update_session_empty_body(self):
        """Test update with empty body (no changes)."""
        from app.api.v1.chat import update_session, UpdateSessionRequest

        session_id = uuid.uuid4()

        mock_session = MagicMock()
        mock_session.id = session_id
        mock_session.title = "Original Title"
        mock_session.mode = "strict"
        mock_session.tier = "hot"
        mock_session.message_count = 2
        mock_session.created_at = "2024-01-01T00:00:00"
        mock_session.updated_at = "2024-01-01T00:00:00"

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_session

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        # Empty body - no updates
        body = UpdateSessionRequest()
        result = await update_session(session_id, body, mock_db)

        # No changes made
        assert mock_session.title == "Original Title"
        assert mock_session.mode == "strict"
        assert result.title == "Original Title"


class TestUpdateSessionRequestValidation:
    """Tests for UpdateSessionRequest validation."""

    def test_valid_mode_strict(self):
        """Test valid mode='strict'."""
        from app.api.v1.chat import UpdateSessionRequest

        req = UpdateSessionRequest(mode="strict")
        assert req.mode == "strict"

    def test_valid_mode_general(self):
        """Test valid mode='general'."""
        from app.api.v1.chat import UpdateSessionRequest

        req = UpdateSessionRequest(mode="general")
        assert req.mode == "general"

    def test_invalid_mode_rejected(self):
        """Test invalid mode is rejected."""
        from app.api.v1.chat import UpdateSessionRequest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            UpdateSessionRequest(mode="invalid")

    def test_title_max_length(self):
        """Test title respects max length."""
        from app.api.v1.chat import UpdateSessionRequest
        from pydantic import ValidationError

        # Should fail with title > 200 chars
        with pytest.raises(ValidationError):
            UpdateSessionRequest(title="x" * 201)

    def test_title_at_max_length(self):
        """Test title at exactly max length is valid."""
        from app.api.v1.chat import UpdateSessionRequest

        req = UpdateSessionRequest(title="x" * 200)
        assert len(req.title) == 200
