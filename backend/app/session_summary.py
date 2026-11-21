"""Session Report, Phase 3: interval and metric engine (read only; nothing is written here).

Specification: docs/DESIGN_SESSION_SUMMARY_INTERVAL.md, docs/EDUAI_SESSION_REPORT_IMPLEMENTATION_AUDIT.md (A1-A8).

Two metrics, never mixed:
  * indication duration score  p(i,k) = active(i,k) / analysable(k)   - a share of observed time, NOT a probability
  * average confidence         C(i,k) = mean of the valid confidence samples of that model (N/A without samples)

Session window (A1): S = the earlier of the scheduled start and the first observed second of the exam; E = the later of
report.session_end (earlier of "Selesai" and the scheduled end) and the last observed second; a running session ends
"now" and is provisional. The same window for every student, so intervals line up across students.

Intervals: [S + 300k, min(S + 300(k+1), E)), half open, never of length 0; weight w_k = d_k / 300.
Everything is counted in whole seconds from actual timestamps (observation_seconds masks, event start/end).

Per student and interval:
  observed(k)   seconds with an analysed frame (all frame sources combined with OR)
  analysable(k) observed seconds outside merged CANNOT_ANALYZE periods
  active(i,k)   seconds of the merged episodes of indicator i (cases.episodes_of: overlapping worker/browser events
                once) that are also analysable - so an event left "open" by a crash never adds unobserved time
  coverage(k)   analysable(k) / d_k
  p(i,k)        active / analysable when analysable > 0; otherwise 0 with a no-data reason (owner's decision)
Whole session: P(i) = sum(w_k p(i,k)) / sum(w_k) (no-data intervals stay in the denominator);
               C(i) = sum of samples / number of samples over the session (each valid sample once).
P_total, indicator weights, persistence and calibration are Phase 4 / 5.
"""
import math
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple

from . import cases as casing
from . import calibration, model_availability, observation
from . import report as reporting
from . import summary

ALGO_VERSION = "session-summary-1"
INTERVAL_S = 300
# A window longer than this means a wrong clock or schedule (A1 joins schedule and observation): not computed,
# reported as not available instead of building per-second arrays for months.
MAX_WINDOW_S = 24 * 3600
# Indicators with a duration score (A3, K3, K4). HEAD_TURN_REPEATED is derived from the HEAD_TURN episodes (the same
# head_active signal, temporal.RepeatCounter) and would count the same behaviour twice; backend indicators
# (CAMERA_OFF, MIC_OFF, LOCKDOWN_LOST), info labels and CANNOT_ANALYZE are not behaviour scores.
VIDEO_INDICATORS = ("FACE_ABSENT", "MULTIPLE_PERSONS", "HEAD_TURN", "PHONE_VISIBLE", "BOOK_VISIBLE")
AUDIO_INDICATORS = ("OTHER_VOICE", "WHISPER", "BOOK_SOUND")          # only with audio consent (excluded, not 0)
EXCLUDED = {"HEAD_TURN_REPEATED": "turunan dari episode HEAD_TURN (dihitung sekali)",
            "CAMERA_OFF": "indikasi sistem, bukan skor perilaku", "MIC_OFF": "indikasi sistem, bukan skor perilaku",
            "LOCKDOWN_LOST": "indikasi sistem, bukan skor perilaku"}
# Valid confidence sources per indicator (A2). Indicators without a meaningful model confidence have none (N/A).
CONF_SOURCES = {"PHONE_VISIBLE": ("phone",), "BOOK_VISIBLE": ("book_coco", "book_clip"),
                "OTHER_VOICE": ("speech",), "WHISPER": ("whisper",), "BOOK_SOUND": ("paper",)}

NO_DATA_REASONS = {
    "tidak_hadir": "mahasiswa tidak bergabung ke ujian",
    "belum_bergabung": "mahasiswa belum bergabung",
    "sudah_keluar": "mahasiswa sudah keluar",
    "terputus": "koneksi video terputus",
    "tidak_dapat_dianalisis": "video tidak dapat dianalisis (gelap, buram, beku)",
    "tidak_ada_frame": "tidak ada frame yang dianalisis",
}


