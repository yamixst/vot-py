from typing import Any

import httpx

from vot.models import VideoData


class BaseHelper:
    """Base class for all video service helpers."""

    def __init__(
        self,
        client: httpx.AsyncClient | None = None,
        extra_info: bool = True,
        referer: str = "",
        origin: str = "",
        service: dict[str, Any] | None = None,
        language: str = "en",
    ) -> None:
        self.client = client or httpx.AsyncClient()
        self.extra_info = extra_info
        self.referer = referer
        self.origin = origin if origin.startswith(("http://", "https://")) else ""
        self.api_origin = self.origin
        self.service = service
        self.language = language

    async def get_video_data(self, video_id: str) -> VideoData | None:
        """Fetch full video metadata (URL, subtitles, duration, title)."""
        return None

    async def get_video_id(self, url: str) -> str | None:
        """Extract the video ID from the service URL."""
        return None

    def return_base_data(self, video_id: str) -> dict[str, Any] | None:
        """Return base metadata using the configured service template."""
        if not self.service:
            return None

        base_url = self.service.get("url", "stub")
        # For stub urls, we just return the video_id or empty prefix
        url = video_id if base_url == "stub" else f"{base_url}{video_id}"

        return {
            "url": url,
            "videoId": video_id,
            "host": self.service.get("host"),
            "duration": None,
        }
