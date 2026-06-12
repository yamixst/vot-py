from typing import Any


class VOTError(Exception):
    """Base exception class for all errors in the library."""

    pass


class VOTJSError(VOTError):
    """Exception raised for errors returned from Yandex VOT API requests."""

    def __init__(self, message: str, data: Any = None) -> None:
        super().__init__(message)
        self.data = data


class VOTAPIError(VOTError):
    """Exception raised for general VOT API connectivity or server failures."""

    pass


class VideoDataError(VOTError):
    """Exception raised when video service/data resolution fails."""

    pass


class VideoHelperError(VOTError):
    """Exception raised within video extraction helpers."""

    pass