# ---------------------------------------------------------------- time helpers
def _epoch(iso: Optional[str]) -> Optional[float]:
    if not iso:
        return None
    d = datetime.fromisoformat(iso)
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


def _iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat(timespec="seconds")


def intervals(start: int, end: int, size: int = INTERVAL_S) -> List[dict]:
    """[{k, start, end, d_s, w}] covering [start, end) in whole seconds: half open, no overlap, no zero length."""
    out, k, a = [], 0, int(start)
    while a < end:
        b = min(a + size, int(end))
        out.append({"k": k, "start": a, "end": b, "d_s": b - a, "w": (b - a) / size})
        k, a = k + 1, b
    return out


def session_window(db, exam: dict, tz_name: str = "", now: Optional[float] = None) -> Optional[dict]:
    """{start, end, scheduled_start, scheduled_end, scheduled_s, observed_first, observed_last, provisional} or None."""
    now = datetime.now(timezone.utc).timestamp() if now is None else now
    win = summary.exam_window(exam, tz_name)
    span = observation.observation_span(db, exam["id"])
    starts = [x for x in ((win[0].timestamp() if win else None), (span[0] if span else None)) if x is not None]
    if not starts:
        return None
    end_ref = reporting.session_end(exam, tz_name)
    ends = [x for x in ((end_ref.timestamp() if end_ref else None), (span[1] if span else None)) if x is not None]
    start = int(math.floor(min(starts)))
    end = int(math.ceil(max(ends))) if ends else start
    provisional = end > now
    if provisional:
        end = int(math.floor(now))
    return {"start": start, "end": max(start, end), "provisional": provisional,
            "scheduled_start": win[0].timestamp() if win else None, "scheduled_end": win[1].timestamp() if win else None,
            "scheduled_s": (win[1] - win[0]).total_seconds() if win else None,
            "observed_first": span[0] if span else None, "observed_last": span[1] if span else None}


# ---------------------------------------------------------------- per-second arrays over [S, E)
def _mark(arr: bytearray, start: int, a: float, b: float):
    """Set seconds floor(a) .. ceil(b)-1 that lie inside the array (whole seconds touched by [a, b))."""
    lo, hi = max(0, int(math.floor(a)) - start), min(len(arr), int(math.ceil(b)) - start)
    if hi > lo:
        arr[lo:hi] = b"\x01" * (hi - lo)


def _episodes_array(rows: List[dict], start: int, n: int, now: datetime) -> bytearray:
    arr = bytearray(n)
    for ep in casing.episodes_of(rows, now):
        a = _epoch(ep["start_ts"])
        b = _epoch(ep["end_ts"]) if ep["end_ts"] else start + n            # still open: bounded by E and observation
        if b is None or b <= a:
            continue
        _mark(arr, start, a, b)
    return arr


def _and(x: bytearray, y: bytearray) -> bytearray:
    return bytearray(a & b for a, b in zip(x, y))


def _and_not(x: bytearray, y: bytearray) -> bytearray:
    return bytearray(a & (1 - b) for a, b in zip(x, y))


# ---------------------------------------------------------------- confidence (per minute sums -> per interval)
def _conf_rows(db, exam_id: int, student_id: int) -> List[dict]:
    keys = ", ".join(f"{k}_sum, {k}_n" for k in observation.CONF_KEYS)
    return db.all(f"SELECT minute_start, observed_mask, {keys} FROM observation_seconds WHERE exam_id=? AND student_id=?",
                  (exam_id, student_id))


def _bits(mask: int, lo: int, hi: int) -> int:
    """Set bits lo..hi (inclusive) of a minute mask."""
    return bin((mask >> lo) & ((1 << (hi - lo + 1)) - 1)).count("1") if hi >= lo else 0


