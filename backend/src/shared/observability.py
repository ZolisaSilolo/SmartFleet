"""
Shared Powertools instances (structured JSON logs, EMF metrics, X-Ray tracing).

Logging rules (POPIA): never log request bodies, driver names, phone numbers or licence numbers.
Log identifiers (tenant_id, record ids) and error classes only.
"""
import os

from aws_lambda_powertools import Logger, Metrics, Tracer

SERVICE_NAME = os.environ.get("POWERTOOLS_SERVICE_NAME", "smart-fleet")

logger = Logger(service=SERVICE_NAME)
metrics = Metrics(namespace=os.environ.get("POWERTOOLS_METRICS_NAMESPACE", "SmartFleet"), service=SERVICE_NAME)
tracer = Tracer(service=SERVICE_NAME)
