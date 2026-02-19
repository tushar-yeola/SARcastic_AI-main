
from backend.database import engine
from sqlalchemy import text
from backend.core.security import verify_password, get_password_hash

def check_user(username, password):
    print(f"Checking user: {username}")
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM users WHERE username = :u"), {"u": username}
        ).fetchone()
        
        if not result:
            print("User NOT found!")
            return

        print(f"User found: {result}")
        # Assuming result is indexable/namedtuple-like
        stored_pw = result.password 
        print(f"Stored hash: {stored_pw}")
        
        is_valid = verify_password(password, stored_pw)
        print(f"Validation result for '{password}': {is_valid}")
        
        # Double check hashing
        new_hash = get_password_hash(password)
        print(f"New hash for '{password}': {new_hash}")
        print(f"Validation of new hash: {verify_password(password, new_hash)}")

if __name__ == "__main__":
    check_user("sarah@sarcastic.ai", "sarah123")