def minute_share(r: Dict[str, Any], a: int, b: int) -> float:
    """Share of a minute row's samples that belongs to [a, b). Samples are stored per minute; when the minute straddles
    an interval boundary they are split by the row's OBSERVED seconds inside the overlap (video samples only come
    from observed frames), or by time when the row has no observed seconds (audio-only samples)."""
    m = observation.minute_epoch(r["minute_start"])
    lo, hi = max(a, m) - m, min(b, m + 60) - m - 1
    if hi < lo:
        return 0.0
    mask = int(r["observed_mask"] or 0)
    total = _bits(mask, 0, 59)
    return _bits(mask, lo, hi) / total if total else (hi - lo + 1) / 60


def _conf_in(rows: List[dict], source: str, a: int, b: int) -> Tuple[float, float]:
    """(sum, n) of one source in [a, b); sum and n of a shared minute are scaled together, so its mean is kept."""
    s = n = 0.0
    for r in rows:
        if r[f"{source}_n"]:
            f = minute_share(r, a, b)
            s += f * r[f"{source}_sum"]
            n += f * r[f"{source}_n"]
    return s, n


def _mean(s: float, n: float) -> Optional[float]:
    return s / n if n > 0 else None                        # None = N/A (never 0); full precision (T5)


def _confidence(rows: List[dict], indicator: str, a: int, b: int) -> Dict[str, dict]:
    """{source: {"mean": value or None (N/A), "n": effective sample count}} of one indicator in [a, b)."""
    out = {}
    for src in CONF_SOURCES.get(indicator, ()):
        s, n = _conf_in(rows, src, a, b)
        out[src] = {"mean": _mean(s, n), "n": n}
    return out


# ---------------------------------------------------------------- no-data reason
def _disconnected(db, exam_id: int, student_id: int, end: int) -> List[Tuple[float, float]]:
    spans, since = [], None
    for r in db.all("SELECT ts, state FROM connection_log WHERE exam_id=? AND student_id=? ORDER BY ts, id", (exam_id, student_id)):
        t = _epoch(r["ts"])
        if r["state"] == "disconnected" and since is None:
            since = t
        elif r["state"] == "connected" and since is not None:
            spans.append((since, t))
            since = None
    if since is not None:
        spans.append((since, end))
    return spans


def no_data_reason(k: dict, observed_s: int, presence: Optional[dict], offline: List[Tuple[float, float]]) -> str:
    joined = _epoch(presence["joined_at"]) if presence else None
    left = _epoch(presence["left_at"]) if presence else None
    if joined is None:
        return "tidak_hadir"
    if k["end"] <= joined:
        return "belum_bergabung"
    if left is not None and k["start"] >= left:
        return "sudah_keluar"
    if observed_s > 0:
        return "tidak_dapat_dianalisis"
    if sum(max(0, min(k["end"], b) - max(k["start"], a)) for a, b in offline) * 2 >= k["d_s"]:
        return "terputus"
    return "tidak_ada_frame"


# ---------------------------------------------------------------- the engine
def applicable_indicators(audio_accepted: bool) -> List[str]:
    return list(VIDEO_INDICATORS) + (list(AUDIO_INDICATORS) if audio_accepted else [])


