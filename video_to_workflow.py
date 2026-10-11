
import os
import json
import base64
import subprocess
from pathlib import Path

import cv2
from dotenv import load_dotenv
from openai import OpenAI

# ================= CONFIGURATION =================

BASE = Path(__file__).resolve().parent
VIDEO = BASE / "demo.webm"
OUT = BASE / "output"
FRAMES = OUT / "frames"
AUDIO = OUT / "audio.mp3"
JSON_FILE = OUT / "workflow.json"

INTERVAL = 3
MAX_FRAMES = 20

load_dotenv(BASE / ".env")
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ================= EXTRACT SCREENSHOTS =================

def extract_frames():
    FRAMES.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)

    # Remove screenshots left over from an older run.
    for file in FRAMES.glob("frame_*.jpg"):
        file.unlink()

    video = cv2.VideoCapture(str(VIDEO))

    if not video.isOpened():
        raise RuntimeError(f"Cannot open video: {VIDEO}")

    fps = video.get(cv2.CAP_PROP_FPS)
    total = video.get(cv2.CAP_PROP_FRAME_COUNT)

    if fps <= 0 or total <= 0:
        video.release()
        raise RuntimeError("Cannot read video information.")

    duration = total / fps
    frames = []

    for i in range(MAX_FRAMES):
        timestamp = i * INTERVAL
        if timestamp >= duration:
            break

        video.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
        success, image = video.read()

        if success:
            name = f"frame_{i:03d}.jpg"
            cv2.imwrite(str(FRAMES / name), image)
            frames.append({
                "frame_id": f"frame_{i:03d}",
                "timestamp_seconds": timestamp,
                "path": f"frames/{name}",
            })

    video.release()

    if not frames:
        raise RuntimeError("No screenshots extracted.")

    print(f"Video: {duration:.1f}s; screenshots: {len(frames)}")
    return frames, duration


# ================= EXTRACT AUDIO =================

def extract_audio():
    # FFmpeg removes the video and saves its audio as an MP3.
    subprocess.run([
        "ffmpeg", "-y", "-i", str(VIDEO),
        "-vn", "-ac", "1", "-ar", "16000",
        str(AUDIO)
    ], check=True, capture_output=True)


# ================= TRANSCRIBE SPEECH =================

def transcribe():
    # Whisper converts your speech into text with timestamps.
    with open(AUDIO, "rb") as audio:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    segments = []
    for i, s in enumerate(result.segments or []):
        segments.append({
            "transcript_id": f"transcript_{i:03d}",
            "start": s.start,
            "end": s.end,
            "text": s.text.strip(),
        })

    return segments, result.text


# ================= RECONSTRUCT WORKFLOW =================

def reconstruct(frames, duration, segments, transcript):
    # Only send real screenshot IDs and transcript IDs to the model.
    prompt = f"""
Reconstruct a computer workflow from the screenshots and transcript.

Return JSON with:
- workflow_name
- application
- workflow_summary
- video_duration_seconds
- coverage
- steps
- overall_uncertainties
- review_status

Each step must contain:
- step_id
- action
- description
- timestamp_seconds
- action_basis: observed, spoken_only, or inferred
- observed_facts
- spoken_instructions
- inferences
- screenshot_evidence_ids
- transcript_evidence_ids
- uncertainties
- execution_ready: false
- review_status: needs_human_review

Rules:
- One step per meaningful action, not per screenshot.
- Merge screenshots showing the same state.
- Separate visible facts from spoken instructions.
- Never claim an action succeeded without evidence.
- Never invent IDs, selectors, or actions.
- Use only IDs provided below.
- Every step needs human review and must not be executable yet.
- Screenshots are sampled, not continuous.
- Only the beginning of the video may have been analyzed.

Video duration: {duration:.1f} seconds
Screenshots: {json.dumps(frames)}
Transcript segments: {json.dumps(segments)}
Full transcript: {transcript}
"""

    content = [{"type": "text", "text": prompt}]

    # Base64 lets the vision model inspect each screenshot.
    for frame in frames:
        image_path = FRAMES / Path(frame["path"]).name
        encoded = base64.b64encode(image_path.read_bytes()).decode("utf-8")

        content.append({
            "type": "text",
            "text": f"Screenshot {frame['frame_id']} at {frame['timestamp_seconds']}s",
        })
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{encoded}",
                "detail": "low",
            },
        })

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"},
        temperature=0,
    )

    workflow = json.loads(response.choices[0].message.content)

    # Add reliable coverage information from the actual extraction.
    workflow["schema_version"] = "2.0"
    workflow["video_duration_seconds"] = round(duration, 2)
    workflow["coverage"] = {
        "analysis_scope": "sampled_frames_only",
        "sampled_frame_count": len(frames),
        "first_sampled_timestamp": frames[0]["timestamp_seconds"],
        "last_sampled_timestamp": frames[-1]["timestamp_seconds"],
        "video_duration_seconds": round(duration, 2),
        "warning": "Only sampled screenshots were analyzed."
    }
    workflow["review_status"] = "needs_human_review"

    # Replace invented evidence IDs with only IDs that actually exist.
    frame_ids = {f["frame_id"]: f for f in frames}
    transcript_ids = {s["transcript_id"]: s for s in segments}

    for i, step in enumerate(workflow.get("steps", [])):
        step["step_id"] = f"step_{i + 1:03d}"
        step["execution_ready"] = False
        step["review_status"] = "needs_human_review"

        ids = step.get("screenshot_evidence_ids", [])
        step["screenshot_evidence"] = [
            frame_ids[x] for x in ids
            if isinstance(x, str) and x in frame_ids
        ]

        ids = step.get("transcript_evidence_ids", [])
        step["transcript_evidence"] = [
            transcript_ids[x] for x in ids
            if isinstance(x, str) and x in transcript_ids
        ]

    return workflow


# ================= RUN EVERYTHING =================

def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing from your .env file.")

    if not VIDEO.exists():
        raise FileNotFoundError(f"Video not found: {VIDEO}")

    frames, duration = extract_frames()
    extract_audio()
    segments, transcript = transcribe()
    workflow = reconstruct(frames, duration, segments, transcript)

    JSON_FILE.write_text(
        json.dumps(workflow, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\nDone! Workflow saved to:\n{JSON_FILE}")


if __name__ == "__main__":
    main()
