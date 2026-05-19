from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime
from models.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=True)
    session_state = Column(String(50), default="IDLE")
    # States: IDLE, SEARCHING, AWAITING_SELECTION, AWAITING_PAYMENT, BOOKED, POST_STAY
    last_query = Column(String(500), nullable=True)
    selected_hotel_id = Column(Integer, nullable=True)
    last_results = Column(String(200), nullable=True)       # Comma-separated hotel IDs from last search
    booking_reference = Column(String(100), nullable=True)
    otp = Column(String(6), nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    last_active = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "phone": self.phone,
            "name": self.name,
            "session_state": self.session_state,
            "last_query": self.last_query,
            "selected_hotel_id": self.selected_hotel_id,
            "booking_reference": self.booking_reference,
        }
