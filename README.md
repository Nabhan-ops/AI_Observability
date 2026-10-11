# AI Observability

**Turn screen recordings and spoken instructions into structured, evidence-backed computer workflows.**

## 1. Project Overview

AI Observability explores how AI can understand computer workflows by analyzing what a person does on screen and what they say while doing it.

A screen recording contains two valuable sources of information:

- **Visual evidence:** screenshots showing the application, its interface, and visible changes.
- **Voice evidence:** spoken instructions explaining the user's intentions and actions.

By combining these sources, we can reconstruct a workflow as structured JSON instead of relying on an unstructured video.

For example, a recording might show someone opening an application, navigating to a page, and filling in a form while explaining what they are doing. AI Observability analyzes the sampled screenshots and speech to produce a workflow containing individual steps, timestamps, evidence references, and uncertainties.

The goal is to build a foundation for workflows that can eventually be inspected, verified, and potentially used by automation systems.

**An important principle:** AI-generated workflows are not automatically trusted or executed. Every reconstructed step requires human review.

## 2. How It Works

The current implementation follows this pipeline:

```text
                          demo.webm
                       Input: Video
                            |
                +-----------+-----------+
                |                       |
         Video processing        Audio extraction
                |                       |
             OpenCV                  FFmpeg
       (Capture video frames)   (Extract audio track)
                |                       |
              Frames                 audio.mp3
                |                       |
                |                   Whisper API
                |                (Speech-to-text)
                |                       |
                |               Timestamped transcript
                |                       |
                + - - - - - - - - - - - +
                            |
                    GPT-4.1 Vision API
              (Analyze frames and transcript)
                            |
                      workflow.json
                            |
                       Human review
                 (Manually verify the JSON)
```

The main script is `video_to_workflow.py`. It coordinates the extraction, transcription, reconstruction, and JSON-generation stages.

## 3. Repository Structure

The project directory is organized as follows:

```text
AI_Observability/
├── video_to_workflow.py    # Main workflow extraction pipeline
├── demo.webm               # Input screen recording (local file)
├── .env                    # API credentials (never commit)
├── .env.example            # Example configuration (recommended)
├── .gitignore              # Excludes secrets and generated files
├── requirements.txt        # Python dependencies (recommended)
├── README.md               # Project documentation
├── LICENSE                 # Project license
├── AI_Observability/       # Local virtual environment, if named this way
└── output/                 # Generated artifacts
    ├── frames/             # Extracted screenshots
    │   ├── frame_000.jpg
    │   ├── frame_001.jpg
    │   └── ...
    ├── audio.mp3           # Extracted audio
    └── workflow.json       # Reconstructed workflow
```

Some files in this tree are created locally and are intentionally excluded from Git. In particular, the input recording, generated output, virtual environment, and `.env` file should not be committed.

The `.env.example` and `requirements.txt` files are recommended additions if they do not exist yet.

### Main components

| Component | Purpose |
|---|---|
| `video_to_workflow.py` | Runs the complete extraction pipeline |
| `demo.webm` | Source recording to analyze |
| `output/frames/` | Stores sampled screenshots |
| `output/audio.mp3` | Stores the extracted audio |
| `output/workflow.json` | Stores the reconstructed workflow |
| `.env` | Provides the OpenAI API key locally |
| `.gitignore` | Helps keep credentials and generated artifacts out of Git |

## 4. Workflow Extraction Pipeline

### Step 1 — Video input

The script loads `demo.webm` from the project directory.

OpenCV reads the video's frame rate and total frame count, then calculates its duration. The script raises an error if it cannot open the video or read valid video information.

### Step 2 — Screenshot extraction with OpenCV

The script samples screenshots at three-second intervals.

The current configuration is:

```python
INTERVAL = 3
MAX_FRAMES = 20
```

Screenshots are saved as JPEG files in `output/frames/` and assigned identifiers such as `frame_000` and `frame_001`.

Each screenshot record includes its identifier, timestamp, and relative file path.

The maximum of 20 screenshots means the visual analysis can sample timestamps from 0 to 57 seconds. Longer recordings are not visually sampled beyond that point by the current implementation.

Sampling reduces the amount of visual information sent to the model, but it can miss actions and intermediate interface states between screenshots.

