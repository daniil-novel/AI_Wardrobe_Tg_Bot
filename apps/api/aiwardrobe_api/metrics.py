import time
from collections import defaultdict
from threading import Lock

HTTP_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
PROCESS_STARTED_AT = time.time()
_lock = Lock()
_request_counts: defaultdict[tuple[str, str, int], int] = defaultdict(int)
_duration_counts: defaultdict[tuple[str, str], int] = defaultdict(int)
_duration_sums: defaultdict[tuple[str, str], float] = defaultdict(float)
_duration_buckets: defaultdict[tuple[str, str, float], int] = defaultdict(int)


def _label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def record_http_request(method: str, route: str, status_code: int, duration_seconds: float) -> None:
    key = (method, route)
    with _lock:
        _request_counts[(method, route, status_code)] += 1
        _duration_counts[key] += 1
        _duration_sums[key] += duration_seconds
        for bucket in HTTP_BUCKETS:
            if duration_seconds <= bucket:
                _duration_buckets[(method, route, bucket)] += 1


def render_prometheus_metrics(app_env: str, missing_runtime_secrets: int) -> str:
    lines = [
        "# HELP aiwardrobe_app_info Application info.",
        "# TYPE aiwardrobe_app_info gauge",
        f'aiwardrobe_app_info{{env="{_label(app_env)}"}} 1',
        "# HELP aiwardrobe_missing_runtime_secrets Missing runtime secrets.",
        "# TYPE aiwardrobe_missing_runtime_secrets gauge",
        f"aiwardrobe_missing_runtime_secrets {missing_runtime_secrets}",
        "# HELP aiwardrobe_process_uptime_seconds API process uptime.",
        "# TYPE aiwardrobe_process_uptime_seconds gauge",
        f"aiwardrobe_process_uptime_seconds {max(0.0, time.time() - PROCESS_STARTED_AT):.3f}",
        "# HELP aiwardrobe_http_requests_total HTTP requests by route and status.",
        "# TYPE aiwardrobe_http_requests_total counter",
    ]
    with _lock:
        for (method, route, status_code), count in sorted(_request_counts.items()):
            lines.append(
                "aiwardrobe_http_requests_total"
                f'{{method="{_label(method)}",route="{_label(route)}",status="{status_code}"}} {count}'
            )
        lines.extend(
            [
                "# HELP aiwardrobe_http_request_duration_seconds HTTP request duration.",
                "# TYPE aiwardrobe_http_request_duration_seconds histogram",
            ]
        )
        for (method, route), count in sorted(_duration_counts.items()):
            labels = f'method="{_label(method)}",route="{_label(route)}"'
            for bucket in HTTP_BUCKETS:
                bucket_count = _duration_buckets[(method, route, bucket)]
                lines.append(
                    f'aiwardrobe_http_request_duration_seconds_bucket{{{labels},le="{bucket:g}"}} {bucket_count}'
                )
            lines.append(f'aiwardrobe_http_request_duration_seconds_bucket{{{labels},le="+Inf"}} {count}')
            lines.append(f"aiwardrobe_http_request_duration_seconds_count{{{labels}}} {count}")
            lines.append(
                f"aiwardrobe_http_request_duration_seconds_sum{{{labels}}} {_duration_sums[(method, route)]:.6f}"
            )
    lines.append("")
    return "\n".join(lines)
