import asyncio
import re
import time
from collections.abc import Coroutine
from typing import Any, TypeVar, cast

import httpx

from vot import config
from vot.exceptions import VOTJSError
from vot.models import (
    GetSubtitlesResponse,
    StreamTranslationObject,
    StreamTranslationResponse,
    SubtitleItem,
    TranslationResponse,
    VideoData,
)
from vot.protobuf import (
    StreamTranslationRequest,
    SubtitlesRequest,
    SubtitlesResponse,
    VideoTranslationAudioRequest,
    VideoTranslationAudioResponse,
    VideoTranslationCacheRequest,
    VideoTranslationCacheResponse,
    VideoTranslationHelpObject,
    VideoTranslationRequest,
    VideoTranslationResponse,
    YandexSessionRequest,
    YandexSessionResponse,
)
from vot.protobuf import (
    StreamTranslationResponse as StreamProtoResponse,
)
from vot.utils.crypto import get_sec_ya_headers, get_signature, get_uuid

T = TypeVar("T")


class MinimalClient:
    """Base client for interacting with the Yandex Protobuf/JSON API endpoints."""

    def __init__(
        self,
        host: str = config.HOST,
        client: httpx.AsyncClient | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        schema_match = re.match(r"^(http(?:s)?):\/\/", host)
        if schema_match:
            self.schema = schema_match.group(1)
            self.host = host.replace(f"{self.schema}://", "")
        else:
            self.schema = "https"
            self.host = host

        self.client = client or httpx.AsyncClient(timeout=10.0)
        self.sessions: dict[str, dict[str, Any]] = {}
        self.user_agent = config.USER_AGENT

        self.headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/x-protobuf",
            "Accept-Language": "en",
            "Content-Type": "application/x-protobuf",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }
        if headers:
            self.headers.update(headers)

    async def request(
        self,
        path: str,
        body: bytes,
        headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> dict[str, Any]:
        """Perform a binary protobuf request."""
        req_headers = self.headers.copy()
        if headers:
            req_headers.update(headers)

        url = f"{self.schema}://{self.host}{path}"
        try:
            res = await self.client.request(
                method,
                url,
                headers=req_headers,
                content=body,
            )
            return {
                "success": res.status_code == 200,
                "data": res.content,
            }
        except Exception as e:
            return {
                "success": False,
                "data": str(e).encode("utf-8"),
            }

    async def request_json(
        self,
        path: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> dict[str, Any]:
        """Perform a JSON request."""
        req_headers = self.headers.copy()
        req_headers["Content-Type"] = "application/json"
        if headers:
            req_headers.update(headers)

        url = f"{self.schema}://{self.host}{path}"
        try:
            res = await self.client.request(
                method,
                url,
                headers=req_headers,
                json=body,
            )
            return {
                "success": res.status_code == 200,
                "data": res.json() if res.status_code == 200 else res.text,
            }
        except Exception as e:
            return {
                "success": False,
                "data": str(e),
            }

    async def get_session(self, module: str) -> dict[str, Any]:
        """Get an active session for the specified module, generating a new one if expired."""
        timestamp = int(time.time())
        session = self.sessions.get(module)
        if session and session["timestamp"] + session["expires"] > timestamp:
            return session

        new_session = await self.create_session(module)
        new_session["timestamp"] = timestamp
        self.sessions[module] = new_session
        return new_session

    async def create_session(self, module: str) -> dict[str, Any]:
        """Create a new Yandex VOT session."""
        uuid = get_uuid()
        req = YandexSessionRequest(uuid=uuid, module=module)
        body = req.SerializeToString()

        signature = get_signature(body)
        res = await self.request(
            "/session/create",
            body,
            headers={"Vtrans-Signature": signature},
        )

        if not res["success"]:
            raise VOTJSError("Failed to request create session", res)

        session_resp = YandexSessionResponse()
        session_resp.ParseFromString(res["data"])

        return {
            "secretKey": session_resp.secretKey,
            "expires": session_resp.expires,
            "uuid": uuid,
        }


class VOTClient(MinimalClient):
    """Core VOTClient implementing the translation, subtitle, and stream Yandex/VOT API endpoints."""

    def __init__(
        self,
        host: str = config.HOST,
        host_vot: str = config.HOST_VOT,
        client: httpx.AsyncClient | None = None,
        request_lang: str = "en",
        response_lang: str = "ru",
        api_token: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(host=host, client=client, headers=headers)

        schema_match = re.match(r"^(http(?:s)?):\/\/", host_vot)
        if schema_match:
            self.schema_vot = schema_match.group(1)
            self.host_vot = host_vot.replace(f"{self.schema_vot}://", "")
        else:
            self.schema_vot = "https"
            self.host_vot = host_vot

        self.request_lang = request_lang
        self.response_lang = response_lang
        self.api_token = api_token

        self.paths = {
            "videoTranslation": "/video-translation/translate",
            "videoTranslationFailAudio": "/video-translation/fail-audio-js",
            "videoTranslationAudio": "/video-translation/audio",
            "videoTranslationCache": "/video-translation/cache",
            "videoSubtitles": "/video-subtitles/get-subtitles",
            "streamPing": "/stream-translation/ping-stream",
            "streamTranslation": "/stream-translation/translate-stream",
        }

        self.headers_vot = {
            "User-Agent": f"vot.js/{config.VERSION}",
            "Content-Type": "application/json",
            "Pragma": "no-cache",
            "Cache-Control": "no-cache",
        }

    def is_custom_link(self, url: str) -> bool:
        """Check if URL points to a custom/direct media stream."""
        return bool(
            re.search(r"\.(m3u8|m4(a|v)|mpd)", url)
            or url.startswith("https://cdn.qstv.on.epicgames.com")
        )

    @property
    def api_token_header(self) -> dict[str, str]:
        if not self.api_token:
            return {}
        return {"Authorization": f"OAuth {self.api_token}"}

    async def request_vot(
        self,
        path: str,
        body: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Perform a request to the third-party VOT Backend service."""
        req_headers = self.headers_vot.copy()
        if headers:
            req_headers.update(headers)

        url = f"{self.schema_vot}://{self.host_vot}{path}"
        try:
            res = await self.client.post(url, headers=req_headers, json=body)
            return {
                "success": res.status_code == 200,
                "data": res.json() if res.status_code == 200 else res.text,
            }
        except Exception as e:
            return {
                "success": False,
                "data": str(e),
            }

    async def translate_video(
        self,
        video_data: VideoData,
        request_lang: str | None = None,
        response_lang: str | None = None,
        translation_help: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
        extra_opts: dict[str, Any] | None = None,
        should_send_failed_audio: bool = True,
    ) -> TranslationResponse:
        """Translate a video using Yandex or VOT backend depending on source URL."""
        if self.is_custom_link(video_data.url):
            return await self.translate_video_vot(
                video_data.url,
                video_data.video_id,
                video_data.host,
                request_lang=request_lang,
                response_lang=response_lang,
                headers=headers,
                extra_opts=extra_opts,
            )
        else:
            return await self.translate_video_ya(
                video_data,
                request_lang=request_lang,
                response_lang=response_lang,
                translation_help=translation_help,
                headers=headers,
                extra_opts=extra_opts,
                should_send_failed_audio=should_send_failed_audio,
            )

    async def translate_video_ya(
        self,
        video_data: VideoData,
        request_lang: str | None = None,
        response_lang: str | None = None,
        translation_help: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
        extra_opts: dict[str, Any] | None = None,
        should_send_failed_audio: bool = True,
    ) -> TranslationResponse:
        """Translate a video using the official Yandex API."""
        url = video_data.url
        duration = video_data.duration or config.DEFAULT_DURATION
        req_lang = request_lang or self.request_lang
        resp_lang = response_lang or self.response_lang
        opts = extra_opts or {}

        session = await self.get_session("video-translation")

        help_objs = []
        if translation_help:
            for item in translation_help:
                help_objs.append(
                    VideoTranslationHelpObject(
                        target=item.get("target", ""),
                        targetUrl=item.get("targetUrl", ""),
                    )
                )

        req = VideoTranslationRequest(
            url=url,
            firstRequest=opts.get("firstRequest", True),
            duration=duration,
            unknown0=1,
            language=req_lang,
            forceSourceLang=opts.get("forceSourceLang", False),
            unknown1=0,
            translationHelp=help_objs,
            responseLanguage=resp_lang,
            wasStream=opts.get("wasStream", False),
            unknown2=1,
            unknown3=2,
            bypassCache=opts.get("bypassCache", False),
            useLivelyVoice=opts.get("useLivelyVoice", False),
            videoTitle=opts.get("videoTitle", ""),
        )
        body = req.SerializeToString()

        path = self.paths["videoTranslation"]
        vtrans_headers = get_sec_ya_headers(
            "Vtrans",
            session["uuid"],
            session["secretKey"],
            body,
            path,
        )

        api_headers = self.api_token_header if opts.get("useLivelyVoice") else {}
        req_headers = {**vtrans_headers, **api_headers, **(headers or {})}

        res = await self.request(path, body, headers=req_headers)
        if not res["success"]:
            raise VOTJSError("Failed to request video translation", res)

        resp = VideoTranslationResponse()
        resp.ParseFromString(res["data"])

        # Status matching (0: failed, 1: finished, 2: waiting, 3: long_waiting, 4: audio_requested, 10: session_required)
        status = resp.status
        translation_id = resp.translationId
        remaining_time = resp.remainingTime if resp.HasField("remainingTime") else -1

        if status == 0:
            raise VOTJSError("Yandex couldn't translate video", resp)
        elif status in (1, 2):  # 1: Success / Finished, 2: Part Content
            if not resp.url:
                raise VOTJSError("Audio link wasn't received from Yandex response", resp)
            return TranslationResponse(
                translationId=translation_id,
                translated=True,
                url=resp.url,
                status=status,
                remainingTime=remaining_time,
            )
        elif status in (3, 5):  # 3: Waiting, 5: Long Waiting
            return TranslationResponse(
                translationId=translation_id,
                translated=False,
                status=status,
                remainingTime=remaining_time,
            )
        elif status == 4:  # Audio Requested
            if url.startswith("https://youtu.be/") and should_send_failed_audio:
                # Trigger fake failure / upload to bypass waiting loop on new videos
                await self.request_vtrans_fail_audio(url)
                await self.request_vtrans_audio(
                    url,
                    translation_id,
                    audio_file=b"",
                    file_id="web_api_get_all_generating_urls_data_from_iframe",
                )
                return await self.translate_video_ya(
                    video_data,
                    request_lang=request_lang,
                    response_lang=response_lang,
                    translation_help=translation_help,
                    headers=headers,
                    extra_opts=extra_opts,
                    should_send_failed_audio=False,
                )
            return TranslationResponse(
                translationId=translation_id,
                translated=False,
                status=status,
                remainingTime=remaining_time,
            )
        elif status == 10:
            raise VOTJSError("Yandex auth required to translate video. See docs.", resp)
        else:
            raise VOTJSError("Unknown response status from Yandex", resp)

    async def translate_video_vot(
        self,
        url: str,
        video_id: str,
        service: str,
        request_lang: str | None = None,
        response_lang: str | None = None,
        headers: dict[str, str] | None = None,
        extra_opts: dict[str, Any] | None = None,
    ) -> TranslationResponse:
        """Translate a video using the custom VOT backend service proxy."""
        req_lang = request_lang or self.request_lang
        resp_lang = response_lang or self.response_lang
        opts = extra_opts or {}
        provider = "yandex_lively" if opts.get("useLivelyVoice") else "yandex"

        payload = {
            "provider": provider,
            "service": "mux" if service == "patreon" else service,
            "video_id": url.split("/")[-1] if service == "patreon" else video_id,
            "from_lang": req_lang,
            "to_lang": resp_lang,
            "raw_video": url,
        }

        res = await self.request_vot(
            self.paths["videoTranslation"],
            payload,
            headers=headers,
        )
        if not res["success"]:
            raise VOTJSError("Failed to request video translation from VOT backend", res)

        data = res["data"]
        status = data.get("status")
        if status == "failed":
            raise VOTJSError("Yandex couldn't translate video via VOT backend", data)
        elif status == "success":
            return TranslationResponse(
                translationId=str(data.get("id", "")),
                translated=True,
                url=data.get("translated_url"),
                status=1,
                remainingTime=-1,
            )
        elif status == "waiting":
            return TranslationResponse(
                translationId="",
                translated=False,
                status=2,
                remainingTime=data.get("remaining_time", 120),
                message=data.get("message"),
            )
        else:
            raise VOTJSError("Unknown response status from VOT backend", data)

    async def request_vtrans_fail_audio(self, url: str) -> dict[str, Any]:
        """Send notification that client audio retrieval failed (triggering server-side fallback)."""
        res = await self.request_json(
            self.paths["videoTranslationFailAudio"],
            body={"video_url": url},
            method="PUT",
        )
        if not res["success"] or res["data"].get("status") != 1:
            raise VOTJSError("Failed to request video translation fail audio", res)
        return res

    async def request_vtrans_audio(
        self,
        url: str,
        translation_id: str,
        audio_file: bytes = b"",
        file_id: str = "",
        chunk_id: int | None = None,
        audio_parts_length: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> VideoTranslationAudioResponse:
        """Submit audio buffer segment for translating new/untranslated YouTube content."""
        session = await self.get_session("video-translation")

        req = VideoTranslationAudioRequest()
        req.translationId = translation_id
        req.url = url

        if chunk_id is not None and audio_parts_length is not None:
            # Partial audio uploads
            req.partialAudioInfo.audioBuffer.audioFile = audio_file
            req.partialAudioInfo.audioBuffer.chunkId = chunk_id
            req.partialAudioInfo.audioPartsLength = audio_parts_length
            req.partialAudioInfo.fileId = file_id
            req.partialAudioInfo.version = 1
        else:
            # Single chunk/file uploads
            req.audioInfo.audioFile = audio_file
            req.audioInfo.fileId = file_id

        body = req.SerializeToString()
        path = self.paths["videoTranslationAudio"]
        vtrans_headers = get_sec_ya_headers(
            "Vtrans",
            session["uuid"],
            session["secretKey"],
            body,
            path,
        )

        req_headers = {**vtrans_headers, **(headers or {})}
        res = await self.request(path, body, headers=req_headers, method="PUT")

        if not res["success"]:
            raise VOTJSError("Failed to request video translation audio", res)

        resp = VideoTranslationAudioResponse()
        resp.ParseFromString(res["data"])
        return resp

    async def translate_video_cache(
        self,
        video_data: VideoData,
        request_lang: str | None = None,
        response_lang: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> VideoTranslationCacheResponse:
        """Check cached translation status for a given video."""
        url = video_data.url
        duration = video_data.duration or config.DEFAULT_DURATION
        req_lang = request_lang or self.request_lang
        resp_lang = response_lang or self.response_lang

        session = await self.get_session("video-translation")

        req = VideoTranslationCacheRequest(
            url=url,
            duration=duration,
            language=req_lang,
            responseLanguage=resp_lang,
        )
        body = req.SerializeToString()

        path = self.paths["videoTranslationCache"]
        vtrans_headers = get_sec_ya_headers(
            "Vtrans",
            session["uuid"],
            session["secretKey"],
            body,
            path,
        )

        req_headers = {**vtrans_headers, **(headers or {})}
        res = await self.request(path, body, headers=req_headers)

        if not res["success"]:
            raise VOTJSError("Failed to request video translation cache", res)

        resp = VideoTranslationCacheResponse()
        resp.ParseFromString(res["data"])
        return resp

    async def get_subtitles(
        self,
        video_data: VideoData,
        request_lang: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> GetSubtitlesResponse:
        """Retrieve video subtitles using Yandex or VOT Backend depending on source URL."""
        if self.is_custom_link(video_data.url):
            return await self.get_subtitles_vot(
                video_data.url,
                video_data.video_id,
                video_data.host,
                headers=headers,
            )
        else:
            return await self.get_subtitles_ya(
                video_data,
                request_lang=request_lang,
                headers=headers,
            )

    async def get_subtitles_ya(
        self,
        video_data: VideoData,
        request_lang: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> GetSubtitlesResponse:
        """Retrieve video subtitles using the official Yandex API."""
        url = video_data.url
        req_lang = request_lang or self.request_lang

        session = await self.get_session("video-translation")

        req = SubtitlesRequest(url=url, language=req_lang)
        body = req.SerializeToString()

        path = self.paths["videoSubtitles"]
        vsubs_headers = get_sec_ya_headers(
            "Vsubs",
            session["uuid"],
            session["secretKey"],
            body,
            path,
        )

        req_headers = {**vsubs_headers, **(headers or {})}
        res = await self.request(path, body, headers=req_headers)

        if not res["success"]:
            raise VOTJSError("Failed to request video subtitles", res)

        resp = SubtitlesResponse()
        resp.ParseFromString(res["data"])

        subtitles = []
        for sub in resp.subtitles:
            subtitles.append(
                SubtitleItem(
                    language=sub.language,
                    url=sub.url,
                    translatedLanguage=sub.translatedLanguage,
                    translatedUrl=sub.translatedUrl,
                )
            )

        return GetSubtitlesResponse(
            waiting=resp.waiting,
            subtitles=subtitles,
        )

    async def get_subtitles_vot(
        self,
        url: str,
        video_id: str,
        service: str,
        headers: dict[str, str] | None = None,
    ) -> GetSubtitlesResponse:
        """Retrieve subtitles using the custom VOT backend service proxy."""
        payload = {
            "provider": "yandex",
            "service": "mux" if service == "patreon" else service,
            "video_id": url.split("/")[-1] if service == "patreon" else video_id,
        }

        res = await self.request_vot(
            self.paths["videoSubtitles"],
            payload,
            headers=headers,
        )
        if not res["success"]:
            raise VOTJSError("Failed to request video subtitles from VOT backend", res)

        items = res["data"]
        subtitles = []
        for sub in items:
            lang_from = sub.get("lang_from")
            if not lang_from:
                continue

            orig_sub = next((s for s in items if s.get("lang") == lang_from), None)
            if not orig_sub:
                continue

            subtitles.append(
                SubtitleItem(
                    language=orig_sub.get("lang", ""),
                    url=orig_sub.get("subtitle_url", ""),
                    translatedLanguage=sub.get("lang", ""),
                    translatedUrl=sub.get("subtitle_url", ""),
                )
            )

        return GetSubtitlesResponse(
            waiting=False,
            subtitles=subtitles,
        )

    async def ping_stream(
        self,
        ping_id: int,
        headers: dict[str, str] | None = None,
    ) -> bool:
        """Send standard stream keep-alive ping request to the Yandex translation server."""
        session = await self.get_session("video-translation")

        from vot.protobuf import StreamPingRequest

        req = StreamPingRequest(pingId=ping_id)
        body = req.SerializeToString()

        path = self.paths["streamPing"]
        vtrans_headers = get_sec_ya_headers(
            "Vtrans",
            session["uuid"],
            session["secretKey"],
            body,
            path,
        )

        req_headers = {**vtrans_headers, **(headers or {})}
        res = await self.request(path, body, headers=req_headers)

        if not res["success"]:
            raise VOTJSError("Failed to request stream ping", res)

        return True

    async def translate_stream(
        self,
        video_data: VideoData,
        request_lang: str | None = None,
        response_lang: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> StreamTranslationResponse:
        """Initiate translation for active streams."""
        url = video_data.url
        if self.is_custom_link(url):
            raise VOTJSError("Unsupported video URL for getting stream translation")

        session = await self.get_session("video-translation")
        req_lang = request_lang or self.request_lang
        resp_lang = response_lang or self.response_lang

        req = StreamTranslationRequest(
            url=url,
            language=req_lang,
            responseLanguage=resp_lang,
            unknown0=1,
            unknown1=0,
        )
        body = req.SerializeToString()

        path = self.paths["streamTranslation"]
        vtrans_headers = get_sec_ya_headers(
            "Vtrans",
            session["uuid"],
            session["secretKey"],
            body,
            path,
        )

        req_headers = {**vtrans_headers, **(headers or {})}
        res = await self.request(path, body, headers=req_headers)

        if not res["success"]:
            raise VOTJSError("Failed to request stream translation", res)

        resp = StreamProtoResponse()
        resp.ParseFromString(res["data"])

        # interval: 0 - NO_CONNECTION, 10 - TRANSLATING, 20 - STREAMING
        interval = resp.interval
        if interval in (0, 10):
            msg = "streamNoConnectionToServer" if interval == 0 else "translationTakeFewMinutes"
            return StreamTranslationResponse(
                translated=False,
                interval=interval,
                message=msg,
            )
        elif interval == 20:
            if not resp.HasField("pingId"):
                raise VOTJSError("Stream ping id wasn't received from Yandex response", resp)

            info = StreamTranslationObject(
                url=resp.translatedInfo.url,
                timestamp=resp.translatedInfo.timestamp,
            )
            return StreamTranslationResponse(
                translated=True,
                interval=interval,
                pingId=resp.pingId,
                result=info,
            )
        else:
            raise VOTJSError("Unknown stream response status from Yandex", resp)


class VOTWorkerClient(VOTClient):
    """VOTWorkerClient wrapping payload and request parameters into Cloudflare Worker JSON arrays."""

    def __init__(
        self,
        host: str = config.HOST_WORKER,
        client: httpx.AsyncClient | None = None,
        request_lang: str = "en",
        response_lang: str = "ru",
        api_token: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(
            host=host,
            client=client,
            request_lang=request_lang,
            response_lang=response_lang,
            api_token=api_token,
            headers=headers,
        )

    async def request(
        self,
        path: str,
        body: bytes,
        headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> dict[str, Any]:
        """Override request to send JSON array bytes to Cloudflare Worker."""
        req_headers = {
            "Content-Type": "application/json",
        }
        payload = {
            "headers": {**self.headers, **(headers or {})},
            "body": list(body),
        }

        url = f"{self.schema}://{self.host}{path}"
        try:
            res = await self.client.post(
                url,
                headers=req_headers,
                json=payload,
            )
            return {
                "success": res.status_code == 200,
                "data": res.content,
            }
        except Exception as e:
            return {
                "success": False,
                "data": str(e).encode("utf-8"),
            }

    async def request_json(
        self,
        path: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
        method: str = "POST",
    ) -> dict[str, Any]:
        """Override request_json to wrap headers/body for Worker proxying."""
        req_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "headers": {
                **self.headers,
                "Content-Type": "application/json",
                "Accept": "application/json",
                **(headers or {}),
            },
            "body": body,
        }

        url = f"{self.schema}://{self.host}{path}"
        try:
            res = await self.client.post(
                url,
                headers=req_headers,
                json=payload,
            )
            return {
                "success": res.status_code == 200,
                "data": res.json() if res.status_code == 200 else res.text,
            }
        except Exception as e:
            return {
                "success": False,
                "data": str(e),
            }


class VOTClientSync:
    """Synchronous wrapper around VOTClient's asynchronous operations."""

    def __init__(
        self,
        host: str = config.HOST,
        host_vot: str = config.HOST_VOT,
        request_lang: str = "en",
        response_lang: str = "ru",
        api_token: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._async_client = httpx.AsyncClient(timeout=10.0)
        self.client = VOTClient(
            host=host,
            host_vot=host_vot,
            client=self._async_client,
            request_lang=request_lang,
            response_lang=response_lang,
            api_token=api_token,
            headers=headers,
        )

    def _run(self, coro: Coroutine[Any, Any, T]) -> T:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            import threading
            from concurrent.futures import Future

            def run_in_thread(coro_fn: Any, fut: Future[Any]) -> None:
                thr_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(thr_loop)
                try:
                    result = thr_loop.run_until_complete(coro_fn)
                    fut.set_result(result)
                except Exception as ex:
                    fut.set_exception(ex)
                finally:
                    thr_loop.close()

            future: Future[Any] = Future()
            t = threading.Thread(target=run_in_thread, args=(coro, future))
            t.start()
            t.join()
            return cast(T, future.result())
        else:
            return loop.run_until_complete(coro)

    def close(self) -> None:
        """Close the underlying client connection pool."""
        self._run(self._async_client.aclose())

    def __enter__(self) -> "VOTClientSync":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def translate_video(
        self,
        video_data: VideoData,
        request_lang: str | None = None,
        response_lang: str | None = None,
        translation_help: list[dict[str, str]] | None = None,
        headers: dict[str, str] | None = None,
        extra_opts: dict[str, Any] | None = None,
        should_send_failed_audio: bool = True,
    ) -> TranslationResponse:
        """Synchronously translate a video."""
        return self._run(
            self.client.translate_video(
                video_data,
                request_lang=request_lang,
                response_lang=response_lang,
                translation_help=translation_help,
                headers=headers,
                extra_opts=extra_opts,
                should_send_failed_audio=should_send_failed_audio,
            )
        )

    def get_subtitles(
        self,
        video_data: VideoData,
        request_lang: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> GetSubtitlesResponse:
        """Synchronously retrieve subtitles."""
        return self._run(
            self.client.get_subtitles(
                video_data,
                request_lang=request_lang,
                headers=headers,
            )
        )

    def translate_video_cache(
        self,
        video_data: VideoData,
        request_lang: str | None = None,
        response_lang: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> VideoTranslationCacheResponse:
        """Synchronously retrieve cached translation status."""
        return self._run(
            self.client.translate_video_cache(
                video_data,
                request_lang=request_lang,
                response_lang=response_lang,
                headers=headers,
            )
        )

    def ping_stream(
        self,
        ping_id: int,
        headers: dict[str, str] | None = None,
    ) -> bool:
        """Synchronously ping active translation stream."""
        return self._run(self.client.ping_stream(ping_id, headers=headers))

    def translate_stream(
        self,
        video_data: VideoData,
        request_lang: str | None = None,
        response_lang: str | None = None,
        headers: dict[str, str] | None = None,
    ) -> StreamTranslationResponse:
        """Synchronously translate an active stream."""
        return self._run(
            self.client.translate_stream(
                video_data,
                request_lang=request_lang,
                response_lang=response_lang,
                headers=headers,
            )
        )
