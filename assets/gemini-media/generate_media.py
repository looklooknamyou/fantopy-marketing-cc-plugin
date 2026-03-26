#!/usr/bin/env python3
"""
Marketing media asset generator using Google Gemini API.

Reads media-brief.json from the current directory, generates images (Imagen 3)
and video clips (Veo 2), and saves outputs to the parent directory.

Usage:
    python3 generate_media.py

Requires:
    - GEMINI_API_KEY or GOOGLE_API_KEY environment variable
    - google-genai package (pip install google-genai)
"""

import base64
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

try:
    from google import genai
    from google.genai import types
except ImportError:
    print("[media] Error: google-genai not installed. Run: pip install google-genai")
    sys.exit(1)

# Configuration
IMAGE_MODEL = "gemini-2.0-flash-exp"
VIDEO_MODEL = "veo-2.0-generate-001"
VIDEO_POLL_INTERVAL = 20  # seconds
VIDEO_TIMEOUT = 600  # 10 minutes
OUTPUT_DIR = Path("..")


def get_client():
    """Initialize Gemini client with API key."""
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("[media] Error: GEMINI_API_KEY or GOOGLE_API_KEY not set")
        sys.exit(1)
    return genai.Client(api_key=api_key)


def generate_image(client, prompt, aspect_ratio="16:9", output_path="image.png"):
    """Generate a single image from a text prompt."""
    print(f"[media] Generating image: {output_path}")
    print(f"[media]   Prompt: {prompt[:80]}...")
    print(f"[media]   Aspect ratio: {aspect_ratio}")

    try:
        response = client.models.generate_content(
            model=IMAGE_MODEL,
            contents=[prompt],
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        # Extract base64 image data from response
        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                image_bytes = base64.b64decode(part.inline_data.data)
                full_path = OUTPUT_DIR / output_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                with open(full_path, "wb") as f:
                    f.write(image_bytes)
                size_kb = len(image_bytes) / 1024
                print(f"[media]   Saved: {full_path} ({size_kb:.0f} KB)")
                return str(full_path)

        print(f"[media]   Warning: No image data in response for {output_path}")
        return None

    except Exception as e:
        print(f"[media]   Error generating {output_path}: {e}")
        return None


def generate_video(client, prompt, duration=8, output_path="video.mp4"):
    """Generate a video clip from a text prompt (async operation)."""
    print(f"[media] Generating video: {output_path}")
    print(f"[media]   Prompt: {prompt[:80]}...")
    print(f"[media]   Duration: {duration}s")

    try:
        # Start async video generation
        operation = client.models.generate_videos(
            model=VIDEO_MODEL,
            prompt=prompt,
            config=types.GenerateVideosConfig(
                number_of_videos=1,
                duration_seconds=duration,
                enhance_prompt=True,
            ),
        )

        print(f"[media]   Operation started: {operation.name}")

        # Poll until complete
        start_time = time.time()
        while time.time() - start_time < VIDEO_TIMEOUT:
            time.sleep(VIDEO_POLL_INTERVAL)
            elapsed = int(time.time() - start_time)

            operation = client.operations.get(operation)

            if operation.done:
                if hasattr(operation, "response") and operation.response:
                    videos = operation.response.generated_videos
                    if videos and len(videos) > 0:
                        video_uri = videos[0].video.uri
                        print(f"[media]   Video ready! Downloading...")

                        # Download video
                        full_path = OUTPUT_DIR / output_path
                        full_path.parent.mkdir(parents=True, exist_ok=True)
                        urllib.request.urlretrieve(video_uri, str(full_path))

                        size_mb = full_path.stat().st_size / (1024 * 1024)
                        print(f"[media]   Saved: {full_path} ({size_mb:.1f} MB)")
                        return str(full_path)

                print(f"[media]   Warning: Operation done but no video data")
                return None

            print(f"[media]   Still generating... ({elapsed}s elapsed)")

        print(f"[media]   Error: Video generation timed out after {VIDEO_TIMEOUT}s")
        return None

    except Exception as e:
        print(f"[media]   Error generating {output_path}: {e}")
        return None


def main():
    # Read media brief
    brief_path = Path("media-brief.json")
    if not brief_path.exists():
        print("[media] Error: media-brief.json not found in current directory")
        sys.exit(1)

    with open(brief_path) as f:
        brief = json.load(f)

    print(f"[media] Campaign: {brief.get('campaign', 'Unknown')}")
    print(f"[media] Style: {brief.get('style', 'Default')}")

    images = brief.get("images", [])
    videos = brief.get("videos", [])
    print(f"[media] Assets to generate: {len(images)} images, {len(videos)} videos")
    print()

    client = get_client()
    results = {"images": [], "videos": [], "errors": []}

    # Generate images
    for img in images:
        style_prefix = f"Style: {brief.get('style', '')}. " if brief.get("style") else ""
        full_prompt = f"{style_prefix}{img['prompt']}"

        path = generate_image(
            client,
            prompt=full_prompt,
            aspect_ratio=img.get("aspect_ratio", "16:9"),
            output_path=img["output"],
        )
        if path:
            results["images"].append({"id": img["id"], "path": path})
        else:
            results["errors"].append({"id": img["id"], "type": "image"})
        print()

    # Generate videos
    for vid in videos:
        style_prefix = f"Style: {brief.get('style', '')}. " if brief.get("style") else ""
        full_prompt = f"{style_prefix}{vid['prompt']}"

        path = generate_video(
            client,
            prompt=full_prompt,
            duration=vid.get("duration", 8),
            output_path=vid["output"],
        )
        if path:
            results["videos"].append({"id": vid["id"], "path": path})
        else:
            results["errors"].append({"id": vid["id"], "type": "video"})
        print()

    # Summary
    total = len(results["images"]) + len(results["videos"])
    errors = len(results["errors"])
    print(f"[media] Complete: {total} assets generated, {errors} errors")

    if results["errors"]:
        print(f"[media] Failed assets: {[e['id'] for e in results['errors']]}")

    # Write results manifest
    manifest_path = OUTPUT_DIR / "media-manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"[media] Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
