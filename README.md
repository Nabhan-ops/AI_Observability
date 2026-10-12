# AI Observability

**Turn recorded GUI tasks into structured workflows, retrieve similar workflows using vector search, and generate reviewable Playwright automation.**

AI Observability is an experimental Python project that combines video analysis, speech transcription, LLM-based workflow reconstruction, PostgreSQL with pgvector, retrieval-augmented generation (RAG), and browser automation.

## 1. Architecture

```text
Screen recording (demo.webm)
        |
        v
Video frames + extracted audio
        |                   |
        v                   v
OpenCV                FFmpeg + Whisper API
        |                   |
        +---------+---------+
                  |
                  v
       GPT-4.1 workflow analysis
                  |
                  v
       output/workflow.json
                  |
                  v
      Ingest workflow into PostgreSQL
                  |
                  v
       OpenAI text-embedding-3-small
                  |
                  v
     PostgreSQL + pgvector database
       /                         \
      v                           v
Workflow-level records      Individual step records
      \                           /
       +------------+-------------+
                    |
                    v
       Retrieve a similar workflow
                    |
                    v
       Adapt workflow with GPT-4.1
                    |
                    v
       Generate Playwright Python code
                    |
                    v
         Human review and testing
```

## 2. Features

- **Video processing:** Reads `demo.webm` and extracts sampled screenshots.
- **Audio processing:** Uses FFmpeg to extract audio and the OpenAI transcription API to produce text and timestamps.
- **Workflow reconstruction:** Uses GPT-4.1 to combine screenshot evidence and spoken instructions into structured JSON.
- **Evidence enrichment:** Records screenshot and transcript references, uncertainties, and review status.
- **Dual-level indexing:** Stores one complete workflow record and separate records for its individual steps.
- **Semantic retrieval:** Embeds a new task and retrieves a similar workflow from PostgreSQL using pgvector cosine distance.
- **Workflow adaptation:** Uses the retrieved workflow as context for generating a Playwright script.
- **Syntax and safety checks:** Checks generated code before saving it. These checks do not guarantee that code is safe or correct.
- **Human checkpoints:** Keeps sensitive or insufficiently supported actions under human control.

## 3. Main files

| File | Purpose |
|---|---|
| `video_to_workflow.py` | Reconstructs a workflow from a recording |
| `ingest_workflow_into_vectordb.py` | Embeds and indexes a workflow and its steps |
| `retrieve_similar_workflow.py` | Finds a similar workflow using semantic retrieval |
| `new_workflow_to_playwright.py` | Retrieves a workflow and generates adapted Playwright code |
| `rag_workflow_assistant.py` | Additional RAG assistant entry point |
| `requirements.txt` | Python dependencies |
| `.env.example` | Example configuration template |
| `.env` | Local credentials and database configuration; never commit |
| `demo.webm` | Example input recording |
| `README.md` | Project documentation |

Generated artifacts are stored locally in `output/`, which is excluded from Git:

```text
output/
├── frames/
├── audio.mp3
├── workflow.json
├── generated_playwright.py
└── new_generated_playwright.py
```

The actual output files depend on which scripts have been run.

## 4. System requirements

- Ubuntu or WSL with Ubuntu
- Python 3.10 or newer
- FFmpeg
- PostgreSQL
- The PostgreSQL pgvector extension
- Chromium for Playwright
- An OpenAI API key with access to the models used by the project

### Install system packages

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip ffmpeg postgresql
```

On Ubuntu versions where the matching package is available, install pgvector with:

```bash
sudo apt install postgresql-16-pgvector
```

The PostgreSQL major version and the pgvector package must be compatible. Package availability may vary by Ubuntu release.

Check the installations:

```bash
python3 --version
ffmpeg -version
psql --version
```

## 5. Python environment

From the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Install the Playwright Chromium browser:

```bash
python -m playwright install chromium
```

If Playwright reports missing Linux libraries, use:

```bash
python -m playwright install-deps chromium
```

These commands install the browser runtime separately from the Python package.

## 6. Configure environment variables

Create a local `.env` file:

```bash
cp .env.example .env
```

Edit it and provide your own credentials and configuration:

```dotenv
OPENAI_API_KEY=your_openai_api_key_here

PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=ai_observability
PGUSER=ai_observability_app
PGPASSWORD=your_database_password_here
```

Use the actual database password configured during setup. Do not commit `.env`, publish API keys, or include secrets in source code.

## 7. PostgreSQL and pgvector setup

This project uses PostgreSQL as its database and pgvector to store and compare vector embeddings.

The setup below documents the database configuration used during development.

### 7.1 Start PostgreSQL

```bash
sudo service postgresql start
sudo -u postgres psql
```

### 7.2 Create the application user and database

Inside the PostgreSQL prompt, create the application role and database. Replace the example password before running the SQL:

```sql
CREATE USER ai_observability_app
WITH LOGIN PASSWORD 'CHANGE_THIS_PASSWORD';

