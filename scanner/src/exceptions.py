"""Custom exception types for structured error handling."""


class ApiError(Exception):
    """HTTP error with a status code, raised by ApiClient."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        super().__init__(detail)
