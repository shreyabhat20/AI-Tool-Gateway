import logging
from collections.abc import Sequence

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult

logger = logging.getLogger("gateway.traces")
_configured = False


class JsonLogSpanExporter(SpanExporter):
    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            attributes = {
                key: value
                for key, value in (span.attributes or {}).items()
                if key in {"http.method", "http.route", "tool.name", "actor.role", "error.code"}
            }
            logger.info(
                "trace span",
                extra={
                    "trace_id": f"{span.context.trace_id:032x}" if span.context else "",
                    "request_id": (span.attributes or {}).get("request.id", ""),
                    "outcome": span.status.status_code.name,
                    "span": span.name,
                    "span_id": f"{span.context.span_id:016x}" if span.context else "",
                    "parent_span_id": f"{span.parent.span_id:016x}" if span.parent else "",
                    "duration_ms": max(0, (span.end_time - span.start_time) / 1_000_000) if span.end_time and span.start_time else 0,
                    "attributes": attributes,
                },
            )
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


def configure_tracing() -> None:
    global _configured
    if _configured:
        return
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(JsonLogSpanExporter()))
    trace.set_tracer_provider(provider)
    _configured = True

