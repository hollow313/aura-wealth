from sqlalchemy import create_engine, Column, Integer, Float, String, Date, ForeignKey
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:ton_mot_de_passe_robuste@localhost:5432/aura_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class GlobalSettings(Base):
    __tablename__ = 'settings'
    id = Column(Integer, primary_key=True)
    max_daily_tokens = Column(Integer, default=100000)
    chf_eur_rate = Column(Float, default=1.03)

class TokenUsage(Base):
    __tablename__ = 'token_usage'
    id = Column(Integer, primary_key=True)
    date = Column(Date, unique=True)
    tokens_used = Column(Integer, default=0)

class Account(Base):
    __tablename__ = 'accounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True)
    bank_name = Column(String)
    account_type = Column(String)
    currency = Column(String)
    
    # Lien avec l'historique
    records = relationship("Record", back_populates="account", cascade="all, delete-orphan")

# --- LA TABLE MANQUANTE ---
class Record(Base):
    __tablename__ = 'records'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'))
    date_releve = Column(Date)
    total_value = Column(Float)
    
    account = relationship("Account", back_populates="records")

# Cette ligne demande à SQLAlchemy de créer les tables automatiquement si elles n'existent pas
Base.metadata.create_all(bind=engine)
