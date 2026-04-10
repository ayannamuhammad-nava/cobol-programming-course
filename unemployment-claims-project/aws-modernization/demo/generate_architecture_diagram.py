"""
Unemployment Claims System - AWS Modernization Architecture Diagram

Prerequisites:
    brew install graphviz
    pip install diagrams

Usage:
    python generate_architecture_diagram.py

Outputs: unemployment_claims_aws_architecture.png
"""

from diagrams import Diagram, Cluster, Edge
from diagrams.aws.compute import Lambda
from diagrams.aws.database import Aurora, RDS
from diagrams.aws.integration import (
    StepFunctions, SQS, SNS, Eventbridge
)
from diagrams.aws.network import APIGateway, VPC
from diagrams.aws.security import Cognito, KMS, SecretsManager
from diagrams.aws.storage import S3
from diagrams.aws.management import Cloudwatch, Cloudtrail, Config
from diagrams.aws.analytics import Quicksight, Athena
from diagrams.aws.general import Client

graph_attr = {
    "fontsize": "28",
    "bgcolor": "white",
    "pad": "0.5",
    "ranksep": "1.2",
    "nodesep": "0.8",
}

with Diagram(
    "Unemployment Claims System\nAWS Modernization Architecture",
    filename="unemployment_claims_aws_architecture",
    show=False,
    direction="TB",
    graph_attr=graph_attr,
):

    # --- Clients / Ingestion ---
    with Cluster("Clients / Ingestion"):
        http_client = Client("Web / Mobile\nClients")
        batch_upload = Client("Batch CSV/JSON\nUploads")
        scheduled = Client("Scheduled Jobs\n(Nightly)")

    # --- Entry Points ---
    with Cluster("API & Event Ingestion"):
        apigw = APIGateway("API Gateway\n(REST)")
        s3_upload = S3("S3 Upload\nBucket")
        eb = Eventbridge("EventBridge\n(Cron Rules)")
        sqs = SQS("SQS Queue\n(claims-cmd-q)")
        cognito = Cognito("Cognito JWT\nAuthorizer")

    http_client >> apigw
    batch_upload >> s3_upload
    scheduled >> eb

    apigw >> cognito
    s3_upload >> sqs
    eb >> Edge(label="trigger") >> sqs

    # --- Orchestration ---
    with Cluster("Policy & Orchestration"):
        step_fn = StepFunctions("Step Functions\n(Orchestrator)")
        opa_lambda = Lambda("OPA Validation\n(Rules R01-R20)")
        dlq_sns = SNS("DLQ + SNS\nAlert")

    cognito >> step_fn
    sqs >> step_fn
    step_fn >> opa_lambda
    opa_lambda >> Edge(label="FAIL", color="red") >> dlq_sns

    # --- Lambda Microservices ---
    with Cluster("Lambda Microservices (x7)"):
        claims_get = Lambda("claims_get")
        claims_create = Lambda("claims_create")
        claims_update = Lambda("claims_update")
        claims_delete = Lambda("claims_delete")
        claims_report = Lambda("claims_report")
        claims_validate = Lambda("claims_validate")
        audit_lambda = Lambda("Audit Log\nLambda")

    step_fn >> Edge(label="route") >> claims_get
    step_fn >> claims_create
    step_fn >> claims_update
    step_fn >> claims_delete
    step_fn >> claims_report
    step_fn >> claims_validate
    step_fn >> audit_lambda

    # --- Data Layer ---
    with Cluster("Data Layer (Private Subnet B)"):
        rds_proxy = RDS("RDS Proxy\n(Connection Pool)")
        aurora = Aurora("Aurora PostgreSQL\n(Multi-AZ, Temporal)")

    claims_get >> rds_proxy
    claims_create >> rds_proxy
    claims_update >> rds_proxy
    claims_delete >> rds_proxy
    claims_report >> rds_proxy
    claims_validate >> rds_proxy
    audit_lambda >> rds_proxy
    rds_proxy >> aurora

    # --- Output Layer ---
    with Cluster("Output / Reporting"):
        quicksight = Quicksight("QuickSight\nDashboards")
        pdf_lambda = Lambda("PDF Generator\nLambda")
        athena = Athena("Athena\n(Ad-hoc SQL)")
        s3_reports = S3("S3 Reports\n(Parquet)")

    aurora >> quicksight
    aurora >> pdf_lambda
    aurora >> Edge(label="export") >> s3_reports
    s3_reports >> athena

    # --- Observability ---
    with Cluster("Observability"):
        cloudwatch = Cloudwatch("CloudWatch\nMetrics & Logs")
        cloudtrail = Cloudtrail("CloudTrail\nAPI Audit")
        sns_alerts = SNS("SNS Alerts\n(Errors)")

    # --- Security ---
    with Cluster("Security"):
        kms = KMS("KMS\n(Encryption)")
        secrets = SecretsManager("Secrets Manager\n(DB Creds)")
        aws_config = Config("AWS Config\n(Compliance)")
