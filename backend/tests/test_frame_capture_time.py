"""G-F1 (20 Nov 2026): browser capture time sent with each frame, used as a performance metric only."""
import time

from app.ai_service import capture_lag, frame_timing
from tests.test_api import BASE_T, client, jpeg, login, start_exam_session, uid  # noqa: F401


def test_frame_timing_keeps_plausible_values_only():
    now = 1_795_000_000.0
    t = frame_timing(str(now * 1000 - 150), "12.5", "180", now)
    assert t == {"capture_to_receive": 150.0, "client_encode": 12.5, "client_rtt": 180.0}
    assert frame_timing(None, None, None, now) == {}                               # older browsers: nothing
    assert frame_timing("abc", "nan", "-5", now) == {}                             # garbage, NaN, negative
    assert frame_timing(str(now * 1000 - 2 * 86_400_000), "70000", "999999", now) == {}   # clock days off; too long
    assert frame_timing(str(now * 1000 + 3000), None, None, now) == {"capture_to_receive": -3000.0}   # laptop clock ahead


def test_capture_lag_removes_the_constant_clock_difference():
    lag = capture_lag([5150.0, 5170.0, 5400.0])            # laptop 5 s behind the server, lags 150/170/400 ms
    assert lag["min_raw"] == 5150.0 and lag["above_min"] == {"n": 3, "median": 20.0, "p90": 250.0, "max": 250.0}
    assert capture_lag([]) is None


def post(c, h, t, **fields):
    c.app.state.ai.clock = lambda: BASE_T + t
    return c.post("/api/exams/1/frames", headers=h, files={"frame": ("f.jpg", jpeg(200), "image/jpeg")}, data=fields)


def test_timing_reaches_performance_and_never_rejects_a_frame(client):
    hs, _ = start_exam_session(client)
    for i in range(4):
        r = post(client, hs, i * 0.5, captured_at=str(time.time() * 1000 - 100), client_age_ms="8.5",
                 **({"prev_rtt_ms": "120"} if i else {}))
        assert r.status_code == 202 and r.json()["accepted"] is True
    assert post(client, hs, 2.5, captured_at="bukan-angka", client_age_ms="-1").status_code == 202
    assert post(client, hs, 3.0).status_code == 202                              # an older browser: no fields
    s = client.get("/api/ai/performance", headers=login(client, "admin1@gmail.com")).json()["students"][0]
    assert s["extra_ms"]["client_encode"]["n"] == 4 and s["extra_ms"]["client_rtt"]["n"] == 3
    assert s["extra_ms"]["capture_to_receive"]["n"] == 4
    assert 100 <= s["capture_lag_ms"]["raw"]["median"] < 5000 and s["capture_lag_ms"]["above_min"]["median"] >= 0


def test_analysis_keeps_the_server_clock(client):
    """A wrong laptop clock (here 10 hours behind) changes the lag metric, never the analysis time of events."""
    hs, _ = start_exam_session(client)
    post(client, hs, 7.0, captured_at=str(time.time() * 1000 - 10 * 3600 * 1000))
    entry = client.app.state.ai.entries[(1, uid(client, "siswa1@gmail.com"))]
    assert entry.analyzer.last_frame_ts == BASE_T + 7.0
    assert entry.analyzer.perf.extra_values("capture_to_receive")[0] > 10 * 3600 * 1000 - 5000
