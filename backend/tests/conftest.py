"""Keep the developer's backend/.env out of the tests.

app/main.py builds a module-level `app = create_app()` for uvicorn. Importing it runs load_settings(), which copies
every KEY=VALUE of backend/.env into os.environ with setdefault. Before this file existed, those values leaked into
every test (e.g. the trial retention EDUAI_EVIDENCE_RETENTION_HOURS=876000 made five retention tests fail), so the
results depended on the local machine.

Here app.main is imported once, before any test module, and every variable that the import ADDED is removed again.
setdefault never overwrites, so variables that were already set in the real environment stay exactly as they were.
The module-level app is not used by the tests and opens no database (the database is opened in its lifespan).
Tests build their own settings with tests.test_api.make_settings (temporary database, evidence and report folders).
"""
import os

_before = set(os.environ)
import app.main  # noqa: E402,F401  (the import that reads backend/.env)

LEAKED_FROM_DOTENV = sorted(set(os.environ) - _before)      # names only; values are never kept or printed
for _name in LEAKED_FROM_DOTENV:
    del os.environ[_name]
