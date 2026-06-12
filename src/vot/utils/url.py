import re
from collections.abc import Callable
from typing import Any
from urllib.parse import ParseResult, parse_qs, urlparse

import httpx

from vot.config import (
    SITES_INVIDIOUS,
    SITES_PIPED,
)
from vot.exceptions import VideoDataError
from vot.helpers.base import BaseHelper
from vot.helpers.youtube import YoutubeHelper
from vot.models import VideoData

# Regex to check for local or loopback links
LOCAL_LINK_RE = re.compile(
    r"(file:///?|https?://(127\.0\.0\.1|localhost|192\.168\.\d{1,3}\.\d{1,3}))"
)


# Helper matching registry
AVAILABLE_HELPERS: dict[str, type[BaseHelper]] = {
    "youtube": YoutubeHelper,
    "preservetube": YoutubeHelper,
    "invidious": YoutubeHelper,
    "piped": YoutubeHelper,
}


class SiteMatchRule:
    def __init__(
        self,
        rule: (re.Pattern[str] | str | list[re.Pattern[str] | str] | Callable[[ParseResult], bool]),
    ) -> None:
        self.rule = rule

    def matches(self, hostname: str, parsed_url: Any) -> bool:
        if isinstance(self.rule, list) or isinstance(self.rule, tuple):
            return any(SiteMatchRule(r).matches(hostname, parsed_url) for r in self.rule)
        elif isinstance(self.rule, re.Pattern):
            return bool(self.rule.search(hostname))
        elif isinstance(self.rule, str):
            return self.rule in hostname
        elif callable(self.rule):
            return self.rule(parsed_url)
        return False


# Define service configurations mapping (mirrors packages/node/src/data/sites.ts)
SITES_CONFIG: list[dict[str, Any]] = [
    {
        "host": "youtube",
        "url": "https://youtu.be/",
        "match": re.compile(r"^((www\.|m\.)?youtube(-nocookie|kids)?\.com)|(youtu\.be)$"),
    },
    {
        "host": "invidious",
        "url": "https://youtu.be/",
        "match": SITES_INVIDIOUS,
    },
    {
        "host": "piped",
        "url": "https://youtu.be/",
        "match": SITES_PIPED,
    },
    {
        "host": "preservetube",
        "url": "https://preservetube.com/watch?v=",
        "match": re.compile(r"^preservetube\.com$"),
    },
    {
        "host": "vk",
        "url": "https://vk.com/",
        "match": [re.compile(r"^(www\.|m\.)?vk\.(com|ru)$"), re.compile(r"^(.*\.)?vkvideo\.ru$")],
    },
    {
        "host": "twitch",
        "url": "https://twitch.tv/",
        "match": [
            re.compile(r"^m\.twitch\.tv$"),
            re.compile(r"^(www\.)?twitch\.tv$"),
            re.compile(r"^clips\.twitch\.tv$"),
            re.compile(r"^player\.twitch\.tv$"),
        ],
    },
    {
        "host": "tiktok",
        "url": "https://www.tiktok.com/",
        "match": re.compile(r"^(www\.)?tiktok\.com$"),
    },
    {
        "host": "vimeo",
        "url": "https://vimeo.com/",
        "match": re.compile(r"^(www\.|m\.)?vimeo\.com$"),
        "needExtraData": True,
    },
    {
        "host": "bannedvideo",
        "url": "https://madmaxworld.tv/watch?id=",
        "match": re.compile(r"^(www\.)?banned\.video|madmaxworld\.tv$"),
        "needExtraData": True,
    },
    {
        "host": "custom",
        "url": "stub",
        "match": lambda url: bool(re.search(r"([^/]+)\.(mp4|webm)", url.path)),
        "rawResult": True,
    },
]


def get_service(video_url: str) -> dict[str, Any] | None:
    """Determine the video service matching the URL."""
    if LOCAL_LINK_RE.search(video_url):
        return None

    try:
        parsed_url = urlparse(video_url)
    except Exception:
        return None

    hostname = parsed_url.hostname or ""

    for site in SITES_CONFIG:
        rule = SiteMatchRule(site["match"])
        if rule.matches(hostname, parsed_url):
            return site

    return None


async def get_video_id(
    service: dict[str, Any],
    video_url: str,
    client: httpx.AsyncClient | None = None,
) -> str | None:
    """Extract the video ID from URL based on the service matching rules."""
    host = service["host"]
    if host in AVAILABLE_HELPERS:
        helper = AVAILABLE_HELPERS[host](client=client, service=service)
        return await helper.get_video_id(video_url)

    if host == "custom":
        return video_url

    # General extraction fallback: try parsing the URL
    parsed = urlparse(video_url)
    if host == "vk":
        # Extract vk video ID from path or query params
        path_id = re.search(r"\/((?:video|clip)-?\d+_\d+)", parsed.path)
        if path_id:
            return path_id.group(1)
        q = parse_qs(parsed.query)
        z = q.get("z")
        if z:
            return z[0].split("/")[0]
        oid = q.get("oid")
        vid = q.get("id")
        if oid and vid:
            return f"video-{abs(int(oid[0]))}_{vid[0]}"
    elif host == "twitch":
        # Simple twitch extraction
        m = re.search(r"videos\/([^/]+)", parsed.path)
        if m:
            return f"videos/{m.group(1)}"
        m = re.search(r"([^/]+)\/(?:clip)\/([^/]+)", parsed.path)
        if m:
            return m.group(0)
    elif host == "vimeo":
        m = re.search(r"video\/([^/]+)$", parsed.path)
        if m:
            return m.group(1)
        parts = parsed.path.strip("/").split("/")
        if parts:
            return parts[-1]

    # Standard last path segment fallback
    parts = parsed.path.strip("/").split("/")
    if parts and parts[-1]:
        return parts[-1]

    return None


async def get_video_data(
    url: str,
    client: httpx.AsyncClient | None = None,
) -> VideoData:
    """Resolve service and extract all details, returning a VideoData model."""
    service = get_service(url)
    if not service:
        raise VideoDataError(f"URL: '{url}' is an unknown service")

    video_id = await get_video_id(service, url, client=client)
    if not video_id:
        raise VideoDataError(f"Entered unsupported link: '{url}'")

    host = service["host"]
    if service.get("rawResult"):
        return VideoData(
            url=video_id,
            videoId=video_id,
            host=host,
        )

    if not service.get("needExtraData"):
        base_url = service.get("url", "stub")
        final_url = video_id if base_url == "stub" else f"{base_url}{video_id}"
        return VideoData(
            url=final_url,
            videoId=video_id,
            host=host,
        )

    # If extra data is needed but we don't have the full helper API logic implemented,
    # return base data mapping.
    if host in AVAILABLE_HELPERS:
        helper = AVAILABLE_HELPERS[host](client=client, service=service)
        data = await helper.get_video_data(video_id)
        if data:
            return data

    # Fallback to base data if extra data helper failed
    base_url = service.get("url", "stub")
    final_url = video_id if base_url == "stub" else f"{base_url}{video_id}"
    return VideoData(
        url=final_url,
        videoId=video_id,
        host=host,
    )
