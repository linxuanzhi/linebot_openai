from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy import create_engine

Base = declarative_base()

class UserSettings(Base):
    __tablename__ = 'user_settings'
    user_id = Column(Integer, primary_key=True)
    stock_id = Column(String, default='2330')
    data_length = Column(Integer, default=180) # 預設180天

class Portfolio(Base):
    __tablename__ = 'portfolio'
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer)
    slot = Column(Integer) # 1, 2, 3, 4, 5
    stock_id = Column(String)
    entry_price = Column(Float)
    shares = Column(Integer)

engine = create_engine('sqlite:///taiwan_stock_bot.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def get_session():
    return Session()
