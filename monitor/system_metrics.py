from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

import psutil
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

from app.config import PROJECT_ROOT
from monitor.metrics import METRICS_REGISTRY


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DiskMetrics:
    mount: str
    usage_percent: float = 0.0
    free_bytes: int = 0


@dataclass(frozen=True)
class SystemMetricsSnapshot:
    cpu_usage_percent: float = 0.0
    cpu_count: int = 0
    process_cpu_usage_percent: float = 0.0
    memory_usage_percent: float = 0.0
    memory_available_bytes: int = 0
    process_memory_rss_bytes: int = 0
    disks: tuple[DiskMetrics, ...] = field(default_factory=tuple)
    disk_read_bytes_total: int = 0
    disk_write_bytes_total: int = 0
    network_sent_bytes_total: int = 0
    network_recv_bytes_total: int = 0


_PROCESS = psutil.Process()
_snapshot = SystemMetricsSnapshot(cpu_count=psutil.cpu_count() or 0)
_snapshot_lock = threading.Lock()
_collector_registered = False
_collector_lock = threading.Lock()
_collector_thread: threading.Thread | None = None
_collector_stop_event: threading.Event | None = None


class SystemMetricsCollector:
    """Expose periodically collected system resource metrics."""

    def collect(self):
        snapshot = get_system_metrics_snapshot()

        yield GaugeMetricFamily(
            "system_cpu_usage_percent",
            "Whole-machine CPU usage percentage.",
            value=float(snapshot.cpu_usage_percent),
        )
        yield GaugeMetricFamily(
            "system_cpu_count",
            "Number of CPU cores visible to the process.",
            value=int(snapshot.cpu_count),
        )
        yield GaugeMetricFamily(
            "process_cpu_usage_percent",
            "FastAPI process CPU usage percentage.",
            value=float(snapshot.process_cpu_usage_percent),
        )
        yield GaugeMetricFamily(
            "system_memory_usage_percent",
            "Whole-machine memory usage percentage.",
            value=float(snapshot.memory_usage_percent),
        )
        yield GaugeMetricFamily(
            "system_memory_available_bytes",
            "Available system memory in bytes.",
            value=int(snapshot.memory_available_bytes),
        )
        yield GaugeMetricFamily(
            "process_memory_rss_bytes",
            "FastAPI process RSS memory in bytes.",
            value=int(snapshot.process_memory_rss_bytes),
        )

        disk_usage = GaugeMetricFamily(
            "system_disk_usage_percent",
            "Disk usage percentage for monitored mounts.",
            labels=["mount"],
        )
        disk_free = GaugeMetricFamily(
            "system_disk_free_bytes",
            "Free disk space in bytes for monitored mounts.",
            labels=["mount"],
        )
        for disk in snapshot.disks:
            disk_usage.add_metric([disk.mount], float(disk.usage_percent))
            disk_free.add_metric([disk.mount], int(disk.free_bytes))
        yield disk_usage
        yield disk_free

        yield CounterMetricFamily(
            "system_disk_read_bytes_total",
            "Cumulative disk read bytes reported by the OS.",
            value=int(snapshot.disk_read_bytes_total),
        )
        yield CounterMetricFamily(
            "system_disk_write_bytes_total",
            "Cumulative disk write bytes reported by the OS.",
            value=int(snapshot.disk_write_bytes_total),
        )
        yield CounterMetricFamily(
            "system_network_sent_bytes_total",
            "Cumulative network sent bytes reported by the OS.",
            value=int(snapshot.network_sent_bytes_total),
        )
        yield CounterMetricFamily(
            "system_network_recv_bytes_total",
            "Cumulative network received bytes reported by the OS.",
            value=int(snapshot.network_recv_bytes_total),
        )


def collect_system_metrics(project_root: str | Path | None = None) -> SystemMetricsSnapshot:
    """Collect one system metrics snapshot and publish it to the registry collector."""
    root = Path(project_root or PROJECT_ROOT)
    mount = _disk_mount_for(root)
    disk = psutil.disk_usage(mount)
    memory = psutil.virtual_memory()
    disk_io = psutil.disk_io_counters()
    network_io = psutil.net_io_counters()
    process_memory = _PROCESS.memory_info()

    snapshot = SystemMetricsSnapshot(
        cpu_usage_percent=float(psutil.cpu_percent(interval=None)),
        cpu_count=int(psutil.cpu_count() or 0),
        process_cpu_usage_percent=float(_PROCESS.cpu_percent(interval=None)),
        memory_usage_percent=float(memory.percent),
        memory_available_bytes=int(memory.available),
        process_memory_rss_bytes=int(process_memory.rss),
        disks=(
            DiskMetrics(
                mount=str(mount),
                usage_percent=float(disk.percent),
                free_bytes=int(disk.free),
            ),
        ),
        disk_read_bytes_total=int(disk_io.read_bytes) if disk_io else 0,
        disk_write_bytes_total=int(disk_io.write_bytes) if disk_io else 0,
        network_sent_bytes_total=int(network_io.bytes_sent) if network_io else 0,
        network_recv_bytes_total=int(network_io.bytes_recv) if network_io else 0,
    )
    _set_system_metrics_snapshot(snapshot)
    return snapshot


def get_system_metrics_snapshot() -> SystemMetricsSnapshot:
    with _snapshot_lock:
        return _snapshot


def start_system_metrics_collector(interval_seconds: float = 5.0) -> bool:
    """Start the background system metrics collector once per process."""
    register_system_metrics_collector()
    interval = max(float(interval_seconds or 5.0), 1.0)

    global _collector_thread, _collector_stop_event
    with _collector_lock:
        if _collector_thread and _collector_thread.is_alive():
            return False
        _collector_stop_event = threading.Event()
        _collector_thread = threading.Thread(
            target=_system_metrics_loop,
            args=(_collector_stop_event, interval),
            name="system-metrics",
            daemon=True,
        )
        _collector_thread.start()
        return True


def stop_system_metrics_collector(timeout_seconds: float = 2.0) -> None:
    global _collector_thread, _collector_stop_event
    with _collector_lock:
        thread = _collector_thread
        stop_event = _collector_stop_event
        _collector_thread = None
        _collector_stop_event = None
    if stop_event:
        stop_event.set()
    if thread and thread.is_alive():
        thread.join(timeout=timeout_seconds)


def register_system_metrics_collector() -> None:
    global _collector_registered
    with _collector_lock:
        if _collector_registered:
            return
        METRICS_REGISTRY.register(SystemMetricsCollector())
        _collector_registered = True


def _system_metrics_loop(stop_event: threading.Event, interval_seconds: float) -> None:
    while not stop_event.is_set():
        try:
            collect_system_metrics()
        except Exception:
            logger.debug("Failed to collect system metrics", exc_info=True)
        stop_event.wait(interval_seconds)


def _set_system_metrics_snapshot(snapshot: SystemMetricsSnapshot) -> None:
    global _snapshot
    with _snapshot_lock:
        _snapshot = snapshot


def _disk_mount_for(path: Path) -> str:
    resolved = path.resolve()
    return resolved.anchor or "/"


register_system_metrics_collector()
