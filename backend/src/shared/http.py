"""
HTTP plumbing shared by every API Lambda: HTTP API (payload v2) resolver, uniform error mapping,
and the observability-wrapped Lambda handler.
"""
import json
from typing import Any, Callable, Dict, Optional, Type

from aws_lambda_powertools.event_handler import APIGatewayHttpResolver, Response
from aws_lambda_powertools.event_handler.exceptions import ServiceError
from aws_lambda_powertools.utilities.typing import LambdaContext
from pydantic import BaseModel, ValidationError
from shared.auth import UnauthorizedException, get_tenant_id, get_user_id
from shared.errors import ApiError
from shared.observability import logger, metrics, tracer
from shared.response import error


def create_app() -> APIGatewayHttpResolver:
    app = APIGatewayHttpResolver()

    @app.exception_handler(ApiError)
    def _api_error(exc: ApiError) -> Response:
        return error(exc.status_code, exc.code, exc.message, exc.details, exc.headers)

    @app.exception_handler(UnauthorizedException)
    def _unauthorized(exc: UnauthorizedException) -> Response:
        return error(401, "UNAUTHORIZED", str(exc))

    @app.exception_handler(ValidationError)
    def _validation(exc: ValidationError) -> Response:
        return error(400, "VALIDATION_ERROR", "Validation error", exc.errors(include_url=False, include_context=False, include_input=False))

    @app.exception_handler(json.JSONDecodeError)
    def _bad_json(_: json.JSONDecodeError) -> Response:
        return error(400, "INVALID_JSON", "Request body must be valid JSON")

    @app.exception_handler(ServiceError)
    def _framework_error(exc: ServiceError) -> Response:
        # Raised by the router itself (unknown route -> 404, method not allowed -> 405, ...).
        return error(exc.status_code, "NOT_FOUND" if exc.status_code == 404 else "REQUEST_ERROR", str(exc.msg))

    @app.exception_handler(Exception)
    def _unexpected(exc: Exception) -> Response:
        # Never leak internals to the caller; the stack trace goes to CloudWatch only.
        logger.exception("unhandled_error", extra={"error_type": type(exc).__name__})
        metrics.add_metric(name="UnhandledErrors", unit="Count", value=1)
        return error(500, "INTERNAL_ERROR", "Internal server error")

    return app


def tenant(app: APIGatewayHttpResolver) -> str:
    tenant_id = get_tenant_id(app.current_event.raw_event)
    logger.append_keys(tenant_id=tenant_id)
    return tenant_id


def user(app: APIGatewayHttpResolver) -> str:
    return get_user_id(app.current_event.raw_event)


def parse_body[M: BaseModel](app: APIGatewayHttpResolver, model: Type[M]) -> M:
    body = app.current_event.json_body
    if not isinstance(body, dict):
        raise ApiError(400, "INVALID_BODY", "Request body must be a JSON object")
    return model(**body)


def query_param(app: APIGatewayHttpResolver, name: str) -> Optional[str]:
    params = app.current_event.query_string_parameters or {}
    value = params.get(name)
    return value if value else None


def make_handler(app: APIGatewayHttpResolver) -> Callable[[Dict[str, Any], LambdaContext], Dict[str, Any]]:
    """Wrap `app.resolve` with structured logging, metrics (EMF) and X-Ray tracing."""

    @logger.inject_lambda_context(clear_state=True)
    @tracer.capture_lambda_handler
    @metrics.log_metrics(capture_cold_start_metric=True)
    def lambda_handler(event: Dict[str, Any], context: LambdaContext) -> Dict[str, Any]:
        return app.resolve(event, context)

    return lambda_handler
