import json
import os
import time
from pathlib import Path


ALLOWED_FIELDS = {
    "attempt_id", "backend", "cancel_cause", "elapsed_us", "failure_class",
    "fallback_kind", "input_bytes", "outcome", "sample_rate",
}


class ObservationRecorder:
    """Bounded, metadata-only buffer; offer() performs no filesystem I/O."""

    def __init__(self, path=None, request_id=None, max_records=256,
                 max_file_bytes=1024 * 1024, enabled=None):
        self.path = Path(path).expanduser() if path else None
        self.request_id = request_id or os.environ.get(
            "READ_SELECTED_TEXT_REQUEST_ID", "unknown")
        self.max_records = max_records
        self.max_file_bytes = max_file_bytes
        self.enabled = bool(self.path) if enabled is None else enabled
        self._records = []
        self._started_ns = time.monotonic_ns()
        self.dropped_count = 0

    @classmethod
    def from_environment(cls):
        return cls(path=os.environ.get("READ_SELECTED_TEXT_OBSERVATION_PATH"))

    def offer(self, kind, **metadata):
        unknown = set(metadata) - ALLOWED_FIELDS
        if unknown:
            raise ValueError(f"unsupported observation fields: {sorted(unknown)}")
        if not self.enabled:
            return False
        if len(self._records) >= self.max_records:
            self.dropped_count += 1
            return False
        record = {
            "schema_version": 1,
            "source": "read-selected-text",
            "kind": _safe_token(kind, "kind"),
            "request_id": _safe_token(self.request_id, "request_id"),
            "observed_at_us": time.time_ns() // 1000,
            "since_request_us": (time.monotonic_ns() - self._started_ns) // 1000,
        }
        for key, value in metadata.items():
            if value is None:
                continue
            if isinstance(value, str):
                value = _safe_token(value, key)
            elif type(value) is not int or value < 0:
                raise ValueError(f"invalid metadata value for {key}")
            record[key] = value
        self._records.append(record)
        return True

    def drain(self):
        records, self._records = self._records, []
        return records

    def flush(self):
        records = self.drain()
        if not self.path or (not records and not self.dropped_count):
            return
        if self.dropped_count:
            records.append({
                "schema_version": 1,
                "source": "read-selected-text",
                "kind": "evidence_gap",
                "request_id": self.request_id,
                "dropped_count": self.dropped_count,
                "observed_at_us": time.time_ns() // 1000,
            })
        encoded = "".join(json.dumps(record, sort_keys=True) + "\n"
                          for record in records).encode()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        current = self.path.stat().st_size if self.path.exists() else 0
        if current + len(encoded) > self.max_file_bytes:
            return
        with self.path.open("ab") as output:
            output.write(encoded)


def _safe_token(value, field):
    if not isinstance(value, str) or not value or len(value.encode()) > 256:
        raise ValueError(f"invalid {field}")
    lowered = value.lower()
    if any(marker in lowered for marker in
           ("://", "bearer ", "authorization:", "-----begin ")):
        raise ValueError(f"unsafe {field}")
    return value
