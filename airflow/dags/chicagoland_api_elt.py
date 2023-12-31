import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.empty import EmptyOperator
from web.operators.chi_api_to_pg_to_gcs import LandInvToPostgresOperator
from airflow.providers.dbt.cloud.operators.dbt import DbtCloudRunJobOperator
from airflow.providers.google.cloud.transfers.gcs_to_bigquery import GCSToBigQueryOperator
from airflow.providers.google.cloud.transfers.postgres_to_gcs import PostgresToGCSOperator



AIRFLOW_HOME = os.environ.get("AIRFLOW_HOME", "/opt/airflow/")


PROJECT_ID = os.environ.get("GCP_PROJECT_ID")
DESTINATION_BUCKET = "bascket1" #os.environ.get("GCP_GCS_BUCKET")

DATASET="raw"

API_TOKEN1 = os.environ.get("API_TOKEN1")

# Database configuration
PG_HOST = os.environ.get("PG_HOST")
PG_PORT = os.environ.get("PG_PORT")
PG_DATABASE = os.environ.get("PG_DATABASE")
PG_USER = os.environ.get("PG_USER")
PG_PASSWORD = os.environ.get("PG_PASSWORD")


DEFAULT_ARGS = {
    "owner": "airflow",
    "start_date": datetime(2023, 11, 20),
    "email": [os.getenv("ALERT_EMAIL", "")],
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

with DAG(
    dag_id="Load-Land-Data-From-Web-To-PG-To-GCS-To-BQ",
    description="Job to move data from Chicago Land website to Postgres to Google Cloud Storage and then transfer from GCS to BigQuery, and finally create a data model using dbt",
    default_args=DEFAULT_ARGS,
    schedule_interval="0 21 * * *",
    max_active_runs=1,
    catchup=True,
    tags=["Land-Website-to-PG-GCS-Bucket-to-BQ"],
) as dag:
    start = EmptyOperator(task_id="start")

    # Use the new EvictionToGCSBQOperator
    download_web_to_gcs_bq = LandInvToPostgresOperator(
        task_id='download_to_gcs',
        api_token=API_TOKEN1,
        user=PG_USER,
        password=PG_PASSWORD,
        host=PG_HOST,
        port=PG_PORT,
        db=PG_DATABASE,
    )

    get_data = PostgresToGCSOperator(
        task_id="transfer_street_names_data_from_Postgres_to_GCS",
        postgres_conn_id='postgres_default',
        sql=f"SELECT * FROM chicago_street_names",
        bucket=DESTINATION_BUCKET,
        filename=f"chicago/street_names_data.json",
        gzip=False,
    )

    load_gcs_to_bgquery =  GCSToBigQueryOperator(
        task_id = "load_gcs_to_bgquery",
        bucket=f"{DESTINATION_BUCKET}", #BUCKET
        source_objects=['chicago/street_names_data.json'], # SOURCE OBJECT
        destination_project_dataset_table=f"{DATASET}.chicago_street_names_data", # `nyc.green_dataset_data` i.e table name
        autodetect=True, #DETECT SCHEMA : the columns and the type of data in each columns of the json file
        write_disposition="WRITE_TRUNCATE", # command to update table from the  latest (or last row) row number upon every job run or task run
        source_format="NEWLINE_DELIMITED_JSON",
    )

    end = EmptyOperator(task_id="end")

    start >> download_web_to_gcs_bq >> get_data >> load_gcs_to_bgquery >> end
