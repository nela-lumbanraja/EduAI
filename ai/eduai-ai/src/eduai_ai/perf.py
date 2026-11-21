"""Live performance of one student's analysis: effective FPS and latency, kept in memory only.

Nothing here is stored in the database and nothing contains image data: per analysed frame only the analysis time
stamp, the frame status and durations in milliseconds are kept, for the last `window_s` seconds (bounded by
`max_samples`). Used by StudentAnalyzer (both frame sources) and shown to admins by GET /api/ai/performance.

Definitions
  fps            frames analysed per second inside the window: (n - 1) / (last ts - first ts); None below 2 frames
  latency_ms     wall time of StudentAnalyzer.process per frame ("total"), and per perception component that
                 actually ran on the frame ("prepare" = resize + colour conversion, "quality", "face", "landmarks",
                 "objects", "clip"); a component that runs
                 every 0.5 s therefore has fewer samples than "total"
  extra_ms       measurements made outside StudentAnalyzer.process by the caller, e.g. in the backend
                 "queue_wait" (time a frame waited for the global analysis semaphore) and "decode" (JPEG -> image)
  percentiles    nearest rank on the samples of the window (p90 of 1-9 samples is the maximum)
"""
import math
import statistics
import threading
from collections import deque
from typing import Dict, Optional

TIMING_KEYS = ("prepare", "quality", "face", "landmarks", "objects", "clip")


def rss_mb() -> Optional[dict]:
    """Memory of THIS process in MB without extra packages: {"rss", "peak"} (peak None where unknown), or None.
    Windows: working set via K32GetProcessMemoryInfo; Linux: /proc/self/status (VmRSS, VmHWM); elsewhere
    (macOS): peak only, from resource.getrusage."""
    import sys
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class Counters(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            c = Counters()
            c.cb = ctypes.sizeof(c)
            k32 = ctypes.WinDLL("kernel32", use_last_error=True)
            k32.GetCurrentProcess.restype = wintypes.HANDLE
            k32.K32GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
            if not k32.K32GetProcessMemoryInfo(k32.GetCurrentProcess(), ctypes.byref(c), c.cb):
                return None
            return {"rss": round(c.WorkingSetSize / 1e6, 1), "peak": round(c.PeakWorkingSetSize / 1e6, 1)}
        with open("/proc/self/status", encoding="ascii") as f:
            kv = dict(line.split(":", 1) for line in f if ":" in line)
        kb = lambda k: int(kv[k].split()[0]) if k in kv else None     # noqa: E731
        rss, peak = kb("VmRSS"), kb("VmHWM")
        return {"rss": round(rss / 1e3, 1) if rss else None, "peak": round(peak / 1e3, 1) if peak else None}
    except OSError:
        try:
            import resource
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss          # bytes on macOS
            return {"rss": None, "peak": round(peak / 1e6, 1)}
        except (ImportError, OSError):
            return None
    except (AttributeError, ValueError):
        return None


def summarize_ms(values) -> Optional[dict]:
    """{"n", "median", "p90", "max"} in ms, or None without values."""
    v = sorted(float(x) for x in values)
    if not v:
        return None
    p90 = v[max(0, math.ceil(0.9 * len(v)) - 1)]
    return {"n": len(v), "median": round(statistics.median(v), 1), "p90": round(p90, 1), "max": round(v[-1], 1)}


class PerfStats:
    def __init__(self, window_s: float = 60.0, max_samples: int = 1200):
        self.window_s = float(window_s)
        self.max_samples = int(max_samples)
        self.samples: deque = deque(maxlen=self.max_samples)     # (ts, status, total_ms, {component: ms})
        self.extra: Dict[str, deque] = {}                        # name -> deque of (ts, ms)
        self.frames_total = 0                                    # since the analyser started (not windowed)
        self._lock = threading.Lock()                            # analysis thread writes, API thread reads

    def record(self, ts: float, status: str, total_ms: float, timing: Optional[Dict[str, float]] = None):
        with self._lock:
            self.frames_total += 1
            self.samples.append((float(ts), status, float(total_ms), dict(timing or {})))
            self._prune(float(ts))

    def record_extra(self, name: str, ts: float, ms: float):
        with self._lock:
            self.extra.setdefault(name, deque(maxlen=self.max_samples)).append((float(ts), float(ms)))
            self._prune(float(ts))

    def _prune(self, now: float):
        for q in (self.samples, *self.extra.values()):
            while q and now - q[0][0] > self.window_s:
                q.popleft()

    def extra_values(self, name: str) -> list:
        """Values (ms) of one extra measurement in the window, e.g. to derive a statistic the snapshot lacks."""
        with self._lock:
            return [v for _, v in self.extra.get(name, ())]

    def totals_ms(self) -> list:
        """Total latency (ms) of every frame in the window, e.g. to combine several students."""
        with self._lock:
            return [x[2] for x in self.samples]

    def snapshot(self, now: Optional[float] = None) -> dict:
        """`now` (same clock as the recorded ts): drop samples older than the window first, so a stream that
        stopped shows 0 frames and fps None instead of its old numbers."""
        with self._lock:
            if now is not None:
                self._prune(float(now))
            s = list(self.samples)
            extra = {name: [v for _, v in q] for name, q in sorted(self.extra.items())}
            frames_total = self.frames_total
        span = s[-1][0] - s[0][0] if len(s) >= 2 else 0.0
        status: Dict[str, int] = {}
        for _, st, _, _ in s:
            status[st] = status.get(st, 0) + 1
        latency = {"total": summarize_ms(x[2] for x in s)}
        for key in TIMING_KEYS:
            latency[key] = summarize_ms(x[3][key] for x in s if key in x[3])
        return {"window_s": self.window_s, "frames": len(s), "frames_total": frames_total,
                "fps": round((len(s) - 1) / span, 2) if span > 0 else None,
                "status": status, "latency_ms": latency,
                "extra_ms": {name: summarize_ms(v) for name, v in extra.items()},
                "last_ts": s[-1][0] if s else None}