def config_exclusions(cfg: Optional[dict]) -> Dict[str, str]:
    """Indicators the ACTIVE configuration cannot produce (T4): disabled indicator, "info" category, or the model
    it needs switched off. They are excluded with this reason, never scored 0. Defaults are those of
    eduai_ai.temporal (BOOK_VISIBLE off unless enabled; voice labels on; WHISPER / BOOK_SOUND category indication).
    No configuration (unit tests) -> nothing excluded."""
    if not cfg:
        return {}
    ind, models = cfg.get("indicators") or {}, cfg.get("models") or {}
    on = lambda name, default=True: bool((ind.get(name) or {}).get("enabled", default))      # noqa: E731
    model_on = lambda name: bool((models.get(name) or {}).get("enabled", True)) if name in models else False  # noqa: E731
    out = {}
    if not on("BOOK_VISIBLE", False):
        out["BOOK_VISIBLE"] = "dinonaktifkan di config (indicators.BOOK_VISIBLE.enabled)"
    for name in AUDIO_INDICATORS:
        if not on(name):
            out[name] = f"dinonaktifkan di config (indicators.{name}.enabled)"
        elif name != "OTHER_VOICE" and (ind.get(name) or {}).get("category", "indication") != "indication":
            out[name] = f"kategori info di config (indicators.{name}.category), bukan indikasi"
    if not model_on("object_detector"):
        out["PHONE_VISIBLE"] = "model detektor objek dinonaktifkan di config"
        if not model_on("book_classifier"):
            out.setdefault("BOOK_VISIBLE", "model detektor objek dan CLIP dinonaktifkan di config")
    if not model_on("face_landmarker"):
        out["HEAD_TURN"] = "model face landmarker dinonaktifkan di config"
    if "audio_classifier" in models and not model_on("audio_classifier"):
        for name in AUDIO_INDICATORS:
            out.setdefault(name, "model audio dinonaktifkan di config")
    return out


def config_version(cfg: Optional[dict], weights: Dict[str, float]) -> str:
    """'<config.yaml version>;w=<8 hex>': the fingerprint changes whenever an indicator weight changes (T3), even if
    the version string was not raised. The weights themselves are stored in the snapshot as well."""
    import hashlib
    import json
    digest = hashlib.sha256(json.dumps(weights, sort_keys=True).encode()).hexdigest()[:8]
    return f"{(cfg or {}).get('version', '')};w={digest}"


COVERAGE_ZERO_NOTE = ("Cakupan pengamatan 0%: skor tidak didukung observasi yang memadai. Skor 0 bukan bukti bahwa "
                      "tidak ada indikasi.")


def _audio_n(r: Dict[str, Any]) -> float:
    """Audio samples of one minute row (the three scores normally arrive together; the largest count is used)."""
    return max(r["speech_n"] or 0, r["whisper_n"] or 0, r["paper_n"] or 0)


def _audio_seconds(rows: List[dict], a: int, b: int) -> int:
    """Seconds of [a, b) inside minutes that received at least one audio sample (resolution: one minute, because audio
    samples are stored per minute)."""
    total = 0
    for r in rows:
        if _audio_n(r):
            m = observation.minute_epoch(r["minute_start"])
            total += max(0, min(b, m + 60) - max(a, m))
    return total


