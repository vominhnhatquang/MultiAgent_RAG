from fastapi import HTTPException


class AppError(Exception):
    """Base application error."""

    def __init__(self, message: str, code: str, http_status: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.http_status = http_status

    def to_http(self) -> HTTPException:
        return HTTPException(
            status_code=self.http_status,
            detail={"error": self.message, "code": self.code},
        )


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", code: str = "NOT_FOUND") -> None:
        super().__init__(message, code, 404)


class ValidationError(AppError):
    def __init__(self, message: str, code: str = "VALIDATION_ERROR") -> None:
        super().__init__(message, code, 400)


class DuplicateError(AppError):
    def __init__(self, message: str, code: str = "DUPLICATE") -> None:
        super().__init__(message, code, 409)


class FileTooLargeError(AppError):
    def __init__(self) -> None:
        super().__init__("File exceeds 50MB limit", "FILE_TOO_LARGE", 413)


class UnsupportedFileTypeError(AppError):
    def __init__(self, file_type: str) -> None:
        super().__init__(f"File type '{file_type}' not supported", "UNSUPPORTED_TYPE", 415)


class LLMUnavailableError(AppError):
    def __init__(self, message: str = "LLM service unavailable") -> None:
        super().__init__(message, "LLM_UNAVAILABLE", 503)


class ServiceDownError(AppError):
    def __init__(self, service: str) -> None:
        super().__init__(f"Service '{service}' is down", "SERVICE_DOWN", 503)


class RateLimitError(AppError):
    def __init__(self) -> None:
        super().__init__("Rate limit exceeded", "RATE_LIMIT", 429)
