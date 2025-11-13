# c:/Users/Vashi/eco-guardian/backend/models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class SmartBin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(100), nullable=False)
    fill_level = db.Column(db.Float, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'location': self.location,
            'fill_level': self.fill_level,
            'last_updated': self.last_updated.isoformat() if self.last_updated else None
        }

class LitterAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    location = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float, default=0)
    image_url = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'location': self.location,
            'confidence': self.confidence,
            'image_url': self.image_url,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }