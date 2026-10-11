from contextvars import ContextVar

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)
# Ids added to every log line of the request (user_id, ride_id). A dict set by the middleware, so
# dependencies deeper in the request can fill it in.
log_fields_ctx: ContextVar[dict[str, str] | None] = ContextVar("log_fields", default=None)


def set_log_field(name: str, value: object) -> None:
    fields = log_fields_ctx.get()
    if fields is not None and value is not None:
        fields[name] = str(value)
