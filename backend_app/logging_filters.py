import logging
import re

#: Matches OpenAI-style keys, including the sk-proj- and sk-svcacct- variants.
_KEY_PATTERN = re.compile(r"sk-[A-Za-z0-9_\-]{16,}")

_REPLACEMENT = "sk-***REDACTED***"


class RedactingFilter(logging.Filter):
    """Strips anything shaped like an API key out of log records.

    Keys are never logged deliberately, but a stack trace or a third-party
    library can echo a request. This filter is the backstop that keeps a
    credential out of the log file even when something upstream misbehaves.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = _KEY_PATTERN.sub(_REPLACEMENT, record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: _KEY_PATTERN.sub(_REPLACEMENT, v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            else:
                record.args = tuple(
                    _KEY_PATTERN.sub(_REPLACEMENT, a) if isinstance(a, str) else a
                    for a in record.args
                )
        return True