def compute_student(db, exam: dict, student_id: int, window: dict, now: Optional[float] = None,
                    indicators: Optional[Iterable[str]] = None, config_excluded: Optional[Dict[str, str]] = None) -> dict:
    """Interval rows and session values of one student (no writes). Values are kept at full precision (T5)."""
    now_dt = datetime.fromtimestamp(datetime.now(timezone.utc).timestamp() if now is None else now, tz=timezone.utc)
    S, E = window["start"], window["end"]
    n = max(0, E - S)
    consent = db.one("SELECT audio_accepted FROM consents WHERE exam_id=? AND student_id=?", (exam["id"], student_id))
    audio = bool(consent and consent["audio_accepted"])
    names = list(indicators) if indicators is not None else applicable_indicators(audio)
    excluded = {i: "tanpa persetujuan audio (dikecualikan, bukan 0)" for i in AUDIO_INDICATORS if i not in names}
    excluded.update(EXCLUDED)
    for i, why in (config_excluded or {}).items():               # T4: follows the active configuration
        if i in names:
            names.remove(i)
        excluded[i] = why

    observed = bytearray(n)
    for minute, mask in observation.observed_masks(db, exam["id"], student_id).items():
        bit = 0
        while mask:
            if mask & 1 and S <= minute + bit < E:
                observed[minute + bit - S] = 1
            mask >>= 1
            bit += 1
    rows = db.all("SELECT * FROM events WHERE exam_id=? AND student_id=?", (exam["id"], student_id))
    cannot = _episodes_array([r for r in rows if r["category"] == "cannot_analyze"], S, n, now_dt)
    analysable = _and_not(observed, cannot)
    active = {i: _and(_episodes_array([r for r in rows if r["category"] == "indication" and r["indicator"] == i], S, n, now_dt),
                      analysable) for i in names}
    presence = db.one("SELECT joined_at, left_at FROM presence WHERE exam_id=? AND student_id=?", (exam["id"], student_id))
    offline = _disconnected(db, exam["id"], student_id, E)
    conf_rows = _conf_rows(db, exam["id"], student_id)

    # T1: consented audio labels without a single audio sample in the whole session are excluded (no_audio_data),
    # so missing audio is never read as "no sound indication" and does not lower P_total.
    audio_scored = [i for i in names if i in AUDIO_INDICATORS]
    audio_samples = sum(_audio_n(r) for r in conf_rows)
    if audio_scored and audio_samples == 0:
        for i in audio_scored:
            names.remove(i)
            excluded[i] = "no_audio_data: persetujuan audio ada, tetapi tidak ada satu pun sampel audio selama sesi"
        audio_scored = []
    tracks_audio = audio                     # audio coverage is reported apart from video coverage, with consent only
    # D4 (Phase 5): models that did not run for this student. Recorded and flagged only; no score, weight or
    # denominator below changes (Phase 4 formula; decision K7 is pending).
    availability = model_availability.summary(db, exam["id"], student_id, names)

    out_intervals = []
    for k in intervals(S, E):
        a, b = k["start"] - S, k["end"] - S
        obs_s, ana_s = sum(observed[a:b]), sum(analysable[a:b])
        reason = None if ana_s > 0 else no_data_reason(k, obs_s, presence, offline)
        audio_s = _audio_seconds(conf_rows, k["start"], k["end"]) if tracks_audio else None
        row = {**k, "start_ts": _iso(k["start"]), "end_ts": _iso(k["end"]), "observed_s": obs_s, "analysable_s": ana_s,
               "coverage": ana_s / k["d_s"], "no_data_reason": reason, "audio_s": audio_s,
               "audio_coverage": None if audio_s is None else audio_s / k["d_s"], "indicators": {}}
        for i in names:
            act = sum(active[i][a:b])
            if i in audio_scored and not audio_s:                 # partial audio: an interval without audio = 0
                score, why = 0.0, "no_audio_data"
            else:
                score, why = (act / ana_s, None) if ana_s else (0.0, reason)
            row["indicators"][i] = {"active_s": act, "duration_score": score, "no_data_reason": why,
                                    "confidence": _confidence(conf_rows, i, k["start"], k["end"])}
        out_intervals.append(row)

    sum_w = sum(k["w"] for k in out_intervals)
    session = {}
    for i in names:
        P = sum(k["w"] * k["indicators"][i]["duration_score"] for k in out_intervals) / sum_w if sum_w else None
        session[i] = {"duration_score": P,
                      "active_s": sum(k["indicators"][i]["active_s"] for k in out_intervals),
                      "confidence": _confidence(conf_rows, i, S, E)}
    coverage = sum(k["w"] * k["coverage"] for k in out_intervals) / sum_w if sum_w else None
    audio_cov = (sum(k["w"] * k["audio_coverage"] for k in out_intervals) / sum_w) if tracks_audio and sum_w else None
    return {
        "student_id": student_id, "algo_version": ALGO_VERSION, "audio_accepted": audio,
        "intervals": out_intervals, "indicators": session, "excluded": excluded,
        "sum_w": sum_w, "n_intervals": len(out_intervals),
        "n_valid": sum(1 for k in out_intervals if k["analysable_s"] > 0),
        "n_no_data": sum(1 for k in out_intervals if k["analysable_s"] == 0),
        "coverage": coverage,
        "coverage_note": COVERAGE_ZERO_NOTE if coverage == 0 else None,        # T2
        "audio_coverage": audio_cov, "audio_samples": audio_samples if tracks_audio else None,
        "model_availability": availability,
        "observed_s": sum(observed), "analysable_s": sum(analysable),
        # this student's first observed second and the end of the last one (None without observation)
        "observation_start": _iso(S + observed.index(1)) if 1 in observed else None,
        "observation_end": _iso(S + len(observed) - observed[::-1].index(1)) if 1 in observed else None,
    }


