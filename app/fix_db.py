import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/aura_db")
engine = create_engine(DATABASE_URL)

def migrate():
    commands = [
        "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS token_limit INTEGER DEFAULT 100000;",
        "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS token_used INTEGER DEFAULT 0;",
        "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS notify_discord BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS discord_webhook TEXT;",
        "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS active_currencies VARCHAR DEFAULT 'EUR';",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS contract_number VARCHAR;",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS fiscal_date DATE;",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS management_profile VARCHAR;",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS total_invested FLOAT DEFAULT 0.0;",
        "ALTER TABLE records ADD COLUMN IF NOT EXISTS total_invested FLOAT DEFAULT 0.0;",
        "ALTER TABLE records ADD COLUMN IF NOT EXISTS total_withdrawn FLOAT DEFAULT 0.0;",
        "ALTER TABLE records ADD COLUMN IF NOT EXISTS fonds_euro_value FLOAT DEFAULT 0.0;",
        "ALTER TABLE records ADD COLUMN IF NOT EXISTS uc_value FLOAT DEFAULT 0.0;",
        "ALTER TABLE records ADD COLUMN IF NOT EXISTS dividends FLOAT DEFAULT 0.0;",
        "ALTER TABLE records ADD COLUMN IF NOT EXISTS fees FLOAT DEFAULT 0.0;"
    ]
    with engine.connect() as conn:
        for cmd in commands:
            try:
                conn.execute(text(cmd))
                conn.commit()
            except: pass

if __name__ == "__main__":
    migrate()
