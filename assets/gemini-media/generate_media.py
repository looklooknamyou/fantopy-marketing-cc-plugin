#!/usr/bin/env python3
"""
Marketing media asset generator for Gemini and Qwen image/video models.

Reads media-brief.json from the current directory, generates images and video
clips based on the provider/model selected for each asset, and saves outputs to
the parent directory.

Usage:
    python3 generate_media.py

Requires:
    - GEMINI_API_KEY or GOOGLE_API_KEY for Gemini assets
    - DASHSCOPE_API_KEY for Qwen image assets
    - google-genai package (pip install google-genai) for Gemini assets
"""

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    import base64
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

DEFAULT_IMAGE_PROVIDER = "qwen"
DEFAULT_VIDEO_PROVIDER = "wan"
DEFAULT_GEMINI_IMAGE_MODEL = "imagen-4.0-fast-generate-001"
DEFAULT_GEMINI_VIDEO_MODEL = "veo-2.0-generate-001"
DEFAULT_QWEN_IMAGE_MODEL = "qwen-image-max"
DEFAULT_WAN_VIDEO_MODEL = "wan2.2-t2v-plus"
QWEN_API_URL = "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
WAN_VIDEO_API_URL = "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
WAN_TASKS_API_BASE = "https://dashscope-intl.aliyuncs.com/api/v1/tasks"
QWEN_SIZE_MAP = {
    "16:9": "1664*928",
    "4:3": "1472*1104",
    "1:1": "1328*1328",
    "3:4": "1104*1472",
    "9:16": "928*1664",
}
WAN_SIZE_MAP = {
    "16:9": "1920*1080",
    "9:16": "1080*1920",
    "1:1": "1440*1440",
    "4:3": "1632*1248",
    "3:4": "1248*1632",
}
VIDEO_POLL_INTERVAL = 20  # seconds
VIDEO_TIMEOUT = 600  # 10 minutes
OUTPUT_DIR = Path("..")


def get_gemini_client():
    """Initialize Gemini client with API key."""
    if genai is None:
        raise RuntimeError("google-genai not installed. Run: pip install google-genai")
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY not set")
    return genai.Client(api_key=api_key)


def get_dashscope_api_key():
    api_key = os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("QWEN_API_KEY")
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY not set")
    return api_key


def save_binary_output(output_path, data):
    full_path = OUTPUT_DIR / output_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    with open(full_path, "wb") as f:
        f.write(data)
    return full_path


def download_binary(url, output_path):
    full_path = OUTPUT_DIR / output_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(url, str(full_path))
    return full_path


def generate_gemini_image(client, prompt, aspect_ratio, output_path, model):
    """Generate a single Gemini image from a text prompt."""
    print(f"[media] Generating image: {output_path}")
    print(f"[media]   Prompt: {prompt[:80]}...")
    print(f"[media]   Provider: gemini")
    print(f"[media]   Model: {model}")
    print(f"[media]   Aspect ratio: {aspect_ratio}")

    response = client.models.generate_content(
        model=model,
        contents=[prompt],
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        ),
    )

    for part in response.candidates[0].content.parts:
        if hasattr(part, "inline_data") and part.inline_data:
            image_bytes = base64.b64decode(part.inline_data.data)
            full_path = save_binary_output(output_path, image_bytes)
            size_kb = len(image_bytes) / 1024
            print(f"[media]   Saved: {full_path} ({size_kb:.0f} KB)")
            return str(full_path)

    raise RuntimeError(f"No image data in response for {output_path}")


