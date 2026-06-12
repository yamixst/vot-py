import re
from typing import Any


def convert_to_str_time(ms: float, delimiter: str = ",") -> str:
    """Convert milliseconds to string time format (00:00:00,000)."""
    seconds = ms / 1000.0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remaining_seconds = int(seconds % 60)
    milliseconds = int(ms % 1000)

    return f"{hours:02d}:{minutes:02d}:{remaining_seconds:02d}{delimiter}{milliseconds:03d}"


def convert_to_ms_time(time_str: str) -> int:
    """Convert string time format (00:00:00,000 or 00:00,000) to milliseconds."""
    parts = time_str.split(" ")[0].split(":")
    if len(parts) < 3:
        parts.insert(0, "00")

    str_hours, str_minutes, str_seconds = parts

    # clean trailing delimiters and extract secs and millisecs
    cleaned_seconds = re.sub(r"[,.]", "", str_seconds)
    # If the clean seconds string is shorter than expected (e.g. no millis), pad it
    if len(cleaned_seconds) < 5:
        # e.g. "05" -> 5000 ms, "051" -> 510 ms, let's treat the end as milliseconds
        # Wait, if original was "05.1" -> cleaned is "051".
        # Let's parse float of the seconds part
        val_sec = float(str_seconds.replace(",", "."))
        secs_ms = int(val_sec * 1000)
    else:
        # standard "05123" -> seconds is 05, milliseconds is 123
        # parts are standard HH:MM:SS,mmm or HH:MM:SS.mmm
        # Let's just parse the float to avoid precision issues
        val_sec = float(str_seconds.replace(",", "."))
        secs_ms = int(val_sec * 1000)

    mins = int(str_minutes) * 60_000
    hours = int(str_hours) * 3_600_000
    return hours + mins + secs_ms


def convert_subs_from_json(data: dict[str, Any], output: str = "srt") -> str:
    """Convert subtitles from JSON structure to SRT or VTT format."""
    is_vtt = output == "vtt"
    delimiter = "." if is_vtt else ","
    subs_list = data.get("subtitles", [])

    formatted_subs = []
    for idx, sub in enumerate(subs_list):
        start_ms = sub.get("startMs", sub.get("start_ms", 0))
        duration_ms = sub.get("durationMs", sub.get("duration_ms", 0))
        text = sub.get("text", "")

        prefix = "" if is_vtt else f"{idx + 1}\n"
        start_time = convert_to_str_time(start_ms, delimiter)
        end_time = convert_to_str_time(start_ms + duration_ms, delimiter)

        formatted_subs.append(f"{prefix}{start_time} --> {end_time}\n{text}")

    subs_str = "\n\n".join(formatted_subs).strip()
    return f"WEBVTT\n\n{subs_str}" if is_vtt else subs_str


def convert_subs_to_json(data: str, from_format: str = "srt") -> dict[str, Any]:
    """Convert SRT or VTT subtitles to JSON format."""
    parts = re.split(r"\r?\n\r?\n", data)
    if from_format == "vtt" and parts:
        parts.pop(0)  # remove WEBVTT header

    if not parts:
        return {"containsTokens": False, "subtitles": []}

    # Check if we have indices (SRT style)
    if parts and re.match(r"^\d+\r?\n", parts[0].strip()):
        from_format = "srt"

    offset = 1 if from_format == "srt" else 0
    subtitles: list[dict[str, Any]] = []

    for part in parts:
        lines = [line.strip() for line in part.strip().split("\n") if line.strip()]
        if not lines:
            continue

        if len(lines) <= offset:
            continue

        time_line = lines[offset]
        text_lines = lines[offset + 1 :]
        text = "\n".join(text_lines)

        if " --> " not in time_line:
            if not subtitles:
                continue
            # Append multi-line paragraph to the previous item
            subtitles[-1]["text"] = f"{subtitles[-1]['text']}\n\n{part.strip()}"
            continue

        time_parts = time_line.split(" --> ")
        if len(time_parts) < 2:
            continue

        start_time, end_time = time_parts[:2]
        start_ms = convert_to_ms_time(start_time)
        end_ms = convert_to_ms_time(end_time)
        duration_ms = end_ms - start_ms

        subtitles.append(
            {
                "text": text,
                "startMs": start_ms,
                "durationMs": duration_ms,
                "speakerId": "0",
            }
        )

    return {
        "containsTokens": False,
        "subtitles": subtitles,
    }


def get_subs_format(data: dict[str, Any] | str) -> str:
    """Detect subtitle format."""
    if not isinstance(data, str):
        return "json"
    if re.match(r"^(WEBVTT([^\n]*)?)(\r?\n)", data):
        return "vtt"
    return "srt"


def convert_subs(data: dict[str, Any] | str, output: str = "srt") -> dict[str, Any] | str:
    """Convert subtitles between JSON, SRT, and VTT formats."""
    from_format = get_subs_format(data)
    if from_format == output:
        return data

    if from_format == "json":
        assert isinstance(data, dict)
        return convert_subs_from_json(data, output)

    assert isinstance(data, str)
    json_data = convert_subs_to_json(data, from_format)
    if output == "json":
        return json_data

    return convert_subs_from_json(json_data, output)