### Step 3 — Audio extraction with FFmpeg

FFmpeg extracts the audio track from the video and saves it as `output/audio.mp3`.

The command converts the audio to mono at 16 kHz, producing the audio file used for transcription.

The video and audio are processed separately so that visual information and spoken instructions can be analyzed together later.

### Step 4 — Speech transcription with Whisper

The script sends the extracted audio to OpenAI's `whisper-1` transcription model.

It requests timestamped segments using `verbose_json`. Each returned segment is assigned an identifier and stores:

- `transcript_id` — a unique segment identifier.
- `start` — segment start time.
- `end` — segment end time.
- `text` — recognized speech.

The complete transcript is also retained.

This provides the model with both the full spoken explanation and individual segments that can be referenced as evidence for specific workflow steps.

### Step 5 — Workflow reconstruction with GPT-4.1

The script sends GPT-4.1 a prompt containing:

- The video duration.
- The sampled screenshot metadata.
- The timestamped transcript segments.
- The complete transcript.
- The actual screenshot images.

The screenshots are encoded as Base64 data URLs and sent as image inputs.

GPT-4.1 reconstructs the recording into meaningful actions. It is instructed to distinguish visible facts from spoken instructions and inferences, avoid inventing evidence IDs, identify uncertainties, and avoid claiming that an action succeeded without evidence.

The model is asked to return a JSON object rather than free-form prose.

### Step 6 — Evidence validation and enrichment

After receiving the JSON, the script performs additional processing in Python.

It:

1. Assigns consistent step identifiers such as `step_001`.
2. Sets `execution_ready` to `false` for every step.
3. Sets the review status to `needs_human_review`.
4. Matches screenshot evidence IDs against screenshots that were actually extracted.
5. Matches transcript evidence IDs against transcript segments that actually exist.
6. Adds the corresponding screenshot and transcript records to the workflow.
7. Adds schema-version and coverage metadata.

References that do not match real extracted records are omitted from the enriched evidence arrays.

This validates whether an evidence reference exists. It does not guarantee that the referenced evidence correctly supports the model's interpretation.

### Step 7 — JSON output

The completed workflow is written to:

```text
output/workflow.json
```

The JSON is formatted with indentation and UTF-8 encoding, making it easier to read, inspect, process, and use in future development.

## 5. Example Workflow JSON

The following is an illustrative example of the output structure. It demonstrates the fields produced by the pipeline; it is not a verbatim result from `demo.webm`.

```json
{
  "schema_version": "2.0",
  "workflow_name": "Open a customer record",
  "application": "Example CRM",
  "workflow_summary": "Navigate to a customer record.",
  "video_duration_seconds": 12.0,
  "coverage": {
    "analysis_scope": "sampled_frames_only",
    "sampled_frame_count": 5,
    "first_sampled_timestamp": 0,
    "last_sampled_timestamp": 12,
    "video_duration_seconds": 12.0,
    "warning": "Only sampled screenshots were analyzed."
  },
  "steps": [
    {
      "step_id": "step_001",
      "action": "Open the customer list",
      "description": "Navigate to the customer list in the application.",
      "timestamp_seconds": 3,
      "action_basis": "observed",
      "observed_facts": [
        "The customer list is visible."
      ],
      "spoken_instructions": [
        "Open the customer list."
      ],
      "inferences": [],
      "screenshot_evidence_ids": [
        "frame_001"
      ],
      "transcript_evidence_ids": [
        "transcript_000"
      ],
      "uncertainties": [],
      "execution_ready": false,
      "review_status": "needs_human_review",
      "screenshot_evidence": [
        {
          "frame_id": "frame_001",
          "timestamp_seconds": 3,
          "path": "frames/frame_001.jpg"
        }
      ],
      "transcript_evidence": [
        {
          "transcript_id": "transcript_000",
          "start": 1.2,
          "end": 3.4,
          "text": "Open the customer list."
        }
      ]
    }
  ],
  "overall_uncertainties": [],
  "review_status": "needs_human_review"
}
```

### Understanding the JSON fields

