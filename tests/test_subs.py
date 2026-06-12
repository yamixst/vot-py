from vot.utils.subs import convert_subs, get_subs_format


def test_get_subs_format() -> None:
    json_subs = {
        "containsTokens": False,
        "subtitles": [{"text": "Hello", "startMs": 1000, "durationMs": 2000}],
    }
    assert get_subs_format(json_subs) == "json"

    vtt_subs = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello"
    assert get_subs_format(vtt_subs) == "vtt"

    srt_subs = "1\n00:00:01,000 --> 00:00:03,000\nHello"
    assert get_subs_format(srt_subs) == "srt"


def test_convert_json_to_srt() -> None:
    json_subs = {
        "containsTokens": False,
        "subtitles": [{"text": "Hello", "startMs": 1000, "durationMs": 2000}],
    }
    expected_srt = "1\n00:00:01,000 --> 00:00:03,000\nHello"
    assert convert_subs(json_subs, "srt") == expected_srt


def test_convert_json_to_vtt() -> None:
    json_subs = {
        "containsTokens": False,
        "subtitles": [{"text": "Hello", "startMs": 1000, "durationMs": 2000}],
    }
    expected_vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello"
    assert convert_subs(json_subs, "vtt") == expected_vtt


def test_convert_srt_to_json() -> None:
    srt_subs = "1\n00:00:01,000 --> 00:00:03,000\nHello"
    expected_json = {
        "containsTokens": False,
        "subtitles": [
            {
                "text": "Hello",
                "startMs": 1000,
                "durationMs": 2000,
                "speakerId": "0",
            }
        ],
    }
    assert convert_subs(srt_subs, "json") == expected_json


def test_convert_vtt_to_json() -> None:
    vtt_subs = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello"
    expected_json = {
        "containsTokens": False,
        "subtitles": [
            {
                "text": "Hello",
                "startMs": 1000,
                "durationMs": 2000,
                "speakerId": "0",
            }
        ],
    }
    assert convert_subs(vtt_subs, "json") == expected_json


def test_convert_vtt_to_srt() -> None:
    vtt_subs = "WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nHello"
    expected_srt = "1\n00:00:01,000 --> 00:00:03,000\nHello"
    assert convert_subs(vtt_subs, "srt") == expected_srt
