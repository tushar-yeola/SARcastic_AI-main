import streamlit as st
from database.db import engine
from sqlalchemy import text
from passlib.hash import bcrypt


def authenticate(username, password):
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT * FROM users WHERE username=:u"),
            {"u": username}
        ).fetchone()

        if result and bcrypt.verify(password, result.password):
            return result

    return None
