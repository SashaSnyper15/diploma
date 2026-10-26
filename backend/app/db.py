import os

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "moderation.db")
DATABASE_URL = f"sqlite:///{_db_path}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

