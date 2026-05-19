from sqlalchemy import Column, Integer, String, Float, Text
from models.database import Base


class Hotel(Base):
    __tablename__ = "hotels"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    area = Column(String(50), nullable=False)          # Yaba, Lekki, VI, Ikeja, Surulere
    address = Column(String(200), nullable=False)
    price_naira = Column(Integer, nullable=False)       # Price per night in Naira
    truth_score = Column(Float, default=50.0)           # 0-100 overall HoLo score
    power_score = Column(Float, default=50.0)           # Electricity reliability 0-100
    wifi_score = Column(Float, default=50.0)            # Wi-Fi quality 0-100
    quiet_score = Column(Float, default=50.0)           # Noise level 0-100
    security_score = Column(Float, default=50.0)        # Security 0-100
    staff_score = Column(Float, default=50.0)           # Staff conduct 0-100
    total_votes = Column(Integer, default=0)
    review_summary = Column(Text, nullable=True)        # AI-generated honest summary
    phone = Column(String(20), nullable=True)           # Hotel contact
    image_url = Column(String(300), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "area": self.area,
            "address": self.address,
            "price_naira": self.price_naira,
            "truth_score": round(self.truth_score, 1),
            "power_score": round(self.power_score, 1),
            "wifi_score": round(self.wifi_score, 1),
            "quiet_score": round(self.quiet_score, 1),
            "security_score": round(self.security_score, 1),
            "staff_score": round(self.staff_score, 1),
            "total_votes": self.total_votes,
            "review_summary": self.review_summary,
            "phone": self.phone,
            "image_url": self.image_url,
        }
