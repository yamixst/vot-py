from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vot.client import VOTClient, VOTClientSync
from vot.models import VideoData
from vot.protobuf import (
    SubtitlesObject,
    SubtitlesResponse,
    VideoTranslationResponse,
    YandexSessionResponse,
)


@pytest.mark.asyncio
async def test_create_session() -> None:
    client = VOTClient()

    # Prepare mocked protobuf response
    session_proto = YandexSessionResponse(secretKey="testsecret", expires=3600)
    mock_response = {
        "success": True,
        "data": session_proto.SerializeToString(),
    }

    with patch.object(client, "request", new_callable=AsyncMock) as mock_request:
        mock_request.return_value = mock_response

        session = await client.get_session("video-translation")
        assert session["secretKey"] == "testsecret"
        assert session["expires"] == 3600
        assert "uuid" in session

        # Verify session caching
        cached_session = await client.get_session("video-translation")
        assert cached_session["secretKey"] == "testsecret"
        # Since it's cached, request shouldn't be called again
        assert mock_request.call_count == 1


@pytest.mark.asyncio
async def test_translate_video_ya() -> None:
    client = VOTClient()
    video_data = VideoData(
        url="https://youtu.be/dQw4w9WgXcQ", videoId="dQw4w9WgXcQ", host="youtube"
    )

    with patch.object(client, "get_session", new_callable=AsyncMock) as mock_get_session:
        mock_get_session.return_value = {
            "secretKey": "testsecret",
            "expires": 3600,
            "uuid": "testuuid",
        }

        # Prepare mocked translation response
        trans_proto = VideoTranslationResponse(
            status=1,  # Success/Finished
            translationId="trans123",
            url="https://r2.yandex.ru/audio.mp3",
            remainingTime=0,
        )
        mock_response = {
            "success": True,
            "data": trans_proto.SerializeToString(),
        }

        with patch.object(client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            res = await client.translate_video(video_data)
            assert res.translated is True
            assert res.translation_id == "trans123"
            assert res.url == "https://r2.yandex.ru/audio.mp3"


@pytest.mark.asyncio
async def test_get_subtitles_ya() -> None:
    client = VOTClient()
    video_data = VideoData(
        url="https://youtu.be/dQw4w9WgXcQ", videoId="dQw4w9WgXcQ", host="youtube"
    )

    with patch.object(client, "get_session", new_callable=AsyncMock) as mock_get_session:
        mock_get_session.return_value = {
            "secretKey": "testsecret",
            "expires": 3600,
            "uuid": "testuuid",
        }

        # Prepare subtitles mock response
        sub_item = SubtitlesObject(
            language="en",
            url="https://yandex.ru/subs_en.vtt",
            translatedLanguage="ru",
            translatedUrl="https://yandex.ru/subs_ru.vtt",
        )
        sub_proto = SubtitlesResponse(waiting=False, subtitles=[sub_item])
        mock_response = {
            "success": True,
            "data": sub_proto.SerializeToString(),
        }

        with patch.object(client, "request", new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_response

            res = await client.get_subtitles(video_data)
            assert res.waiting is False
            assert len(res.subtitles) == 1
            assert res.subtitles[0].language == "en"
            assert res.subtitles[0].translated_language == "ru"


def test_sync_client_wrapper() -> None:
    with VOTClientSync() as sync_client:
        video_data = VideoData(
            url="https://youtu.be/dQw4w9WgXcQ", videoId="dQw4w9WgXcQ", host="youtube"
        )

        # Mock translate_video on the async client
        trans_res = MagicMock()
        with patch.object(
            sync_client.client, "translate_video", new_callable=AsyncMock
        ) as mock_translate:
            mock_translate.return_value = trans_res

            res = sync_client.translate_video(video_data)
            assert res == trans_res
            mock_translate.assert_called_once_with(
                video_data,
                request_lang=None,
                response_lang=None,
                translation_help=None,
                headers=None,
                extra_opts=None,
                should_send_failed_audio=True,
            )