# ---------------------------------------------------------------- Phase 4: indicator weights and P_total
SCORED = VIDEO_INDICATORS + AUDIO_INDICATORS
NOT_CALIBRATED = {"status": "not_calibrated", "version": None, "probability": None,
                  "note": "Belum tersedia: belum ada kalibrator yang dilatih dengan data berlabel tingkat sesi."}


def load_weights(cfg: Optional[dict]) -> dict:
    """{"weights": {indicator: v}, "source": text} from config.yaml -> session_summary.indicator_weights.
    Fail-fast on unknown indicators or weights that are not finite numbers >= 0. A missing section or indicator
    gets 1 (the plain mean, decision K5), and the source says so."""
    section = ((cfg or {}).get("session_summary") or {}).get("indicator_weights")
    given = dict(section or {})
    unknown = sorted(set(given) - set(SCORED))
    if unknown:
        raise ValueError(f"session_summary.indicator_weights: indikasi tidak dikenal {unknown}")
    weights, defaulted = {}, []
    for i in SCORED:
        if i not in given:
            weights[i], _ = 1.0, defaulted.append(i)
            continue
        v = given[i]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0:
            raise ValueError(f"session_summary.indicator_weights.{i} harus angka >= 0, bukan {v!r}")
        weights[i] = float(v)
    source = "config.yaml session_summary.indicator_weights" + (f"; bawaan 1 untuk {defaulted}" if defaulted else "")
    return {"weights": weights, "source": source}


def aggregate(student: dict, weights: Dict[str, float]) -> dict:
    """P_total = sum(v_i P_i) / sum(v_i) over the student's scored indicators (excluded ones are not in the sum).
    The indicator weight is applied here only; the interval weights are already inside every P_i."""
    used = {i: weights[i] for i, v in student["indicators"].items() if v["duration_score"] is not None}
    total_w = sum(used.values())
    value = (sum(weights[i] * student["indicators"][i]["duration_score"] for i in used) / total_w) if total_w > 0 else None
    return {"duration_score": value, "weights_used": used,                 # full precision (T5)
            "sum_weights": total_w, "calibration": dict(NOT_CALIBRATED)}


