"""
Prometheus 指标
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Counter:
    """计数器"""
    name: str
    help_text: str = ""
    _value: float = 0.0

    def inc(self, amount: float = 1.0) -> None:
        self._value += amount

    def to_prometheus(self) -> str:
        lines = []
        if self.help_text:
            lines.append(f"# HELP {self.name} {self.help_text}")
        lines.append(f"# TYPE {self.name} counter")
        lines.append(f"{self.name} {self._value}")
        return "\n".join(lines)


@dataclass
class Gauge:
    """仪表"""
    name: str
    help_text: str = ""
    _value: float = 0.0

    def set(self, value: float) -> None:
        self._value = value

    def inc(self, amount: float = 1.0) -> None:
        self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        self._value -= amount

    def to_prometheus(self) -> str:
        lines = []
        if self.help_text:
            lines.append(f"# HELP {self.name} {self.help_text}")
        lines.append(f"# TYPE {self.name} gauge")
        lines.append(f"{self.name} {self._value}")
        return "\n".join(lines)


class Metrics:
    """指标集合"""

    def __init__(self):
        self._counters: dict[str, Counter] = {}
        self._gauges: dict[str, Gauge] = {}

    def counter(self, name: str, help_text: str = "") -> Counter:
        if name not in self._counters:
            self._counters[name] = Counter(name=name, help_text=help_text)
        return self._counters[name]

    def gauge(self, name: str, help_text: str = "") -> Gauge:
        if name not in self._gauges:
            self._gauges[name] = Gauge(name=name, help_text=help_text)
        return self._gauges[name]

    def to_prometheus(self) -> str:
        lines = []
        for counter in self._counters.values():
            lines.append(counter.to_prometheus())
        for gauge in self._gauges.values():
            lines.append(gauge.to_prometheus())
        return "\n".join(lines)


# 全局实例
metrics = Metrics()

feishu_messages_total = metrics.counter("jackclaw_feishu_messages_total", "Total Feishu messages")
runner_workers_active = metrics.gauge("jackclaw_runner_workers_active", "Active runner workers")
runner_queue_size = metrics.gauge("jackclaw_runner_queue_size", "Runner queue size")
agent_requests_total = metrics.counter("jackclaw_agent_requests_total", "Total Agent requests")
agent_errors_total = metrics.counter("jackclaw_agent_errors_total", "Total Agent errors")
