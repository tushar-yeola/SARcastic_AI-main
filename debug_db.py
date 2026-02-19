
from backend.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    print("Connected to:", engine.url)
    try:
        result = conn.execute(text("SELECT count(*) FROM users")).scalar()
        print(f"Users count: {result}")
    except Exception as e:
        print(f"Error: {e}")
