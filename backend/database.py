from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from .core.config import settings

# Create sync engine for now, but with pooling
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
