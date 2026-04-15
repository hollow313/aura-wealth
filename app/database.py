from sqlalchemy import create_engine, Column, Integer, Float, String, Date, ForeignKey, Boolean, Text
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:password@localhost:5432/aura_db")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class UserProfile(Base):
    __tablename__ = 'user_profiles'
    id = Column(Integer, primary_key=True)
    username = Column(String, unique=True, index=True)
    # Paramètres
    active_currencies = Column(String, default="EUR")
    # Quotas et Reset
    token_limit_weekly = Column(Integer, default=100000) # Limite hebdo par user
    token_used_weekly = Column(Integer, default=0)       # Compteur hebdo
    token_used_daily = Column(Integer, default=0)        # Compteur jour (pour l'admin)
    token_used_global = Column(Integer, default=0)       # Compteur à vie
    last_daily_reset = Column(Date, nullable=True)
    last_weekly_reset = Column(Integer, nullable=True)   # Numéro de semaine ISO
    # Divers
    notify_discord = Column(Boolean, default=False)
    discord_webhook = Column(Text, nullable=True)

class Account(Base):
    __tablename__ = 'accounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True)
    bank_name = Column(String)
    account_type = Column(String)
    contract_number = Column(String)
    currency = Column(String, default="EUR")
    total_invested = Column(Float, default=0.0) 
    fiscal_date = Column(Date, nullable=True)
    management_profile = Column(String, nullable=True)
    records = relationship("Record", back_populates="account", cascade="all, delete-orphan")

class Record(Base):
    __tablename__ = 'records'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('accounts.id'))
    date_releve = Column(Date)
    total_value = Column(Float)
    total_invested = Column(Float, default=0.0) 
    total_withdrawn = Column(Float, default=0.0)
    fonds_euro_value = Column(Float, default=0.0)
    uc_value = Column(Float, default=0.0)
    dividends = Column(Float, default=0.0)
    fees = Column(Float, default=0.0)
    account = relationship("Account", back_populates="records")
    positions = relationship("Position", back_populates="record", cascade="all, delete-orphan")

class Position(Base):
    __tablename__ = 'positions'
    id = Column(Integer, primary_key=True)
    record_id = Column(Integer, ForeignKey('records.id'))
    name = Column(String)
    asset_type = Column(String, nullable=True)
    quantity = Column(Float, default=0.0)
    unit_price = Column(Float, default=0.0)
    total_value = Column(Float, default=0.0)
    record = relationship("Record", back_populates="positions")

Base.metadata.create_all(bind=engine)
