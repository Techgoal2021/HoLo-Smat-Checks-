from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from datetime import datetime
from models.database import Base


class Vote(Base):
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    hotel_id = Column(Integer, ForeignKey("hotels.id"), nullable=False)
    phone = Column(String(20), nullable=False)
    power_ok = Column(Boolean, nullable=True)
    wifi_ok = Column(Boolean, nullable=True)
    quiet_ok = Column(Boolean, nullable=True)
    vote_type = Column(String(20), default="POST_STAY")  # POST_STAY or REALTIME
    airtime_sent = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "hotel_id": self.hotel_id,
            "vote_type": self.vote_type,
            "power_ok": self.power_ok,
            "created_at": self.created_at.isoformat(),
        }
