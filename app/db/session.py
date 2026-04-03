# 作者：小红书@人间清醒的李某人

from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
DATABASE_PATH = (DATA_DIR / "patient_agent.db").resolve()
DATABASE_PATH_STR = str(DATABASE_PATH)
if DATABASE_PATH_STR.startswith("\\\\?\\"):
    DATABASE_PATH_STR = DATABASE_PATH_STR[4:]
DATABASE_PATH_STR = DATABASE_PATH_STR.replace("\\", "/")
DATABASE_URL = f"sqlite:///{DATABASE_PATH_STR}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