| Field | Meaning |
|---|---|
| `schema_version` | Version of the workflow data structure |
| `workflow_name` | Short name for the workflow |
| `application` | Application being used |
| `workflow_summary` | Overview of the workflow |
| `video_duration_seconds` | Duration of the original recording |
| `coverage` | Information about the visual sampling coverage |
| `steps` | Individual reconstructed workflow actions |
| `action_basis` | Whether a step is observed, spoken-only, or inferred |
| `observed_facts` | Facts visible in the sampled screenshots |
| `spoken_instructions` | Relevant instructions from the transcript |
| `inferences` | Interpretations that are not directly established by evidence |
| `screenshot_evidence_ids` | Screenshot identifiers associated with a step |
| `transcript_evidence_ids` | Transcript segment identifiers associated with a step |
| `screenshot_evidence` | Matched screenshot metadata |
| `transcript_evidence` | Matched transcript segment records |
| `uncertainties` | Questions or ambiguities about a step |
| `execution_ready` | Whether a step is approved for execution; currently always `false` |
| `review_status` | Current review state |

The exact workflow names, actions, timestamps, and evidence contents depend on the recording and the model's reconstruction. The post-processing code guarantees several metadata fields, but the model may not always return every requested descriptive field.

## 6. Setup and Installation

### Prerequisites

- Python 3.10 or newer.
- FFmpeg installed and available on your system's `PATH`.
- An OpenAI API key with access to the required models.
- A screen recording named `demo.webm` in the project directory.

### Install FFmpeg on Ubuntu or WSL

```bash
sudo apt update
sudo apt install ffmpeg
```

Check that FFmpeg is available:

```bash
ffmpeg -version
```

### Create a Python virtual environment

From the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

If you already use a virtual environment, activate it instead of creating another one.

### Install Python dependencies

```bash
python -m pip install --upgrade pip
python -m pip install openai opencv-python python-dotenv
```

### Configure the API key

Create a `.env` file in the project root:

```dotenv
OPENAI_API_KEY=your_openai_api_key_here
```

Replace the placeholder locally with your own key. Never commit `.env` or paste a real API key into public source code.

## 7. Running the Project

Place your recording at:

```text
AI_Observability/demo.webm
```

Activate your virtual environment and run:

```bash
python video_to_workflow.py
```

The script will:

1. Extract screenshots.
2. Extract the audio track.
3. Transcribe speech.
4. Reconstruct the workflow using GPT-4.1.
5. Enrich and validate evidence references.
6. Save `output/workflow.json`.

A successful run prints the video duration, the number of screenshots extracted, and the location of the resulting JSON file.

The process uses API calls, so execution may incur costs depending on the recording and the models used.

## 8. Current Limitations

The current implementation is a workflow reconstruction prototype, not a complete autonomous automation platform.

- **Sampled visual evidence:** screenshots are sampled every three seconds, so intermediate actions can be missed.
- **Limited visual coverage:** at most 20 screenshots are extracted, covering timestamps from 0 to 57 seconds.
- **Full audio transcription:** the audio is transcribed separately, so spoken content may cover more of the recording than the visual analysis.
- **AI interpretation:** a model can misunderstand a screen, instruction, or action.
- **Evidence validation:** the code checks that referenced IDs exist, but does not prove that they support the interpretation.
- **Human review required:** every step is marked `needs_human_review`.
- **No execution:** the current script does not execute the reconstructed steps in a browser or desktop application.
- **API dependency:** transcription and workflow reconstruction require successful OpenAI API calls.

## 9. Future Development

Possible next steps include:

- Improve visual coverage with adaptive screenshot sampling.
- Develop a stronger workflow schema and validation rules.
- Add more detailed evidence verification and confidence indicators.
- Build a human-review interface for inspecting and correcting reconstructed steps.
- Add workflow storage, search, and retrieval.
- Explore controlled browser or API automation only after workflows have been reviewed and validated.
- Add automated tests and reproducible evaluation datasets.

These are development goals, not claims about functionality already implemented in this script.

## 10. Project Philosophy

AI Observability is built around a simple idea:

**A reconstructed workflow should explain what the AI believes happened, show which evidence supports that interpretation, identify what remains uncertain, and stay unapproved until a human reviews it.**

The long-term direction is to move from raw recordings toward structured, inspectable, and trustworthy workflow data.
