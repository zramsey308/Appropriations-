import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import EligibleAccount

# Shared in-memory SQLite for all API tests.
# StaticPool ensures all connections share the same in-memory database.
test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def db_session():
    """Provide a raw TestSession for tests that need direct DB access."""
    db = TestSession()
    yield db
    db.close()


@pytest.fixture(autouse=True)
def setup_db():
    """Create tables before each test, drop after."""
    Base.metadata.create_all(bind=test_engine)
    db = TestSession()
    if db.query(EligibleAccount).count() == 0:
        db.add(EligibleAccount(
            id=1, subcommittee="transportation_hud",
            agency="Department of Transportation",
            account_name="Transit Infrastructure Grants",
            active=True,
        ))
        db.add(EligibleAccount(
            id=2, subcommittee="agriculture",
            agency="Department of Agriculture",
            account_name="Rural Development",
            active=True,
        ))
        db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=test_engine)
