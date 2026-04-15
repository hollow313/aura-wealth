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
    show_chf = Column(Boolean, default=False)
    active_currencies = Column(String, default="EUR") # NOUVEAU : Devises actives (ex: "EUR,CHF,USD")
    token_limit = Column(Integer, default=100000)
    token_used = Column(Integer, default=0)
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

Base.metadata.create_all(bind=engine)
