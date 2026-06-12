import pytest

from vot.exceptions import VideoDataError
from vot.utils.url import get_service, get_video_data, get_video_id


def test_get_service() -> None:
    def check_host(url: str) -> str | None:
        res = get_service(url)
        return res["host"] if res else None

    # Test YouTube
    assert check_host("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "youtube"
    assert check_host("https://youtu.be/dQw4w9WgXcQ") == "youtube"
    assert check_host("https://m.youtube.com/shorts/dQw4w9WgXcQ") == "youtube"

    # Test Invidious
    assert check_host("https://yewtu.be/watch?v=dQw4w9WgXcQ") == "invidious"

    # Test VK
    assert check_host("https://vk.com/video-12345_67890") == "vk"

    # Test Twitch
    assert check_host("https://www.twitch.tv/videos/1234567") == "twitch"

    # Test Custom
    assert check_host("https://example.com/video.mp4") == "custom"
    assert check_host("https://example.com/video.webm") == "custom"

    # Unknown
    assert get_service("https://example.com/page") is None


@pytest.mark.asyncio
async def test_get_video_id_youtube() -> None:
    service = {"host": "youtube"}

    # watch?v=
    assert (
        await get_video_id(service, "https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    )
    # youtu.be
    assert await get_video_id(service, "https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    # shorts
    assert (
        await get_video_id(service, "https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    )
    # embed
    assert await get_video_id(service, "https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    # attribution_link
    assert (
        await get_video_id(
            service,
            "https://www.youtube.com/attribution_link?u=%2Fwatch%3Fv%3DdQw4w9WgXcQ%26feature%3Dshare",
        )
        == "dQw4w9WgXcQ"
    )


@pytest.mark.asyncio
async def test_get_video_id_others() -> None:
    # VK
    vk_service = {"host": "vk"}
    assert await get_video_id(vk_service, "https://vk.com/video-12345_67890") == "video-12345_67890"

    # Custom
    custom_service = {"host": "custom"}
    assert (
        await get_video_id(custom_service, "https://example.com/movie.mp4")
        == "https://example.com/movie.mp4"
    )


@pytest.mark.asyncio
async def test_get_video_data() -> None:
    # Standard link
    data = await get_video_data("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert data.host == "youtube"
    assert data.video_id == "dQw4w9WgXcQ"
    assert data.url == "https://youtu.be/dQw4w9WgXcQ"

    # Custom direct link
    data_custom = await get_video_data("https://example.com/movie.mp4")
    assert data_custom.host == "custom"
    assert data_custom.video_id == "https://example.com/movie.mp4"
    assert data_custom.url == "https://example.com/movie.mp4"

    # Error link
    with pytest.raises(VideoDataError):
        await get_video_data("https://example.com/invalid_page")