CREATE DATABASE ai_observability
OWNER ai_observability_app;
```

If the role or database already exists, do not run the corresponding `CREATE` command again. Reuse the existing setup or modify it deliberately.

Exit the PostgreSQL prompt:

```sql
\q
```

### 7.3 Enable pgvector and create the table

Connect as the PostgreSQL administrator:

```bash
sudo -u postgres psql -d ai_observability
```

Run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS workflow_chunks (
    id BIGSERIAL PRIMARY KEY,
    content TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding VECTOR(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    workflow_name TEXT NOT NULL DEFAULT '',
    step_id TEXT NOT NULL DEFAULT '',
    CONSTRAINT workflow_chunks_workflow_step_unique
        UNIQUE (workflow_name, step_id)
);

GRANT CONNECT ON DATABASE ai_observability
TO ai_observability_app;

GRANT USAGE ON SCHEMA public
TO ai_observability_app;

GRANT SELECT, INSERT, UPDATE, DELETE
ON TABLE workflow_chunks
TO ai_observability_app;

GRANT USAGE, SELECT
ON SEQUENCE workflow_chunks_id_seq
TO ai_observability_app;
```

Exit with `\q`.

The embedding column uses `VECTOR(1536)` because the project uses the `text-embedding-3-small` model with its default embedding dimensions.

The unique constraint prevents duplicate records for the same workflow and step ID. The ingestion script can update existing records instead of inserting duplicates.

### 7.4 Verify the database

Connect using the application credentials from `.env`:

```bash
psql -h 127.0.0.1 \
  -U ai_observability_app \
  -d ai_observability
```

Then run:

```sql
SELECT extname, extversion
FROM pg_extension
WHERE extname = 'vector';

SELECT workflow_name, step_id
FROM workflow_chunks
ORDER BY workflow_name, step_id;
```

The first query checks whether pgvector is enabled. The second lists indexed workflow records.

If the application role or database already exists, follow the existing database configuration rather than recreating it.

## 8. Run the workflow pipeline

### Step 1: Reconstruct the workflow

Place the recording at `demo.webm` in the repository root and run:

```bash
python video_to_workflow.py
```

The script produces `output/workflow.json` and supporting local evidence files.

The current implementation samples a limited number of screenshots. Actions between sampled frames can be missed, and a recording's full duration does not mean the entire recording was analyzed.

### Step 2: Index the workflow

After PostgreSQL is running and `.env` is configured:

```bash
python ingest_workflow_into_vectordb.py
```

The ingestion pipeline creates embeddings and stores two types of records:

- **Workflow-level record:** A searchable representation of the entire workflow.
- **Step-level records:** Individual workflow steps with their own evidence and metadata.

This avoids relying only on small text chunks when the task requires retrieving an entire use case.

### Step 3: Retrieve a similar workflow

Run:

```bash
python retrieve_similar_workflow.py
```

Enter the task you want to automate and the target application when prompted.

The script searches workflow-level records, ranks matches by vector similarity, and retrieves the matching workflow's ordered steps.

A similarity score is a ranking signal, not a probability that the workflow is correct.

### Step 4: Generate an adapted Playwright script

Run:

```bash
python new_workflow_to_playwright.py
```

The script retrieves relevant workflow context, asks the language model to adapt it to the requested task, checks the generated source, and saves the result to:

```text
output/new_generated_playwright.py
```

Review the generated script before running it. The generator's static checks are not a security audit.

### Step 5: Review and test

Inspect the generated code:

```bash
sed -n '1,260p' output/new_generated_playwright.py
```

Only run it after you understand its actions and have checked the destination, selectors, and any state-changing operations.

The current Wikimedia Commons example opens the site, clicks the login link, pauses for manual login, and pauses before upload preparation. It does not independently complete an upload.

## 9. Safety and current limitations

- **Sampled evidence:** The workflow reconstruction can miss actions between screenshots.
- **AI uncertainty:** Model-generated steps, interpretations, and selectors can be incorrect.
- **Evidence validation:** Checking that an evidence reference exists does not prove that it supports the associated claim.
- **Human review:** Reconstructed steps are marked `execution_ready: false` and require review.
- **Generated code:** Syntax checks do not prove runtime correctness or security.
- **Credentials:** Login credentials should not be embedded in generated code or sent to the language model.
- **State-changing actions:** Uploads, deletions, purchases, and other consequential actions require explicit review and appropriate confirmation.
- **Database setup:** PostgreSQL and pgvector must be installed and configured separately from Python dependencies.
- **Costs:** OpenAI API requests can incur charges.

## 10. Development principles

The project follows these principles:

1. Reconstruct workflows from available evidence.
2. Preserve uncertainty instead of inventing missing actions.
3. Retrieve a relevant workflow before generating a new one.
4. Keep workflow-level and step-level representations.
5. Review generated automation before execution.
6. Verify results independently.

The long-term goal is to make GUI automation more reusable by learning from recorded workflows rather than generating every task from scratch.
