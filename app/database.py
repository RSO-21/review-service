from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from app.config import settings
from contextlib import contextmanager

DATABASE_URL = (
    f"postgresql://{settings.pg_user}:{settings.pg_password}"
    f"@{settings.pg_host}:{settings.pg_port}/{settings.pg_database}"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

@contextmanager
def get_db_session(schema: str = None):
    session = SessionLocal()
    try:
        session.execute(text(f"SET search_path TO {schema}"))
        yield session
    finally:
        session.close()
