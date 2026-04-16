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
    active_currencies = Column(String, default="EUR")
    token_limit_weekly = Column(Integer, default=100000)
    token_used_weekly = Column(Integer, default=0)
    token_used_daily = Column(Integer, default=0)
    token_used_global = Column(Integer, default=0)
    last_daily_reset = Column(Date, nullable=True)
    last_weekly_reset = Column(Integer, nullable=True)
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
    is_manual = Column(Boolean, default=False)
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

# --- NOUVELLES TABLES BUDGET (CSV) ---
class BankAccount(Base):
    __tablename__ = 'bank_accounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True)
    bank_name = Column(String)
    account_name = Column(String)
    transactions = relationship("BankTransaction", back_populates="account", cascade="all, delete-orphan")

class BankTransaction(Base):
    __tablename__ = 'bank_transactions'
    id = Column(Integer, primary_key=True)
    account_id = Column(Integer, ForeignKey('bank_accounts.id'))
    date = Column(Date)
    amount = Column(Float)
    label = Column(String)
    balance = Column(Float, nullable=True)
    category = Column(String, default="Autre")
    account = relationship("BankAccount", back_populates="transactions")

class CategoryRule(Base):
    __tablename__ = 'category_rules'
    id = Column(Integer, primary_key=True)
    user_id = Column(String, index=True)
    category_name = Column(String)
    keywords = Column(Text) # Mots-clés séparés par des virgules (ex: "AMAZON, PAYPAL, CDISCOUNT")

Base.metadata.create_all(bind=engine)
