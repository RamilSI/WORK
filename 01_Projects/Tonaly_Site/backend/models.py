from sqlalchemy import Column, Integer, String, Text
from database import Base

class Product(Base):
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String, unique=True, index=True)
    name = Column(String)
    badge = Column(String)
    ptype = Column(String)
    binder = Column(String)
    purpose = Column(String)
    short_desc = Column(String)
    description = Column(Text)
    specs = Column(Text)
    related = Column(String)
