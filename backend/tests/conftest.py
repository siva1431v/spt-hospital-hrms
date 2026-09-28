"""
Pytest configuration for SPT Hospital HRMS test suite.
Provides an isolated temporary SQLite database for all tests and safety guards
to ensure tests NEVER touch or write to the live/production spt_hrms.db.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shutil
import asyncio
import pytest
from sqlalchemy import event, text

# ── 1. Create a dedicated temporary database before importing app modules ──
_test_dir = tempfile.mkdtemp(prefix="spt_hrms_test_")
_test_db_path = os.path.join(_test_dir, "test.db")
_test_db_url = f"sqlite+aiosqlite:///{_test_db_path}"
_test_sync_db_url = f"sqlite:///{_test_db_path}"

os.environ["DATABASE_URL"] = _test_db_url
os.environ["SYNC_DATABASE_URL"] = _test_sync_db_url

# Override settings
from app.core.config import settings
settings.DATABASE_URL = _test_db_url
settings.SYNC_DATABASE_URL = _test_sync_db_url

# Safety guard 1: Check settings URL immediately
if "spt_hrms.db" in str(settings.DATABASE_URL):
    sys.exit("CRITICAL: Test suite is attempting to connect to production database spt_hrms.db! Aborting.")

# ── 2. Configure app.core.database engine to use test DB ──
import app.core.database as db_mod
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

db_mod.engine = create_async_engine(_test_db_url, echo=False)
db_mod.AsyncSessionLocal = async_sessionmaker(
    db_mod.engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Safety guard 2: Check engine URL immediately
if "spt_hrms.db" in str(db_mod.engine.url):
    sys.exit("CRITICAL: Engine URL contains spt_hrms.db! Aborting.")


# Safety guard 3: Event listener ensuring no connection opens spt_hrms.db
@event.listens_for(db_mod.engine.sync_engine, "connect")
def _guard_db_connection(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA database_list")
    for row in cursor.fetchall():
        db_file = row[2] or ""
        if "spt_hrms.db" in db_file and "test" not in db_file:
            raise RuntimeError(f"CRITICAL SAFETY VIOLATION: Connected to production database {db_file}!")


def pytest_sessionstart(session):
    """Safety guard checked at pytest session startup."""
    if "spt_hrms.db" in str(settings.DATABASE_URL) or "spt_hrms.db" in str(db_mod.engine.url):
        pytest.exit("CRITICAL: Resolved DATABASE_URL contains spt_hrms.db! Aborting test session.", returncode=1)


@pytest.fixture(scope="session", autouse=True)
def setup_test_database():
    """
    Session-wide fixture that creates all tables and seeds core test data
    (admin user, HR user, departments, shifts, designations, 66 employees, settings).
    """
    if "spt_hrms.db" in str(settings.DATABASE_URL) or "spt_hrms.db" in str(db_mod.engine.url):
        pytest.exit("CRITICAL: Test suite is attempting to connect to production database spt_hrms.db! Aborting.", returncode=1)

    backup_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spt_hrms.backup-before-fixes.db")
    if not os.path.exists(backup_path):
        backup_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "spt_hrms.db")

    if os.path.exists(backup_path):
        shutil.copyfile(backup_path, _test_db_path)
    else:
        from app.core.database import Base
        from scripts.init_db import init_database

        async def _init():
            async with db_mod.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await init_database()

        asyncio.run(_init())

    yield _test_db_path

    # Cleanup temp directory after test session
    try:
        shutil.rmtree(_test_dir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def test_db_path():
    """Provide the absolute path to the isolated test database file."""
    return _test_db_path


@pytest.fixture
async def client():
    """In-process async HTTP client for FastAPI."""
    import httpx
    from app.main import app
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
