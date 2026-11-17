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
    # rem-color | akzo | weg — поставщик / бренд каталога
    brand = Column(String, default="rem-color", index=True)
    # POX, INTERGARD, INTERZONE … — линейка внутри бренда
    family = Column(String, default="", index=True)
    tds_file = Column(String, default="")
    source_id = Column(String, default="")
    # JSON: notice, name, url, note, rem_slug — блок «протестирован аналог»
    analog_json = Column(Text, default="")


# Схемы покрытий живут в data/coating_schemes.json (удобно править без миграции БД).
# Страницы: /schemes и /schemes/{slug}, загрузка — schemes.py.
