"""Сбрасывает БД к первоначальному виду: пустые таблицы + demo-проект."""

from .db import Base, engine
from .main import create_default_project_if_missing


def reset_db() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    create_default_project_if_missing()


if __name__ == "__main__":
    reset_db()
    print("БД сброшена: остался только demo-проект (api_key: demo-api-key-123).")
