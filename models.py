from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker


Base = declarative_base()


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String)
    qty = Column(Integer)
    expiry = Column(String)


engine = create_engine("sqlite:///grocery.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)