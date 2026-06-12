import pytest
from vot.utils.url import get_service, get_video_id, get_video_data
from vot.exceptions import VideoDataError


def test_get_service() -> None:
    # Test YouTube
    assert get_service("https://www.youtube.com/watch?v=dQw4w9WgXcQ")["host"] == "youtube"
    assert get_service("https://youtu.be/dQw4w9WgXcQ")["host"] == "youtube"
    assert get_service("https://m.youtube.com/shorts/dQw4w9WgXcQ")["host"] == "youtube"

    # Test Invidious
    assert get_service("https://yewtu.be/watch?v=dQw4w9WgXcQ")["host"] == "invidious"

    # Test VK
    assert get_service("https://vk.com/video-12345_67890")["host"] == "vk"

    # Test Twitch
    assert get_service("https://www.twitch.tv/videos/1234567")["host"] == "twitch"

    # Test Custom
    assert get_service("https://example.com/video.mp4")["host"] == "custom"
    assert get_service("https://example.com/video.webm")["host"] == "custom"

    # Unknown
    assert get_service("https://example.com/page") is None


@pytest.mark.asyncio
async def test_get_video_id_youtube() -> None:
    service = {"host": "youtube"}

    # watch?v=
    assert await get_video_id(service, "https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    # youtu.be
    assert await get_video_id(service, "https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    # shorts
    assert await get_video_id(service, "https://www.youtube.com/shorts/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    # embed
    assert await get_video_id(service, "https://www.youtube.com/embed/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    # attribution_link
    assert await get_video_id(service, "https://www.youtube.com/attribution_link?u=%2Fwatch%3Fv%3DdQw4w9WgXcQ%26feature%3Dshare") == "dQw4w9WgXcQ"


@pytest.mark.asyncio
async def test_get_video_id_others() -> None:
    # VK
    vk_service = {"host": "vk"}
    assert await get_video_id(vk_service, "https://vk.com/video-12345_67890") == "video-12345_67890"

    # Custom
    custom_service = {"host": "custom"}
    assert await get_video_id(custom_service, "https://example.com/movie.mp4") == "https://example.com/movie.mp4"


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
