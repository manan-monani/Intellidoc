"""
IntelliDoc Document Processing DAG
===================================
Apache Airflow DAG that orchestrates the full ML processing pipeline.

What is Airflow?
    Apache Airflow is a workflow orchestration tool.
    Think of it as a scheduler that runs tasks in a specific order.

    A DAG (Directed Acyclic Graph) defines:
    - WHAT tasks to run
    - In WHAT ORDER (dependencies)
    - WHEN to run them (schedule)

This DAG processes a document through the full ML pipeline:
    Upload → OCR → Classification → NER → Summarization → Embedding → Done

Industry context:
    - Airflow is the #1 workflow tool in data engineering
    - Used by Airbnb (created it), Spotify, Twitter, etc.
    - Alternatives: Prefect, Dagster, Luigi
"""

from datetime import datetime, timedelta

# NOTE: These imports work when running inside an Airflow environment.
# For development, you can test the individual functions directly.
try:
    from airflow import DAG
    from airflow.operators.python import PythonOperator
    AIRFLOW_AVAILABLE = True
except ImportError:
    AIRFLOW_AVAILABLE = False


# ── Task Functions ───────────────────────────────────────────
# Each function is one step in the pipeline.
# They communicate via Airflow's XCom (cross-communication).

def extract_text(**kwargs):
    """
    Task 1: OCR — Extract text from the document.

    Reads the document from S3, runs OCR, saves text to DB.
    """
    document_id = kwargs["dag_run"].conf.get("document_id")

    import requests
    response = requests.post(
        f"http://localhost:8000/api/ml/{document_id}/ocr"
    )

    result = response.json()
    # Push result to XCom for downstream tasks
    kwargs["ti"].xcom_push(key="ocr_result", value=result)
    return result


def classify_document(**kwargs):
    """
    Task 2: Classification — Determine document type.
    """
    document_id = kwargs["dag_run"].conf.get("document_id")

    import requests
    response = requests.post(
        f"http://localhost:8000/api/ml/{document_id}/classify"
    )
    return response.json()


def extract_entities(**kwargs):
    """
    Task 3: NER — Extract named entities.
    """
    document_id = kwargs["dag_run"].conf.get("document_id")

    import requests
    response = requests.post(
        f"http://localhost:8000/api/ml/{document_id}/ner"
    )
    return response.json()


def summarize_text(**kwargs):
    """
    Task 4: Summarization — Generate document summary.
    """
    document_id = kwargs["dag_run"].conf.get("document_id")

    import requests
    response = requests.post(
        f"http://localhost:8000/api/ml/{document_id}/summarize"
    )
    return response.json()


def generate_embeddings(**kwargs):
    """
    Task 5: Embedding — Index document for RAG.
    """
    document_id = kwargs["dag_run"].conf.get("document_id")

    import requests
    response = requests.post(
        f"http://localhost:8000/api/rag/{document_id}/index"
    )
    return response.json()


def update_status(**kwargs):
    """
    Task 6: Update document status to 'processed'.
    """
    document_id = kwargs["dag_run"].conf.get("document_id")

    import requests
    response = requests.patch(
        f"http://localhost:8000/api/documents/{document_id}",
        json={"status": "processed"},
    )
    return {"status": "completed", "document_id": document_id}


# ── DAG Definition ───────────────────────────────────────────

if AIRFLOW_AVAILABLE:
    default_args = {
        "owner": "intellidoc",
        "depends_on_past": False,
        "email_on_failure": False,
        "retries": 2,
        "retry_delay": timedelta(minutes=2),
    }

    dag = DAG(
        dag_id="intellidoc_document_pipeline",
        description="Process uploaded documents through the ML pipeline",
        default_args=default_args,
        schedule_interval=None,  # Triggered manually or by webhook
        start_date=datetime(2024, 1, 1),
        catchup=False,
        tags=["intellidoc", "ml", "document-processing"],
    )

    # Define tasks
    t_ocr = PythonOperator(
        task_id="extract_text_ocr",
        python_callable=extract_text,
        dag=dag,
    )

    t_classify = PythonOperator(
        task_id="classify_document",
        python_callable=classify_document,
        dag=dag,
    )

    t_ner = PythonOperator(
        task_id="extract_entities_ner",
        python_callable=extract_entities,
        dag=dag,
    )

    t_summarize = PythonOperator(
        task_id="summarize_document",
        python_callable=summarize_text,
        dag=dag,
    )

    t_embed = PythonOperator(
        task_id="generate_embeddings",
        python_callable=generate_embeddings,
        dag=dag,
    )

    t_done = PythonOperator(
        task_id="update_status_done",
        python_callable=update_status,
        dag=dag,
    )

    # ─ Define Execution Order ────────────────────────────────
    # OCR must run first (other tasks need the extracted text)
    # Classification, NER, and Summarization can run in parallel
    # Embedding runs after all ML tasks complete
    # Status update is the final step
    #
    #              ┌─ classify ─┐
    # ocr ────────>├─ ner ──────├───> embed ───> done
    #              └─ summarize─┘

    t_ocr >> [t_classify, t_ner, t_summarize]
    [t_classify, t_ner, t_summarize] >> t_embed >> t_done
