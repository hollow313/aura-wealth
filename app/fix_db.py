import os
from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/aura_db")
engine = create_engine(DATABASE_URL)

def migrate():
    print("🚀 Mise à jour vers Aura Pro v2.0...")
    
    commands = [
        # --- TABLE ACCOUNTS ---
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS contract_number VARCHAR;",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS fiscal_date DATE;",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS management_profile VARCHAR;",
        "ALTER TABLE accounts ADD COLUMN IF NOT EXISTS total_invested FLOAT DEFAULT 0.0;",
        
        # --- TABLE RECORDS ---
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
                print(f"✅ OK : {cmd[:50]}...")
            except Exception as e:
                print(f"⚠️ Note : {e}")
                
    print("✨ Base de données synchronisée avec le nouveau Dashboard !")

if __name__ == "__main__":
    migrate()
