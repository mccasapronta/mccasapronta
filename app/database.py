
from sqlalchemy import create_engine, Integer, String, Float, DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from datetime import datetime

engine = create_engine("sqlite:///./data.db", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

class Base(DeclarativeBase):
    pass

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str] = mapped_column(String(50))
    address: Mapped[str] = mapped_column(String(300))
    # Client GPS (optional, via browser geolocation)
    client_lat: Mapped[float] = mapped_column(Float, default=0.0)
    client_lng: Mapped[float] = mapped_column(Float, default=0.0)
    # Travel calculation
    distance_km: Mapped[float] = mapped_column(Float, default=0.0)
    travel_cost_eur: Mapped[float] = mapped_column(Float, default=0.0)
    # Pricing (we'll start with travel cost only)
    total_price: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

def init_db():
    Base.metadata.create_all(bind=engine)
