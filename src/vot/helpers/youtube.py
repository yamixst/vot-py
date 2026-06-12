import re
from urllib.parse import parse_qs, unquote, urlparse

from vot.helpers.base import BaseHelper


class YoutubeHelper(BaseHelper):
    """Helper to extract video IDs from YouTube URLs."""

    @staticmethod
    def extract_video_id(url_str: str) -> str | None:
        try:
            url = urlparse(url_str)
        except Exception:
            return None

        # Handle YouTube "share/redirect" wrappers
        # Example: /attribution_link?u=%2Fwatch%3Fv%3DVIDEO_ID%26feature%3Dshare
        if url.path == "/attribution_link":
            q = parse_qs(url.query)
            u_list = q.get("u")
            if u_list:
                try:
                    decoded = unquote(u_list[0])
                    inner_url = (
                        decoded
                        if decoded.startswith("http")
                        else f"{url.scheme}://{url.netloc}{decoded}"
                    )
                    video_id = YoutubeHelper.extract_video_id(inner_url)
                    if video_id:
                        return video_id
                except Exception:
                    pass

        # Handle hash fragment formats
        raw_hash = url.fragment
        if raw_hash:
            normalized_hash = raw_hash[1:] if raw_hash.startswith("!") else raw_hash
            try:
                decoded_hash = unquote(normalized_hash)
            except Exception:
                decoded_hash = normalized_hash

            try:
                hash_url = (
                    decoded_hash
                    if decoded_hash.startswith("http")
                    else f"{url.scheme}://{url.netloc}{decoded_hash}"
                )
                hash_video_id = YoutubeHelper.extract_video_id(hash_url)
                if hash_video_id:
                    return hash_video_id
            except Exception:
                # Regex backup for hash
                match = re.search(r"(?:^|[?&#])v=([^&#]+)", decoded_hash)
                if match:
                    return match.group(1)

        # Handle youtu.be/<id>
        hostname = url.hostname or ""
        if hostname == "youtu.be":
            parts = url.path.lstrip("/").split("/")
            if parts and parts[0]:
                return parts[0]

        # Handle watch?v=<id>
        q = parse_qs(url.query)
        v_param = q.get("v")
        if v_param:
            return v_param[0]

        # Handle /shorts/<id>, /embed/<id>, /live/<id>, /v/<id>, /e/<id>
        match = re.search(r"\/(?:shorts|embed|live|v|e)\/([^/?#]+)", url.path)
        if match:
            return match.group(1)

        return None

    async def get_video_id(self, url: str) -> str | None:
        return self.extract_video_id(url)