def generate_qwen_image(prompt, aspect_ratio, output_path, model):
    """Generate a single Qwen image from a text prompt."""
    print(f"[media] Generating image: {output_path}")
    print(f"[media]   Prompt: {prompt[:80]}...")
    print(f"[media]   Provider: qwen")
    print(f"[media]   Model: {model}")
    print(f"[media]   Aspect ratio: {aspect_ratio}")

    api_key = get_dashscope_api_key()
    size = QWEN_SIZE_MAP.get(aspect_ratio, QWEN_SIZE_MAP["1:1"])
    payload = {
        "model": model,
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}],
                }
            ]
        },
        "parameters": {
            "result_format": "message",
            "watermark": False,
            "size": size,
        },
    }
    request = urllib.request.Request(
        QWEN_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        try:
            error_data = json.loads(error_body)
            message = error_data.get("message") or error_data.get("code") or error_body
        except json.JSONDecodeError:
            message = error_body
        raise RuntimeError(message) from exc

    content = (
        ((data.get("output") or {}).get("choices") or [{}])[0]
        .get("message", {})
        .get("content", [])
    )
    image_url = None
    for item in content:
        if isinstance(item, dict) and item.get("image"):
            image_url = item["image"]
            break
    if not image_url:
        raise RuntimeError("No image URL returned by DashScope")

    full_path = download_binary(image_url, output_path)
    size_kb = full_path.stat().st_size / 1024
    print(f"[media]   Saved: {full_path} ({size_kb:.0f} KB)")
    return str(full_path)


def generate_gemini_video(client, prompt, duration, output_path, model):
    """Generate a video clip from a text prompt (async operation)."""
    print(f"[media] Generating video: {output_path}")
    print(f"[media]   Prompt: {prompt[:80]}...")
    print(f"[media]   Provider: gemini")
    print(f"[media]   Model: {model}")
    print(f"[media]   Duration: {duration}s")

    # Start async video generation
    operation = client.models.generate_videos(
        model=model,
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

                    full_path = download_binary(video_uri, output_path)
                    size_mb = full_path.stat().st_size / (1024 * 1024)
                    print(f"[media]   Saved: {full_path} ({size_mb:.1f} MB)")
                    return str(full_path)

            raise RuntimeError("Operation completed but no video data was returned")

        print(f"[media]   Still generating... ({elapsed}s elapsed)")

    raise RuntimeError(f"Video generation timed out after {VIDEO_TIMEOUT}s")


def generate_wan_video(prompt, duration, output_path, model, aspect_ratio="16:9"):
    """Generate a video clip using Alibaba Wan's async DashScope API."""
    print(f"[media] Generating video: {output_path}")
    print(f"[media]   Prompt: {prompt[:80]}...")
    print(f"[media]   Provider: wan")
    print(f"[media]   Model: {model}")
    print(f"[media]   Duration: {duration}s")

    api_key = get_dashscope_api_key()
    size = WAN_SIZE_MAP.get(aspect_ratio, WAN_SIZE_MAP["16:9"])
    payload = {
        "model": model,
        "input": {
            "prompt": prompt,
        },
        "parameters": {
            "size": size,
            "duration": duration,
            "prompt_extend": True,
            "watermark": False,
        },
    }
    create_request = urllib.request.Request(
        WAN_VIDEO_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(create_request, timeout=120) as response:
            create_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        try:
            error_data = json.loads(error_body)
            message = error_data.get("message") or error_data.get("code") or error_body
        except json.JSONDecodeError:
            message = error_body
        raise RuntimeError(message) from exc

    task_id = ((create_data.get("output") or {}).get("task_id") or "").strip()
    if not task_id:
        raise RuntimeError("Wan task creation did not return a task_id")

    print(f"[media]   Operation started: {task_id}")
    start_time = time.time()
    while time.time() - start_time < VIDEO_TIMEOUT:
        time.sleep(VIDEO_POLL_INTERVAL)
        elapsed = int(time.time() - start_time)
        task_request = urllib.request.Request(
            f"{WAN_TASKS_API_BASE}/{urllib.parse.quote(task_id)}",
            headers={"Authorization": f"Bearer {api_key}"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(task_request, timeout=120) as response:
                task_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            try:
                error_data = json.loads(error_body)
                message = error_data.get("message") or error_data.get("code") or error_body
            except json.JSONDecodeError:
                message = error_body
            raise RuntimeError(message) from exc

        output = task_data.get("output") or {}
        status = output.get("task_status")
        if status == "SUCCEEDED":
            video_url = output.get("video_url")
            if not video_url:
                raise RuntimeError("Wan task succeeded but did not return a video_url")
            print("[media]   Video ready! Downloading...")
            full_path = download_binary(video_url, output_path)
            size_mb = full_path.stat().st_size / (1024 * 1024)
            print(f"[media]   Saved: {full_path} ({size_mb:.1f} MB)")
            return str(full_path)
        if status == "FAILED":
            raise RuntimeError(output.get("message") or output.get("code") or "Wan task failed")
        print(f"[media]   Still generating... ({elapsed}s elapsed)")

    raise RuntimeError(f"Wan video generation timed out after {VIDEO_TIMEOUT}s")


def get_asset_provider(asset, media_type):
    provider = asset.get("provider") or (
        DEFAULT_VIDEO_PROVIDER if media_type == "video" else DEFAULT_IMAGE_PROVIDER
    )
    return provider.lower()


def get_asset_model(asset, media_type, provider):
    explicit_model = asset.get("model")
    if explicit_model:
        return explicit_model
    if provider == "qwen":
        return DEFAULT_QWEN_IMAGE_MODEL
    if provider == "wan":
        return DEFAULT_WAN_VIDEO_MODEL
    if media_type == "video":
        return DEFAULT_GEMINI_VIDEO_MODEL
    return DEFAULT_GEMINI_IMAGE_MODEL


def generate_image(clients, prompt, asset):
    provider = get_asset_provider(asset, "image")
    model = get_asset_model(asset, "image", provider)
    if provider == "gemini":
        client = clients.get("gemini")
        if client is None:
            client = get_gemini_client()
            clients["gemini"] = client
        return generate_gemini_image(
            client,
            prompt=prompt,
            aspect_ratio=asset.get("aspect_ratio", "16:9"),
            output_path=asset["output"],
            model=model,
        ), provider, model
    if provider == "qwen":
        return generate_qwen_image(
            prompt=prompt,
            aspect_ratio=asset.get("aspect_ratio", "16:9"),
            output_path=asset["output"],
            model=model,
        ), provider, model
    raise RuntimeError(f"Unsupported image provider: {provider}")


def generate_video(clients, prompt, asset):
    provider = get_asset_provider(asset, "video")
    model = get_asset_model(asset, "video", provider)
    if provider == "gemini":
        client = clients.get("gemini")
        if client is None:
            client = get_gemini_client()
            clients["gemini"] = client
        return generate_gemini_video(
            client,
            prompt=prompt,
            duration=asset.get("duration", 8),
            output_path=asset["output"],
            model=model,
        ), provider, model
    if provider == "wan":
        return generate_wan_video(
            prompt=prompt,
            duration=asset.get("duration", 8),
            output_path=asset["output"],
            model=model,
            aspect_ratio=asset.get("aspect_ratio", "16:9"),
        ), provider, model
    raise RuntimeError(f"Unsupported video provider: {provider}")


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

    results = {"images": [], "videos": [], "errors": []}
    clients = {}

    # Generate images
    for img in images:
        style_prefix = f"Style: {brief.get('style', '')}. " if brief.get("style") else ""
        full_prompt = f"{style_prefix}{img['prompt']}"
        try:
            path, provider, model = generate_image(clients, full_prompt, img)
            results["images"].append(
                {"id": img["id"], "path": path, "provider": provider, "model": model}
            )
        except Exception as e:
            print(f"[media]   Error generating {img['output']}: {e}")
            results["errors"].append(
                {
                    "id": img["id"],
                    "type": "image",
                    "provider": get_asset_provider(img, "image"),
                    "model": get_asset_model(img, "image", get_asset_provider(img, "image")),
                    "message": str(e),
                }
            )
        print()

    # Generate videos
    for vid in videos:
        style_prefix = f"Style: {brief.get('style', '')}. " if brief.get("style") else ""
        full_prompt = f"{style_prefix}{vid['prompt']}"
        try:
            path, provider, model = generate_video(clients, full_prompt, vid)
            results["videos"].append(
                {"id": vid["id"], "path": path, "provider": provider, "model": model}
            )
        except Exception as e:
            print(f"[media]   Error generating {vid['output']}: {e}")
            results["errors"].append(
                {
                    "id": vid["id"],
                    "type": "video",
                    "provider": get_asset_provider(vid, "video"),
                    "model": get_asset_model(vid, "video", get_asset_provider(vid, "video")),
                    "message": str(e),
                }
            )
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
