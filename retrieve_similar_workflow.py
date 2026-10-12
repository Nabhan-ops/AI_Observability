
import json
import os

import psycopg
from dotenv import load_dotenv
from openai import OpenAI


EMBEDDING_MODEL = "text-embedding-3-small"
WORKFLOW_RECORD_ID = "__workflow__"


def create_embedding(client, text):
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def main():
    load_dotenv(".env", override=True)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is missing from .env")

    client = OpenAI(api_key=api_key)

    task = input("What automation do you need? ").strip()
    if not task:
        print("Please enter an automation request.")
        return

    application = input(
        "Which application? (e.g. Wikimedia Commons): "
    ).strip()

    if not application:
        print("Please enter an application name.")
        return

    query_text = (
        f"Application: {application}\n"
        f"Requested automation: {task}"
    )

    query_embedding = create_embedding(client, query_text)
    embedding_text = "[" + ",".join(
        str(value) for value in query_embedding
    ) + "]"

    db_config = {
        "host": os.getenv("PGHOST", "127.0.0.1"),
        "port": os.getenv("PGPORT", "5432"),
        "dbname": os.getenv("PGDATABASE", "ai_observability"),
        "user": os.getenv("PGUSER", "ai_observability_app"),
        "password": os.getenv("PGPASSWORD"),
    }

    with psycopg.connect(**db_config) as conn:
        with conn.cursor() as cur:
            # 1. Find the best matching complete workflow.
            cur.execute(
                """
                SELECT
                    workflow_name,
                    content,
                    metadata,
                    embedding <=> %s::vector AS distance
                FROM workflow_chunks
                WHERE step_id = %s
                  AND metadata->>'record_type' = 'workflow'
                  AND metadata->>'application' ILIKE %s
                ORDER BY embedding <=> %s::vector
                LIMIT 1
                """,
                (
                    embedding_text,
                    WORKFLOW_RECORD_ID,
                    f"%{application}%",
                    embedding_text,
                ),
            )

            workflow = cur.fetchone()

            if workflow is None:
                print(
                    "\nNo matching workflow found for this application."
                )
                print(
                    "Check the application name or ingest a workflow "
                    "for that application first."
                )
                return

            workflow_name, workflow_content, metadata, distance = workflow

            if isinstance(metadata, str):
                metadata = json.loads(metadata)

            print("\n" + "=" * 60)
            print("BEST MATCHING WORKFLOW")
            print("=" * 60)
            print(f"Name: {workflow_name}")
            print(f"Application: {metadata.get('application', 'Unknown')}")
            print(f"Similarity: {1 - distance:.4f}")
            print("\nWorkflow overview:")
            print(workflow_content)

            # 2. Load the complete ordered steps for that workflow.
            cur.execute(
                """
                SELECT
                    step_id,
                    content,
                    metadata
                FROM workflow_chunks
                WHERE workflow_name = %s
                  AND metadata->>'record_type' = 'step'
                ORDER BY step_id
                """,
                (workflow_name,),
            )

            steps = cur.fetchall()

            print("\n" + "=" * 60)
            print(f"WORKFLOW STEPS ({len(steps)})")
            print("=" * 60)

            for step_id, content, step_metadata in steps:
                if isinstance(step_metadata, str):
                    step_metadata = json.loads(step_metadata)

                print(f"\n{step_id}")
                print(content)
                print(
                    "Review status:",
                    step_metadata.get(
                        "review_status", "unknown"
                    ),
                )
                print(
                    "Execution ready:",
                    step_metadata.get(
                        "execution_ready", False
                    ),
                )

    print("\nRetrieval finished. No automation was executed.")


if __name__ == "__main__":
    main()
