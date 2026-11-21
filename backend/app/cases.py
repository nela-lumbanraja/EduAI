"""Group indication events into review *cases*.

Nothing is stored for a case: cases are computed from the existing `events` table every time,
so no event row, review or evidence is changed, merged or deleted by grouping.

Grouping rule (one rule, applied the same way everywhere):
  * same exam session, same student and same indicator type -> one case for the whole exam
    (default, gap_s <= 0: one consolidated indication per student and behaviour), or
  * with gap_s > 0 (optional, EDUAI_CASE_GAP_S): additionally the next event must start at most
    gap_s seconds after the previous event of the group ended (an open event ends "now").
  Different exams, students or indicator types are never grouped.

Occurrences (episodes): the AI's temporal rules already turn many frames into one event, so one
event = one qualifying episode. Events of the same case that overlap or touch in time (within
EPISODE_JOIN_S) describe the same behaviour twice - e.g. after a worker restart or from browser
fallback frames analysed in parallel - and are counted as ONE episode. Nothing is deleted.

Rule (product threshold, see RULES): an indicator's rule is "met" when at least min_count
episodes start within window_s seconds (or anywhere in the exam when window_s is None). The case
is shown either way; only the supervisor pop-up waits for the rule.

A case is identified by its first event: case_id = "c-" + event_id of the earliest event.

Review status of a case (derived from its events, never guessed):
  * no event reviewed                    -> None   ("Belum ditinjau")
  * every event has the same decision    -> that decision
  * some events reviewed, some not       -> None, with unreviewed_count > 0. This happens when a new
                                            event joins a case after it was reviewed: the new event is
                                            NOT marked as reviewed automatically.
  * every event reviewed, decisions vary -> "Campuran"
"""
from datetime import datetime, timezone
from typing import Iterable, List, Optional

CASE_PREFIX = "c-"
MIXED = "Campuran"
EPISODE_JOIN_S = 2.0         # AI cooldowns are >= 20 s, so closer events are duplicates of one episode

# Configurable initial PRODUCT rules (not validated model thresholds). Overridden by
# config.yaml -> summary_rules through configure_rules(). Indicators not listed: 1 episode.
DEFAULT_RULES = {
    "PHONE_VISIBLE": {"min_count": 1, "window_s": None},
    "MULTIPLE_PERSONS": {"min_count": 1, "window_s": None},
    "OTHER_VOICE": {"min_count": 1, "window_s": None},
    "FACE_ABSENT": {"min_count": 1, "window_s": None},
    "HEAD_TURN": {"min_count": 1, "window_s": None},
    # one HEAD_TURN_REPEATED episode = 5 look-aways within 120 s (AI config); 4 such episodes per hour
    "HEAD_TURN_REPEATED": {"min_count": 4, "window_s": 3600.0},
    "BOOK_VISIBLE": {"min_count": 1, "window_s": None},       # first book episode notifies (10 Nov 2026)
    "BOOK_SOUND": {"min_count": 1, "window_s": None},         # paper/page sound (book), needs audio consent
    "WHISPER": {"min_count": 1, "window_s": None},
    # camera / microphone switched off by the student during monitoring (app/device.py)
    "CAMERA_OFF": {"min_count": 1, "window_s": None},
    "LOCKDOWN_LOST": {"min_count": 1, "window_s": None},     # SEB lost during the exam (app/lockdown.py): review, not proof
    "MIC_OFF": {"min_count": 1, "window_s": None},
}
RULES = dict(DEFAULT_RULES)


def configure_rules(cfg_rules) -> dict:
    """Load summary_rules from the AI config (missing or invalid entries keep the defaults)."""
    RULES.clear()
    RULES.update(DEFAULT_RULES)
    for name, r in (cfg_rules or {}).items():
        if isinstance(r, dict) and int(r.get("min_count", 0) or 0) >= 1:
            w = r.get("window_s")
            RULES[str(name)] = {"min_count": int(r["min_count"]), "window_s": float(w) if w else None}
    return RULES


def rule_for(indicator: str) -> dict:
    return RULES.get(indicator, {"min_count": 1, "window_s": None})


def _t(iso: str) -> datetime:
    d = datetime.fromisoformat(iso)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)      # stored timestamps are UTC


def _end(row: dict, now: datetime) -> datetime:
    if row.get("end_ts"):
        return _t(row["end_ts"])
    return now if row.get("status") == "open" else _t(row["start_ts"])


def case_id_for(first_event_id: str) -> str:
    return CASE_PREFIX + first_event_id


