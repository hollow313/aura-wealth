import os
from sqlalchemy import create_engine, text

# On récupère l'URL de ta base
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/aura_db")
engine = create_engine(DATABASE_URL)

def migrate():
    print("🚀 Début de la mise à jour de la base de données...")
    
    # Liste des commandes SQL pour ajouter les colonnes manquantes
    commands = [
        # Table user_profiles
        "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS token_limit INTEGER DEFAULT 100000;",
        "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS token_used INTEGER DEFAULT 0;",
        "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS notify_discord BOOLEAN DEFAULT FALSE;",
        "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS discord_webhook TEXT;",
        
        # Table records
        "ALTER TABLE records ADD COLUMN IF NOT EXISTS dividends FLOAT DEFAULT 0.0;",
        "ALTER TABLE records ADD COLUMN IF NOT EXISTS fees FLOAT DEFAULT 0.0;"
    ]
    
    with engine.connect() as conn:
        for cmd in commands:
            try:
                conn.execute(text(cmd))
                conn.commit()
                print(f"✅ Exécuté : {cmd[:40]}...")
            except Exception as e:
                print(f"⚠️ Erreur sur {cmd[:40]} : {e}")
                
    print("✨ Base de données mise à jour avec succès !")

if __name__ == "__main__":
    migrate()
