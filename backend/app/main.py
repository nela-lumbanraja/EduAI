"""EduAI backend (FastAPI).

Run (from the backend folder):   uvicorn app.main:app --reload --port 8000
"""
import asyncio
import contextlib
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import cases as casing
from . import store, summary
from .ai_service import AIManager
from .api import router
from .db import Database
from .livekit_service import WorkerManager
from .security import LoginLimiter
from .seed import seed_demo
from .settings import load_settings

log = logging.getLogger("eduai")
MAINTENANCE_EVERY_S = 30
PURGE_EVERY_S = 600


async def _maintenance(app: FastAPI):
    tick = 0
    while True:
        await asyncio.sleep(MAINTENANCE_EVERY_S)
        tick += MAINTENANCE_EVERY_S
        try:
            await app.state.ai.reap_idle()
            await asyncio.to_thread(_check_summaries, app)
            if tick % PURGE_EVERY_S == 0:
                await asyncio.to_thread(store.purge_expired_evidence, app.state.db, app.state.evidence_store)
        except Exception:                                   # keep the loop alive; never log frame data
            log.exception("maintenance task failed")


def _check_summaries(app: FastAPI):
    """Server-side trigger for the consolidated exam summary (idempotent; see app/summary.py)."""
    for exam_id, kind in summary.check_all(app.state.db, tz_name=app.state.settings.exam_timezone):
        store.audit(app.state.db, None, f"Ringkasan indikasi dibuat ({kind})", f"exam:{exam_id}")


def create_app(settings=None, perception_factory=None) -> FastAPI:
    settings = settings or load_settings()

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        from eduai_ai.evidence import EvidenceStore
        db = Database(settings.db_path)
        if settings.seed_demo and seed_demo(db):
            log.warning("Seeded DEMO accounts (password 123456). Set EDUAI_SEED_DEMO=false for real deployments.")
        app.state.settings = settings
        app.state.db = db
        app.state.limiter = LoginLimiter()
        app.state.evidence_store = EvidenceStore(settings.evidence_dir, settings.evidence_retention_hours,
                                                 settings.evidence_key or None)
        app.state.workers = WorkerManager(settings)
        app.state.ai = AIManager(settings, db, app.state.evidence_store)
        await asyncio.to_thread(app.state.ai.init, perception_factory)
        for n in settings.notes:
            log.warning(n)
        log.info("AI available=%s %s", app.state.ai.available, app.state.ai.reason)
        db.run("UPDATE exams SET monitoring_active=0")      # worker processes do not survive a restart
        for r in db.all("SELECT DISTINCT exam_id FROM events WHERE source='livekit' AND status='open'"):
            store.close_open_events(db, r["exam_id"], "livekit", " (backend dimulai ulang)")
        store.purge_expired_evidence(db, app.state.evidence_store)
        casing.configure_rules((app.state.ai.cfg or {}).get("summary_rules"))
        try:
            _check_summaries(app)                        # summaries that fell due while the backend was down
        except Exception:
            log.exception("summary check failed")
        task = asyncio.create_task(_maintenance(app))
        try:
            yield
        finally:
            task.cancel()
            await asyncio.to_thread(app.state.workers.stop_all)
            await app.state.ai.shutdown()
            db.close()

    app = FastAPI(title="EduAI API", version="0.2.0", lifespan=lifespan,
                  description="Online exam monitoring: AI gives indications only; supervisors decide.")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH"], allow_headers=["Authorization", "Content-Type"])
    app.include_router(router)
    return app


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
app = create_app()