def event_id_from_case(case_id: str) -> Optional[str]:
    return case_id[len(CASE_PREFIX):] if case_id.startswith(CASE_PREFIX) and len(case_id) > len(CASE_PREFIX) else None


def group_events(rows: Iterable[dict], gap_s: Optional[float], now: Optional[datetime] = None) -> List[List[dict]]:
    """Split indication event rows into cases. Each case is a list of rows in time order.
    gap_s None or <= 0: one case per exam, student and indicator."""
    whole_exam = not gap_s or gap_s <= 0
    now = now or datetime.now(timezone.utc)
    ordered = sorted(rows, key=lambda r: (r["exam_id"], r["student_id"], r["indicator"], _t(r["start_ts"])))
    cases: List[List[dict]] = []
    key, last_end = None, None
    for r in ordered:
        k = (r["exam_id"], r["student_id"], r["indicator"])
        start = _t(r["start_ts"])
        if k != key or last_end is None or (not whole_exam and (start - last_end).total_seconds() > gap_s):
            cases.append([r])
            key, last_end = k, _end(r, now)
        else:
            cases[-1].append(r)
            last_end = max(last_end, _end(r, now))
    return cases


def review_status(events: List[dict]):
    """Returns (status, counts, unreviewed_count) following the rule in the module docstring."""
    counts = {}
    for e in events:
        k = e.get("review_status") or "unreviewed"
        counts[k] = counts.get(k, 0) + 1
    unreviewed = counts.get("unreviewed", 0)
    decisions = [k for k in counts if k != "unreviewed"]
    if unreviewed or not decisions:
        status = None
    elif len(decisions) == 1:
        status = decisions[0]
    else:
        status = MIXED
    return status, counts, unreviewed


def merge_episodes(events: List[dict], now: Optional[datetime] = None, join_s: float = EPISODE_JOIN_S) -> List[dict]:
    """Distinct qualifying episodes of one case: events overlapping/touching in time are one episode."""
    now = now or datetime.now(timezone.utc)
    eps: List[dict] = []
    for e in sorted(events, key=lambda r: _t(r["start_ts"])):
        s, end = _t(e["start_ts"]), _end(e, now)
        if eps and (s - eps[-1]["_end"]).total_seconds() <= join_s:
            ep = eps[-1]
            ep["_end"] = max(ep["_end"], end)
            ep["event_ids"].append(e["event_id"])
            ep["open"] = ep["open"] or e["status"] == "open"
            if e.get("evidence_id") and not ep["evidence_id"]:
                ep["evidence_id"] = e["evidence_id"]
        else:
            eps.append({"_start": s, "_end": end, "start_ts": e["start_ts"], "event_ids": [e["event_id"]],
                        "open": e["status"] == "open", "evidence_id": e.get("evidence_id")})
    for ep in eps:
        ep["end_ts"] = None if ep["open"] else ep["_end"].isoformat(timespec="milliseconds")
        ep["duration_s"] = round(max(0.0, (ep.pop("_end") - ep.pop("_start")).total_seconds()), 1)
    return eps


def episodes_of(rows: Iterable[dict], now: Optional[datetime] = None) -> List[dict]:
    """Every distinct episode in `rows`: grouped per exam, student and indicator (as group_events with gap 0),
    then events that overlap or touch in time count once (merge_episodes). This is the ONE counting rule shared
    by the case list, the exam summary and the session report, so their numbers agree:
      * kejadian (event)   = one row of the events table, the unit a supervisor reviews;
      * indikasi (episode) = the events of one student and behaviour that describe the same moment.
    Durations come from the merged episodes, so overlapping events are never counted twice."""
    now = now or datetime.now(timezone.utc)
    return [ep for group in group_events(rows, 0, now) for ep in merge_episodes(group, now)]


def episode_seconds(episodes: Iterable[dict]) -> float:
    return round(sum(ep["duration_s"] for ep in episodes), 1)


def rule_status(indicator: str, episodes: List[dict]) -> dict:
    """Is the product rule met? Returns min_count, window_s, met, met_at (start of the episode that
    first satisfied it) and the most episodes seen inside one window."""
    r = rule_for(indicator)
    starts = [_t(ep["start_ts"]) for ep in episodes]
    best, met_at = 0, None
    for i, s in enumerate(starts):
        n = sum(1 for x in starts[:i + 1] if r["window_s"] is None or (s - x).total_seconds() <= r["window_s"])
        best = max(best, n)
        if met_at is None and n >= r["min_count"]:
            met_at = episodes[i]["start_ts"]
    return {"min_count": r["min_count"], "window_s": r["window_s"], "met": met_at is not None,
            "met_at": met_at, "max_in_window": best}