def compute_exam(db, exam: dict, tz_name: str = "", now: Optional[float] = None, weights: Optional[dict] = None,
                 cfg: Optional[Dict[str, Any]] = None, calibrator: Optional[Dict[str, Any]] = None,
                 config_version: str = "", models_fp: str = "", final: bool = False) -> dict:
    """Session Summary of every enrolled student. Exams without any observation data: not available
    (decision A7: sessions before this feature are not recomputed). weights = load_weights(cfg); cfg = the active
    AI configuration, whose disabled / info indicators are excluded (T4).
    Phase 5 Tahap 3: calibrator = calibration.load(...) result. When given, each student's calibration block comes from
    calibration.evaluate (probability only when final=True, T3-2); it reads the values above and changes none of them.
    Without it the Phase 4 block (not_calibrated) stays."""
    weights = weights or load_weights(None)
    cfg_excluded = config_exclusions(cfg)
    window = session_window(db, exam, tz_name, now)
    base = {"exam_id": exam["id"], "algo_version": ALGO_VERSION, "interval_s": INTERVAL_S,
            "weights": weights["weights"], "weights_source": weights["source"], "config_excluded": cfg_excluded}
    if calibrator is not None:
        base["models_fingerprint"] = models_fp or ""
        base["calibration_approved_sha256"] = calibrator.get("approved_sha256")
    if observation.observation_span(db, exam["id"]) is None:
        return {**base, "status": "tidak_tersedia", "reason": "tidak ada data cakupan pengamatan untuk sesi ini", "students": []}
    if window is None:
        return {**base, "status": "tidak_tersedia", "reason": "jadwal dan pengamatan tidak dapat dibaca", "students": []}
    if window["end"] - window["start"] > MAX_WINDOW_S:
        return {**base, "status": "tidak_tersedia", "students": [],
                "reason": f"jendela sesi {window['end'] - window['start']} dtk melebihi {MAX_WINDOW_S} dtk: jam pengamatan "
                          "atau jadwal ujian tidak wajar, periksa sebelum menghitung"}
    students = []
    for r in db.all("SELECT student_id FROM exam_students WHERE exam_id=? ORDER BY student_id", (exam["id"],)):
        st = compute_student(db, exam, r["student_id"], window, now, config_excluded=cfg_excluded)
        st["total"] = aggregate(st, weights["weights"])
        if calibrator is not None:
            st["total"]["calibration"] = calibration.evaluate(st, st["total"], config_version, calibrator, models_fp, final)
        students.append(st)
    return {**base, "status": "sementara" if window["provisional"] else "lengkap",
            "window": {**window, "start_ts": _iso(window["start"]), "end_ts": _iso(window["end"]), "duration_s": window["end"] - window["start"]},
            "students": students}


# ---------------------------------------------------------------- Phase 4: snapshot at finalisation
_INTERVAL_SQL = ("INSERT OR IGNORE INTO session_interval_summary (exam_id,student_id,indicator,k,conf_source,start_ts,end_ts,d_s,w,"
                 "active_s,analysable_s,coverage,duration_score,conf_mean,conf_n,no_data_reason,algo_version,config_version,"
                 "computed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")
_PARTICIPANT_SQL = ("INSERT OR IGNORE INTO session_participant_summary (exam_id,student_id,indicator,duration_score,coverage,"
                    "sum_w,n_intervals,n_no_data,observed_s,scheduled_s,observation_start,observation_end,conf_json,weights_json,"
                    "config_version,algo_version,calibration_status,calibration_version,calibrated_probability,computed_at)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)")


def snapshot_statements(result: dict, config_version: str, computed_at: str) -> List[Tuple[str, tuple]]:
    """(sql, params) for every interval row and participant row of a computed exam, to run in the SAME transaction
    as report_finals (api.finalize_report). INSERT OR IGNORE + primary keys: a repeated call cannot duplicate rows.
    Nothing for an exam whose summary is not available (A7)."""
    import json
    if result.get("status") not in ("lengkap", "sementara"):
        return []
    out, ex, scheduled = [], result["exam_id"], result["window"].get("scheduled_s")
    for st in result["students"]:
        sid = st["student_id"]
        for k in st["intervals"]:
            for ind, v in k["indicators"].items():
                out.append((_INTERVAL_SQL, (ex, sid, ind, k["k"], "", k["start_ts"], k["end_ts"], k["d_s"], k["w"], v["active_s"],
                                            k["analysable_s"], k["coverage"], v["duration_score"], None, None,
                                            v.get("no_data_reason", k["no_data_reason"]), ALGO_VERSION, config_version,
                                            computed_at)))
                for src, c in v["confidence"].items():
                    out.append((_INTERVAL_SQL, (ex, sid, ind, k["k"], src, k["start_ts"], k["end_ts"], k["d_s"], k["w"], None,
                                                k["analysable_s"], k["coverage"], None, c["mean"], round(c["n"]),
                                                k["no_data_reason"], ALGO_VERSION, config_version, computed_at)))
        common = (st["coverage"], st["sum_w"], st["n_intervals"], st["n_no_data"], st["observed_s"], scheduled,
                  st["observation_start"], st["observation_end"])
        for ind, v in st["indicators"].items():
            out.append((_PARTICIPANT_SQL, (ex, sid, ind, v["duration_score"], *common, json.dumps(v["confidence"]),
                                           json.dumps({"weight": result["weights"][ind]}), config_version, ALGO_VERSION,
                                           "not_calibrated", None, None, computed_at)))
        t = st["total"]
        meta = {"weights": result["weights"], "weights_used": t["weights_used"], "source": result["weights_source"],
                "excluded": st["excluded"], "audio_accepted": st["audio_accepted"], "status": result["status"],
                "coverage_note": st["coverage_note"], "audio_coverage": st["audio_coverage"],
                "audio_samples": st["audio_samples"], "config_excluded": result.get("config_excluded", {}),
                "model_availability": st.get("model_availability")}
        cal = t["calibration"]
        if "reasons" in cal:                               # Phase 5 Tahap 3: why (not) calibrated, frozen with the row
            meta["calibration_reasons"], meta["calibration_details"] = cal["reasons"], cal.get("details") or {}
        for key in ("calibration_approved_sha256", "models_fingerprint"):      # C6, C7
            if key in result:
                meta[key] = result[key]
        out.append((_PARTICIPANT_SQL, (ex, sid, "*", t["duration_score"], *common, None, json.dumps(meta), config_version,
                                       ALGO_VERSION, cal["status"], cal["version"], cal["probability"], computed_at)))
    return out


