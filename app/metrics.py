"""Minimal in-process Prometheus metrics (text exposition format).

Avoids a hard dependency on prometheus_client — the gateway's metric set is
small and fixed, so we accumulate counters in memory and render on scrape."""
import threading
from collections import defaultdict

_lock = threading.Lock()

# label tuple (nim_model, status) -> count
_requests: dict[tuple, int] = defaultdict(int)
_input_tokens: dict[str, int] = defaultdict(int)
_output_tokens: dict[str, int] = defaultdict(int)
# simple latency histogram buckets (seconds)
_LAT_BUCKETS = [0.5, 1, 2, 5, 10, 30, 60, 120, 300]
_latency_bucket_counts: list[int] = [0] * (len(_LAT_BUCKETS) + 1)
_latency_sum = 0.0
_latency_count = 0
_cache_hits = 0
_cache_misses = 0


def record_request(nim_model: str, status: str, input_tokens: int, output_tokens: int) -> None:
    with _lock:
        _requests[(nim_model, status)] += 1
        _input_tokens[nim_model] += int(input_tokens or 0)
        _output_tokens[nim_model] += int(output_tokens or 0)


def record_latency(seconds: float) -> None:
    global _latency_sum, _latency_count
    with _lock:
        _latency_sum += seconds
        _latency_count += 1
        for i, edge in enumerate(_LAT_BUCKETS):
            if seconds <= edge:
                _latency_bucket_counts[i] += 1
                break
        else:
            _latency_bucket_counts[-1] += 1


def record_cache(hit: bool) -> None:
    global _cache_hits, _cache_misses
    with _lock:
        if hit:
            _cache_hits += 1
        else:
            _cache_misses += 1


def _esc(v: str) -> str:
    return str(v).replace("\\", "\\\\").replace('"', '\\"')


def render() -> str:
    lines: list[str] = []
    with _lock:
        lines.append("# HELP claudenim_requests_total Total gateway requests.")
        lines.append("# TYPE claudenim_requests_total counter")
        for (model, status), count in _requests.items():
            lines.append(
                f'claudenim_requests_total{{model="{_esc(model)}",status="{_esc(status)}"}} {count}'
            )

        lines.append("# HELP claudenim_input_tokens_total Input tokens by model.")
        lines.append("# TYPE claudenim_input_tokens_total counter")
        for model, v in _input_tokens.items():
            lines.append(f'claudenim_input_tokens_total{{model="{_esc(model)}"}} {v}')

        lines.append("# HELP claudenim_output_tokens_total Output tokens by model.")
        lines.append("# TYPE claudenim_output_tokens_total counter")
        for model, v in _output_tokens.items():
            lines.append(f'claudenim_output_tokens_total{{model="{_esc(model)}"}} {v}')

        lines.append("# HELP claudenim_request_latency_seconds Upstream latency.")
        lines.append("# TYPE claudenim_request_latency_seconds histogram")
        cumulative = 0
        for i, edge in enumerate(_LAT_BUCKETS):
            cumulative += _latency_bucket_counts[i]
            lines.append(f'claudenim_request_latency_seconds_bucket{{le="{edge}"}} {cumulative}')
        cumulative += _latency_bucket_counts[-1]
        lines.append(f'claudenim_request_latency_seconds_bucket{{le="+Inf"}} {cumulative}')
        lines.append(f"claudenim_request_latency_seconds_sum {_latency_sum}")
        lines.append(f"claudenim_request_latency_seconds_count {_latency_count}")

        lines.append("# HELP claudenim_cache_hits_total Response cache hits.")
        lines.append("# TYPE claudenim_cache_hits_total counter")
        lines.append(f"claudenim_cache_hits_total {_cache_hits}")
        lines.append("# HELP claudenim_cache_misses_total Response cache misses.")
        lines.append("# TYPE claudenim_cache_misses_total counter")
        lines.append(f"claudenim_cache_misses_total {_cache_misses}")

    return "\n".join(lines) + "\n"
