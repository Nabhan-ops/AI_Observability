
import json
import os

import psycopg
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv(".env", override=True)

WORKFLOW_PATH = "output/workflow.json"
EMBEDDING_MODEL = "text-embedding-3-small"
WORKFLOW_STEP_ID = "__workflow__"


def create_workflow_text(workflow):
    """Create searchable text representing the complete use case."""
    steps = workflow.get("steps", [])

    parts = [
        f"Record type: complete workflow",
        f"Workflow: {workflow['workflow_name']}",
        f"Application: {workflow.get('application', 'Unknown')}",
        f"Workflow summary: {workflow.get('workflow_summary', '')}",
        f"Video duration: {workflow.get('video_duration_seconds', 'Unknown')} seconds",
        "Workflow steps:",
    ]

    for index, step in enumerate(steps, start=1):
        parts.append(
            f"{index}. {step.get('action', 'Unknown action')}: "
            f"{step.get('description', '')}"
        )

    parts.extend([
        f"Coverage: {json.dumps(workflow.get('coverage', {}), ensure_ascii=False)}",
        "This record describes the entire use case, not one individual action.",
    ])

    return "\n".join(parts)


def create_step_text(workflow, step):
    """Create searchable text representing one workflow step."""
    parts = [
        "Record type: individual workflow step",
        f"Workflow: {workflow['workflow_name']}",
        f"Application: {workflow.get('application', 'Unknown')}",
        f"Workflow summary: {workflow.get('workflow_summary', '')}",
        f"Step ID: {step['step_id']}",
        f"Action: {step['action']}",
        f"Description: {step.get('description', '')}",
        f"Timestamp: {step.get('timestamp_seconds', 'Unknown')} seconds",
        f"Action basis: {step.get('action_basis', 'Unknown')}",
        f"Observed facts: {'; '.join(step.get('observed_facts', []))}",
        f"Spoken instructions: {'; '.join(step.get('spoken_instructions', []))}",
        f"Inferences: {'; '.join(step.get('inferences', []))}",
        f"Uncertainties: {'; '.join(step.get('uncertainties', []))}",
        f"Review status: {step.get('review_status', 'unknown')}",
        f"Execution ready: {step.get('execution_ready', False)}",
    ]

    return "\n".join(parts)


def create_embedding(client, content):
    """Generate an embedding for a text record."""
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=content,
    )
    return response.data[0].embedding


def upsert_record(
    cursor,
    client,
    workflow,
    step_id,
    content,
    metadata,
):
    """Create an embedding and insert or update one database record."""
    embedding = create_embedding(client, content)

    cursor.execute(
        """
        INSERT INTO workflow_chunks
            (workflow_name, step_id, content, metadata, embedding)
        VALUES (%s, %s, %s, %s, %s::vector)
        ON CONFLICT (workflow_name, step_id)
        DO UPDATE SET
            content = EXCLUDED.content,
            metadata = EXCLUDED.metadata,
            embedding = EXCLUDED.embedding,
            created_at = NOW()
        """,
        (
            workflow["workflow_name"],
            step_id,
            content,
            json.dumps(metadata, ensure_ascii=False),
            str(embedding),
        ),
    )


def main():
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is missing from .env")

    with open(WORKFLOW_PATH, encoding="utf-8") as file:
        workflow = json.load(file)

    workflow_name = workflow.get("workflow_name")
    if not workflow_name:
        raise ValueError("The workflow has no workflow_name.")

    steps = workflow.get("steps", [])
    if not steps:
        raise ValueError("The workflow contains no steps.")

    # Reserve this ID for the complete workflow record.
    if any(step.get("step_id") == WORKFLOW_STEP_ID for step in steps):
        raise ValueError(
            f"{WORKFLOW_STEP_ID} is reserved for the complete workflow."
        )

    client = OpenAI()

    connection_settings = {
        "host": os.getenv("PGHOST", "127.0.0.1"),
        "port": int(os.getenv("PGPORT", "5432")),
        "dbname": os.getenv("PGDATABASE", "ai_observability"),
        "user": os.getenv("PGUSER"),
        "password": os.getenv("PGPASSWORD"),
    }

    coverage = workflow.get("coverage", {})

    # Both the workflow record and step records use the same table.
    with psycopg.connect(**connection_settings) as connection:
        with connection.cursor() as cursor:

            # 1. Index the complete use case.
            workflow_content = create_workflow_text(workflow)

            workflow_metadata = {
                "record_type": "workflow",
                "source": WORKFLOW_PATH,
                "application": workflow.get("application"),
                "coverage": coverage,
                "step_count": len(steps),
                "step_ids": [step.get("step_id") for step in steps],
                "review_status": "needs_human_review",
                "execution_ready": False,
            }

            upsert_record(
                cursor=cursor,
                client=client,
                workflow=workflow,
                step_id=WORKFLOW_STEP_ID,
                content=workflow_content,
                metadata=workflow_metadata,
            )

            print(f"Stored complete workflow: {workflow_name}")

            # 2. Index each individual step.
            for step in steps:
                step_id = step.get("step_id")
                action = step.get("action")

                if not step_id or not action:
                    raise ValueError(
                        "Every step must have a step_id and an action."
                    )

                content = create_step_text(workflow, step)

                metadata = {
                    "record_type": "step",
                    "source": WORKFLOW_PATH,
                    "application": workflow.get("application"),
                    "timestamp_seconds": step.get("timestamp_seconds"),
                    "action_basis": step.get("action_basis"),
                    "observed_facts": step.get("observed_facts", []),
                    "spoken_instructions": step.get("spoken_instructions", []),
                    "inferences": step.get("inferences", []),
                    "uncertainties": step.get("uncertainties", []),
                    "screenshot_evidence_ids": step.get(
                        "screenshot_evidence_ids", []
                    ),
                    "transcript_evidence_ids": step.get(
                        "transcript_evidence_ids", []
                    ),
                    "screenshot_evidence": step.get(
                        "screenshot_evidence", []
                    ),
                    "review_status": step.get(
                        "review_status", "unknown"
                    ),
                    "execution_ready": step.get("execution_ready", False),
                    "coverage": coverage,
                }

                upsert_record(
                    cursor=cursor,
                    client=client,
                    workflow=workflow,
                    step_id=step_id,
                    content=content,
                    metadata=metadata,
                )

                print(f"Stored step {step_id}: {action}")

    print(f"\nSuccessfully indexed {len(steps)} steps.")
    print("Complete workflow record: 1")
    print(f"Total records for this workflow: {len(steps) + 1}")
    print(f"Workflow: {workflow_name}")
    print(f"Analysis coverage: {coverage.get('warning', 'Not specified')}")


if __name__ == "__main__":
    main()
