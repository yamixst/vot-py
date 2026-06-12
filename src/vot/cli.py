import argparse
import asyncio
import json
import sys
from typing import Any

import httpx

from vot import VOTClient, get_video_data
from vot.exceptions import VOTError
from vot.models import SubtitleItem
from vot.utils.subs import convert_subs


def print_subtitles_info(subtitles: list[SubtitleItem]) -> None:
    """Print details of available subtitles."""
    print(f"Found {len(subtitles)} subtitles:")
    for idx, sub in enumerate(subtitles):
        print(f"  [{idx + 1}] Language: {sub.language} -> {sub.translated_language or ''}")
        print(f"      Original Subtitle URL: {sub.url}")
        if sub.translated_url:
            print(f"      Translated Subtitle URL: {sub.translated_url}")


async def download_and_save_subtitles(
    http_client: httpx.AsyncClient, sub_url: str, output_path: str
) -> None:
    """Download subtitle file from url, convert if format differs from output extension, and save."""
    print(f"Downloading subtitles to {output_path}...")
    try:
        res = await http_client.get(sub_url)
    except Exception as e:
        print(f"Failed to request subtitles: {e}", file=sys.stderr)
        return

    if res.status_code != 200:
        print(f"Error downloading subtitles: HTTP {res.status_code}", file=sys.stderr)
        return

    content = res.text
    ext_from = "vtt" if ".vtt" in sub_url else "json" if ".json" in sub_url else "srt"
    ext_to = output_path.split(".")[-1].lower() if "." in output_path else "vtt"

    if ext_to not in ("srt", "vtt", "json") or ext_from == ext_to:
        # Save raw content directly
        try:
            with open(output_path, "wb") as f:
                f.write(res.content)
            print("Subtitles saved successfully!")
        except Exception as e:
            print(f"Failed to write raw subtitles file: {e}", file=sys.stderr)
        return

    # Convert format
    try:
        raw_data: Any = json.loads(content) if ext_from == "json" else content
        converted = convert_subs(raw_data, output=ext_to)

        if ext_to == "json":
            content_to_write = json.dumps(converted, ensure_ascii=False, indent=2)
        else:
            content_to_write = str(converted)

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(content_to_write)
        print(
            f"Subtitles converted from {ext_from.upper()} to {ext_to.upper()} and saved successfully!"
        )
    except Exception as err:
        print(
            f"Failed to convert subtitles format: {err}. Saving raw file instead.",
            file=sys.stderr,
        )
        try:
            with open(output_path, "wb") as f:
                f.write(res.content)
        except Exception as write_err:
            print(
                f"Failed to write raw subtitles file after failed conversion: {write_err}",
                file=sys.stderr,
            )


async def run_translation(
    url: str,
    lang_from: str,
    lang_to: str,
    output_path: str | None = None,
    fetch_subs: bool = False,
    output_subs_path: str | None = None,
) -> None:
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        client = VOTClient(
            client=http_client,
            request_lang=lang_from,
            response_lang=lang_to,
        )

        try:
            print(f"Resolving video data for: {url}...")
            video_data = await get_video_data(url, client=http_client)
            print(f"Resolved service: '{video_data.host}', video ID: '{video_data.video_id}'")
        except VOTError as e:
            print(f"Error resolving URL: {e}", file=sys.stderr)
            sys.exit(1)

        # Poll translation status
        print("Requesting translation from Yandex...")
        while True:
            try:
                response = await client.translate_video(
                    video_data,
                    request_lang=lang_from,
                    response_lang=lang_to,
                )
                if response.translated and response.url:
                    print(f"\nSuccess! Translated Audio URL:\n{response.url}")

                    # Download file if output_path is provided
                    if output_path:
                        print(f"Downloading audio to {output_path}...")
                        audio_res = await http_client.get(response.url)
                        if audio_res.status_code == 200:
                            with open(output_path, "wb") as f:
                                f.write(audio_res.content)
                            print("Download completed successfully!")
                        else:
                            print(
                                f"Error downloading audio: HTTP {audio_res.status_code}",
                                file=sys.stderr,
                            )
                    break
                else:
                    wait_time = response.remaining_time if response.remaining_time > 0 else 15
                    print(
                        f"Translation is in progress (status: {response.status}). "
                        f"Waiting {wait_time} seconds before retrying...",
                        end="\r",
                        flush=True,
                    )
                    await asyncio.sleep(wait_time)
            except VOTError as e:
                print(f"\nAPI Error: {e}", file=sys.stderr)
                sys.exit(1)

        # Retrieve subtitles if requested or output path is provided
        if not (fetch_subs or output_subs_path):
            return

        print("\nFetching subtitles...")
        try:
            subs_response = await client.get_subtitles(video_data, request_lang=lang_from)
            if not subs_response.subtitles:
                print("No subtitles found.")
                return

            if fetch_subs:
                print_subtitles_info(subs_response.subtitles)

            if output_subs_path:
                # Prefer translated subtitles, fallback to original
                sub_to_download = next(
                    (sub.translated_url for sub in subs_response.subtitles if sub.translated_url),
                    subs_response.subtitles[0].url,
                )

                if sub_to_download:
                    await download_and_save_subtitles(
                        http_client, sub_to_download, output_subs_path
                    )
                else:
                    print("No valid subtitle URL found to download.", file=sys.stderr)
        except VOTError as e:
            print(f"Failed to fetch subtitles: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="vot-py CLI: Translate videos using Yandex Video Translation API"
    )
    parser.add_argument("url", help="URL of the video to translate (e.g. YouTube, Vimeo, Twitch)")
    parser.add_argument(
        "-f",
        "--lang-from",
        default="en",
        help="Source language of the video (default: 'en', 'auto' is also supported)",
    )
    parser.add_argument(
        "-t",
        "--lang-to",
        default="ru",
        help="Target language of the translation (default: 'ru')",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Save the translated audio file to this local path",
    )
    parser.add_argument(
        "-s",
        "--subtitles",
        action="store_true",
        help="Fetch and print available subtitle links",
    )
    parser.add_argument(
        "--output-subs",
        help="Save the translated subtitles file to this local path (supports .srt, .vtt, .json)",
    )

    args = parser.parse_args()

    try:
        asyncio.run(
            run_translation(
                url=args.url,
                lang_from=args.lang_from,
                lang_to=args.lang_to,
                output_path=args.output,
                fetch_subs=args.subtitles,
                output_subs_path=args.output_subs,
            )
        )
    except KeyboardInterrupt:
        print("\nTranslation cancelled by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
