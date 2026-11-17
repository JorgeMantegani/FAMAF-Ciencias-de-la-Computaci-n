"""Migración aditiva para instalaciones existentes; no borra datos."""

from sqlalchemy import DateTime, Engine, inspect, text


def migrate_email_verification(engine: Engine) -> None:
    with engine.begin() as connection:
        inspector = inspect(connection)
        if "users" not in inspector.get_table_names():
            return
        columns = {column["name"] for column in inspector.get_columns("users")}
        if "email_verified_at" not in columns:
            sql_type = DateTime(timezone=True).compile(dialect=engine.dialect)
            connection.execute(
                text(f"ALTER TABLE users ADD COLUMN email_verified_at {sql_type} NULL")
            )
