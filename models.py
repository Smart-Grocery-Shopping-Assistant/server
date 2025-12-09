from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import date

Base = declarative_base()

class ItemList(Base):
    __tablename__ = "item_lists"
    id = Column(Integer, primary_key=True)
    created_at = Column(Date, default=date.today)

    items = relationship("Item", back_populates="list", cascade="all, delete")

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    list_id = Column(Integer, ForeignKey("item_lists.id"))
    name = Column(String)
    qty = Column(String)
    expiry = Column(String)

    list = relationship("ItemList", back_populates="items")

engine = create_engine("sqlite:///grocery.db", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base.metadata.create_all(engine)