def read_snapshot(db, exam_id: int) -> Optional[dict]:
    """The frozen summary of a finalised exam, or None when nothing was stored (e.g. finalised before this feature)."""
    import json
    rows = db.all("SELECT * FROM session_participant_summary WHERE exam_id=? ORDER BY student_id, indicator", (exam_id,))
    if not rows:
        return None
    students: Dict[int, dict] = {}
    for r in rows:
        s = students.setdefault(r["student_id"], {"student_id": r["student_id"], "indicators": {}, "total": None,
                                                  "coverage": r["coverage"], "sum_w": r["sum_w"], "n_intervals": r["n_intervals"],
                                                  "n_no_data": r["n_no_data"], "observed_s": r["observed_s"],
                                                  "scheduled_s": r["scheduled_s"], "observation_start": r["observation_start"],
                                                  "observation_end": r["observation_end"]})
        if r["indicator"] == "*":
            meta = json.loads(r["weights_json"] or "{}")
            s["total"] = {"duration_score": r["duration_score"], "weights_used": meta.get("weights_used"),
                          "calibration": {"status": r["calibration_status"], "version": r["calibration_version"],
                                          "probability": r["calibrated_probability"]}}
            s["excluded"], s["audio_accepted"], s["status"] = meta.get("excluded"), meta.get("audio_accepted"), meta.get("status")
            s["weights"], s["weights_source"] = meta.get("weights"), meta.get("source")
            s["coverage_note"], s["audio_coverage"] = meta.get("coverage_note"), meta.get("audio_coverage")
            s["audio_samples"], s["config_excluded"] = meta.get("audio_samples"), meta.get("config_excluded")
            s["model_availability"] = meta.get("model_availability")
            s["calibration_reasons"], s["calibration_details"] = meta.get("calibration_reasons"), meta.get("calibration_details")
            s["calibration_approved_sha256"], s["models_fingerprint"] = (meta.get("calibration_approved_sha256"),
                                                                         meta.get("models_fingerprint"))
        else:
            s["indicators"][r["indicator"]] = {"duration_score": r["duration_score"], "confidence": json.loads(r["conf_json"] or "{}"),
                                               "weight": json.loads(r["weights_json"] or "{}").get("weight")}
    intervals = db.all("SELECT * FROM session_interval_summary WHERE exam_id=? ORDER BY student_id, k, indicator, conf_source", (exam_id,))
    first = rows[0]
    return {"exam_id": exam_id, "source": "final", "algo_version": first["algo_version"], "config_version": first["config_version"],
            "computed_at": first["computed_at"], "students": list(students.values()), "interval_rows": len(intervals)}
