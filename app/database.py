from sqlalchemy import create_engine, Column, Integer, Float, String, Date
from sqlalchemy.orm import declarative_base, sessionmaker
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost/aura_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class GlobalSettings(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True)
    max_daily_tokens = Column(Integer, default=100000) # Ex: 100k, donc bloqué à 70k

class TokenUsage(Base):
    __tablename__ = 'token_usage'
    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True)
    tokens_used = Column(Integer, default=0)

class Account(Base):
    __tablename__ = 'accounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True) # Ex: "loic" (venant d'Authelia)
    bank_name = Column(String)
    account_type = Column(String)
    currency = Column(String)
    total_value = Column(Float)