def summarize(events: List[dict], now: Optional[datetime] = None) -> dict:
    """One summary row for a case. `events` must be one group from group_events()."""
    now = now or datetime.now(timezone.utc)
    first, last = events[0], events[-1]
    is_open = any(e["status"] == "open" for e in events)
    with_evidence = [e for e in events if e.get("evidence_id")]
    scores = [e["score"] for e in events if e.get("score") is not None]
    status, counts, unreviewed = review_status(events)
    episodes = merge_episodes(events, now)
    return {
        "case_id": case_id_for(first["event_id"]),
        "exam_id": first["exam_id"],
        "student_id": first["student_id"],
        "indicator": first["indicator"],
        "label": next((e["label"] for e in events if e.get("label")), None),
        "event_count": len(events),
        "episode_count": len(episodes),
        "episodes": episodes,
        "rule": rule_status(first["indicator"], episodes),
        "event_ids": [e["event_id"] for e in events],
        "first_event_id": first["event_id"],
        "first_start_ts": first["start_ts"],
        "last_start_ts": last["start_ts"],
        "last_end_ts": None if is_open else max(e["end_ts"] or e["start_ts"] for e in events),
        "status": "open" if is_open else "closed",
        "total_duration_s": episode_seconds(episodes),      # merged episodes: overlapping events count once
        "max_score": max(scores) if scores else None,
        "evidence_count": len(with_evidence),
        "latest_evidence_id": with_evidence[-1]["evidence_id"] if with_evidence else None,
        "review_status": status,
        "review_counts": counts,
        "unreviewed_count": unreviewed,
        "updated_at": max(e["updated_at"] for e in events),
    }


# ---------------------------------------------------------------- review priority (G-P1, 20 Nov 2026)
# Neutral order in which a supervisor may look at cases: facts about the case only, no weight per kind of behaviour,
# no model score, no "level". It says what to look at first, never how serious or likely a violation is.
PRIORITY_ORDER = ("ada kejadian belum ditinjau", "aturan ringkasan terpenuhi", "masih berlangsung",
                  "jumlah indikasi", "total durasi", "aktivitas terbaru")
SORTS = ("priority", "latest")


def _ts(iso: Optional[str]) -> float:
    return _t(iso).timestamp() if iso else 0.0


def priority_key(c: dict) -> tuple:
    """Sort key of a case from summarize() (larger = earlier), in the order of PRIORITY_ORDER."""
    return (c["unreviewed_count"] > 0, bool((c.get("rule") or {}).get("met")), c["status"] == "open",
            c.get("episode_count") or c["event_count"], c["total_duration_s"], _ts(c["last_start_ts"]))


def _duration_text(s: float) -> str:
    s = int(round(s))
    m, sec = divmod(s, 60)
    return f"{m} mnt {sec} dtk" if m else f"{sec} dtk"


def priority_reasons(c: dict) -> List[str]:
    """Short facts shown next to the case, e.g. ["belum ditinjau", "aturan ringkasan terpenuhi", "3 kali", "total 45 dtk"]."""
    out = []
    if c["unreviewed_count"] == c["event_count"]:
        out.append("belum ditinjau")
    elif c["unreviewed_count"]:
        out.append(f"{c['unreviewed_count']} kejadian baru belum ditinjau")
    else:
        out.append("sudah ditinjau")
    if (c.get("rule") or {}).get("met"):
        out.append("aturan ringkasan terpenuhi")
    if c["status"] == "open":
        out.append("masih berlangsung")
    out.append(f"{c.get('episode_count') or c['event_count']} kali")
    out.append(f"total {_duration_text(c['total_duration_s'])}")
    return out


def rank_and_sort(items: List[dict], sort: str = "priority") -> List[dict]:
    """Adds priority_rank (1 = look first) and priority_reasons to every case and returns them in the requested order:
    "priority" or "latest" (newest activity first, the order before G-P1). The rank is the same in both orders."""
    if sort not in SORTS:
        raise ValueError(f"sort must be one of {SORTS}")
    by_priority = sorted(items, key=priority_key, reverse=True)
    for i, c in enumerate(by_priority, 1):
        c["priority_rank"] = i
        c["priority_reasons"] = priority_reasons(c)
    if sort == "priority":
        return by_priority
    return sorted(items, key=lambda c: _ts(c["last_start_ts"]), reverse=True)


def find_case(groups: List[List[dict]], event_id: str) -> Optional[List[dict]]:
    """The case that contains this event (normally its first event)."""
    for g in groups:
        if any(e["event_id"] == event_id for e in g):
            return g
    return None
