"""Set up OpenTelemetry tracing."""

from collections.abc import Sequence
from pathlib import Path

from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
    SpanExportResult,
)

from app.config import Settings


class JsonLinesSpanExporter(SpanExporter):
    """Append each finished span to a file as one line of JSON. Needs no extra server."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._path = path

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        """Write a batch of spans."""
        try:
            with self._path.open("a", encoding="utf-8") as handle:
                for span in spans:
                    handle.write(span.to_json(indent=None) + "\n")
        except OSError:
            return SpanExportResult.FAILURE
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """Nothing to close: the file is opened per batch."""


def build_tracer_provider(settings: Settings) -> TracerProvider:
    """Create a tracer provider for this app instance.

    Spans are exported in the background in batches, so tracing does not slow a reply.
    """
    provider = TracerProvider(resource=Resource.create({"service.name": "supportloop"}))
    if settings.trace_exporter == "file":
        exporter: SpanExporter = JsonLinesSpanExporter(settings.resolve(settings.trace_file_path))
    elif settings.trace_exporter == "otlp":
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(endpoint=settings.otlp_endpoint)
    else:
        return provider
    provider.add_span_processor(BatchSpanProcessor(exporter))
    return provider
