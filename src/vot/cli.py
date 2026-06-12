import argparse
import asyncio
import sys

import httpx

from vot import VOTClient, get_video_data
from vot.exceptions import VOTError


async def run_translation(
    url: str,
    lang_from: str,
    lang_to: str,
    output_path: str | None = None,
    fetch_subs: bool = False,
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

        # Retrieve subtitles if requested
        if fetch_subs:
            print("\nFetching subtitles...")
            try:
                subs_response = await client.get_subtitles(video_data, request_lang=lang_from)
                if subs_response.subtitles:
                    print(f"Found {len(subs_response.subtitles)} subtitles:")
                    for idx, sub in enumerate(subs_response.subtitles):
                        print(
                            f"  [{idx + 1}] Language: {sub.language} -> {sub.translated_language or ''}"
                        )
                        print(f"      Original Subtitle URL: {sub.url}")
                        if sub.translated_url:
                            print(f"      Translated Subtitle URL: {sub.translated_url}")
                else:
                    print("No subtitles found.")
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

    args = parser.parse_args()

    try:
        asyncio.run(
            run_translation(
                url=args.url,
                lang_from=args.lang_from,
                lang_to=args.lang_to,
                output_path=args.output,
                fetch_subs=args.subtitles,
            )
        )
    except KeyboardInterrupt:
        print("\nTranslation cancelled by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
