# AI Observability

**Turn screen recordings and spoken instructions into structured workflows, then generate reviewable browser automation code.**

## 1. What We Have Now

AI Observability is a Python project that reconstructs computer workflows from screen recordings by combining visual evidence and spoken instructions.

### Current pipeline

```text

                         demo.webm
                             |
                +------------+------------+
                |                         |
                v                         v
         Video processing          Audio extraction
                |                         |
                v                         v
             OpenCV                    FFmpeg
       (Extract video frames)     (Extract audio track)
                |                         |
                v                         v
              Frames                  audio.mp3
                |                         |
                |                         v
                |                  Whisper API
                |                (Speech-to-text)
                |                         |
                |                         v
                |                 Transcription
                |                 (with timestamps)
                |                         |
                +------------+------------+
                             |
                             v
                  GPT-4.1 vision analysis
                 (Frames + transcription)
                             |
                             v
                       workflow.json
                             |
                             v
                    Evidence enrichment

```

### Implemented features

- **Video processing:** Loads `demo.webm` from the project root and reads its duration.
- **Screenshot extraction:** Uses OpenCV to capture frames at three-second intervals, with a maximum of 20 screenshots.
- **Audio extraction:** Uses FFmpeg to extract mono audio at 16 kHz into an MP3 file.
- **Speech transcription:** Uses OpenAI Whisper (`whisper-1`) to produce text and timestamped transcript segments.
- **Visual workflow reconstruction:** Uses GPT-4.1 to analyze screenshots alongside the transcript.
- **Structured output:** Produces JSON describing workflow steps, timestamps, observed facts, spoken instructions, inferences, uncertainties, and evidence references.
- **Evidence enrichment:** Checks screenshot and transcript references against records that actually exist.
- **Human-review safeguards:** Marks every reconstructed step as `execution_ready: false` and `needs_human_review`.

### Main files

| File | Purpose |
|---|---|
| `video_to_workflow.py` | Runs the video-to-workflow pipeline |
| `demo.webm` | Example input recording |
| `workflow_to_playwright.py` | Converts reconstructed workflow JSON into Playwright code |
| `requirements.txt` | Python dependencies |
| `.env.example` | Example environment configuration |
| `.env` | Local API credentials; never commit |
| `README.md` | Project documentation |

Generated artifacts are stored in the ignored `output/` directory:

```text
output/
├── frames/                  # Sampled screenshots
├── audio.mp3                # Extracted audio
├── workflow.json            # Reconstructed workflow
└── generated_playwright.py  # Generated browser automation
```

These files are created locally and are excluded from Git by default.

### Installation

Requirements:

- Python 3.10 or newer.
- FFmpeg installed and available on `PATH`.
- An OpenAI API key with access to the models used by the project.

On Ubuntu or WSL, install FFmpeg:

```bash
sudo apt update
sudo apt install ffmpeg
```

Create and activate a virtual environment if you do not already have one:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the Python packages:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Configure your API key in a local `.env` file:

```dotenv
OPENAI_API_KEY=your_openai_api_key_here
```

Never commit your actual API key or share it publicly.

### Run workflow reconstruction

Place the input recording at `demo.webm`, then run:

```bash
python video_to_workflow.py
```

The resulting workflow is saved to:

```text
output/workflow.json
```

### Current limitations

- Screenshots are sampled rather than continuously analyzed.
- A maximum of 20 screenshots are extracted, at timestamps starting at zero and spaced three seconds apart.
- Actions between sampled frames may be missed.
- AI-generated descriptions and interpretations can be incorrect.
- Evidence-reference validation confirms that records exist, not that they prove the associated claims.
- Every step remains unapproved for execution until a human-review process is implemented.
- OpenAI API usage may incur costs.

## 2. Browser Automation

The second stage converts a reconstructed workflow into a Python script using Playwright.

### Browser automation pipeline

```text

                       workflow.json
                            |
                            v
                workflow_to_playwright.py
                            |
                            v
                   OpenAI GPT-4.1 API
                            |
                            v
            Generate Playwright script on the fly
                            |
                            v
                  Browser automation

```

### How it works

`workflow_to_playwright.py` reads `output/workflow.json`, sends the workflow to GPT-4.1, validates the returned source, and saves the generated Python script.

The generator checks that the output includes Playwright, has a `__main__` guard, and passes Python syntax parsing. These checks do not prove that the script is correct or safe.

The generated script is saved for review. The generator does not automatically execute it.

### Generate browser automation

First, run the workflow reconstruction pipeline if `output/workflow.json` does not exist:

```bash
python video_to_workflow.py
```

Then generate the Playwright script:

```bash
python workflow_to_playwright.py
```

The generated file is:

```text
output/generated_playwright.py
```

### Install the Playwright browser

Install the Python package through `requirements.txt` as described above. Then install Chromium:

```bash
python -m playwright install chromium
```

On Linux or WSL, missing browser system libraries may require additional installation.

### Run the generated script

Inspect the code before executing it:

```bash
sed -n '1,240p' output/generated_playwright.py
```

If you have reviewed the code and are comfortable with its actions, run:

```bash
python output/generated_playwright.py
```

The current example workflow opens Chromium, navigates to Wikimedia Commons, and pauses at manual checkpoints for login and upload preparation. It does not automatically upload a file.

### Safety and human review

The browser automation stage is experimental.

- Unverified, inferred, and spoken-only actions should remain TODOs.
- Missing URLs, selectors, and form values must not be invented.
- Login and sensitive interactions require appropriate human involvement.
- Generated code must be reviewed before execution.
- Syntax validation is not a security audit.
- The workflow currently marks every step `execution_ready: false`. The generator must not treat those steps as approved actions.
- Browser automation may behave differently from the original recording, so successful execution must be verified independently.

### Future development

Planned improvements include:

- A human-review stage for approving individual workflow steps.
- A structured action schema instead of relying entirely on free-form code generation.
- Better selector discovery and validation.
- Automated tests for generated workflows.
- More reliable execution checks and failure handling.
- Improved evidence coverage and uncertainty reporting.

These are future goals, not features currently guaranteed by the implementation.

### Project principle

**Reconstruct first. Review the evidence. Approve actions explicitly. Automate only what has been verified.**
