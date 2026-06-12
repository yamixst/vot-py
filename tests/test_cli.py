from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vot.cli import main, run_translation
from vot.models import GetSubtitlesResponse, SubtitleItem, VideoData


@patch("vot.cli.run_translation", new_callable=AsyncMock)
def test_cli_parser_defaults(mock_run_translation: AsyncMock) -> None:
    with patch("sys.argv", ["vot", "https://youtube.com/watch?v=123"]):
        main()
        mock_run_translation.assert_called_once_with(
            url="https://youtube.com/watch?v=123",
            lang_from="en",
            lang_to="ru",
            output_path=None,
            fetch_subs=False,
            output_subs_path=None,
        )


@pytest.mark.asyncio
@patch("vot.cli.get_video_data", new_callable=AsyncMock)
@patch("builtins.open", new_callable=MagicMock)
async def test_run_translation_only_subs(
    mock_open: MagicMock, mock_get_video_data: AsyncMock
) -> None:
    # Set up resolved video metadata
    mock_get_video_data.return_value = VideoData(
        url="https://youtube.com/watch?v=123", videoId="123", host="youtube"
    )

    # Mock translation response so we exit the loop immediately
    translation_response_mock = MagicMock()
    translation_response_mock.translated = True
    translation_response_mock.url = "https://r2.yandex.ru/audio.mp3"

    # Mock subtitles response using Pydantic models (using alias names for constructor to satisfy type checkers)
    sub_item = SubtitleItem(
        language="en",
        url="https://yandex.ru/subs_en.vtt",
        translatedLanguage="ru",
        translatedUrl="https://yandex.ru/subs_ru.vtt",
    )
    subtitles_response_mock = GetSubtitlesResponse(waiting=False, subtitles=[sub_item])

    # Setup the clients
    with (
        patch("vot.cli.VOTClient") as mock_client_cls,
        patch("httpx.AsyncClient") as mock_http_client_cls,
    ):
        mock_client = MagicMock()
        mock_client.translate_video = AsyncMock(return_value=translation_response_mock)
        mock_client.get_subtitles = AsyncMock(return_value=subtitles_response_mock)
        mock_client_cls.return_value = mock_client

        mock_http_client = MagicMock()
        # Mocking the GET requests for audio and subtitles
        audio_res_mock = MagicMock()
        audio_res_mock.status_code = 200
        audio_res_mock.content = b"audio content"

        subs_res_mock = MagicMock()
        subs_res_mock.status_code = 200
        subs_res_mock.text = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello"
        subs_res_mock.content = b"WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello"

        async def mock_get(url: str, *args: Any, **kwargs: Any) -> MagicMock:
            if "audio.mp3" in url:
                return audio_res_mock
            return subs_res_mock

        mock_http_client.get = AsyncMock(side_effect=mock_get)
        mock_http_client_cls.return_value.__aenter__.return_value = mock_http_client

        # Mock writing to files
        file_handle_mock = MagicMock()
        mock_open.return_value.__enter__.return_value = file_handle_mock

        await run_translation(
            url="https://youtube.com/watch?v=123",
            lang_from="en",
            lang_to="ru",
            output_path="audio.mp3",
            fetch_subs=True,
            output_subs_path="subs.srt",
        )

        mock_get_video_data.assert_called_once()
        mock_client.translate_video.assert_called_once()
        mock_client.get_subtitles.assert_called_once()

        # Check that we wrote the files: audio.mp3 and subs.srt
        # Since it converted to srt, it should have written srt content
        mock_open.assert_any_call("audio.mp3", "wb")
        mock_open.assert_any_call("subs.srt", "w", encoding="utf-8")
        file_handle_mock.write.assert_any_call("1\n00:00:01,000 --> 00:00:03,000\nHello")
