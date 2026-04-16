import os
from sqlalchemy import create_engine, text
from database import Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/aura_db")
engine = create_engine(DATABASE_URL)

def migrate():
    Base.metadata.create_all(bind=engine)

if __name__ == "__main__":
    migrate()
