from apps.config.server import db
from datetime import datetime
import enum


class Status(enum.Enum):
    READY = "READY"
    APPROVED = "APPROVED"
    FAILED="FAILED"


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(50), nullable=False)
    user_id = db.Column(db.String(50), nullable=False)
    item_name = db.Column(db.String(100))
    amount = db.Column(db.Integer)
    
    tid = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(20), default=Status.READY)  
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
