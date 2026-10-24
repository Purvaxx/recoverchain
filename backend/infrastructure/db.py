import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Offline-first: default to a local SQLite file so the app runs with zero setup
# and no external services. Point DATABASE_URL at Postgres for a real deployment
# (then run `alembic upgrade head`).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./recoverchain.db")

if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
