from datetime import datetime
from decimal import Decimal
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Product(db.Model):
  __tablename__ = 'products'
  
  id = db.Column(db.Integer, primary_key=True)
  name = db.Column(db.String(100), nullable=False)
  description = db.Column(db.Text, default='')
  price = db.Column(db.Numeric(10, 2), nullable=False)
  stock = db.Column(db.Integer, default=0)
  is_active = db.Column(db.Boolean, default=True)
  created_at = db.Column(db.DateTime, default=datetime.now)
  updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
  
  def __init__(self, name, price, description='', stock=0, is_active=True):
    self.name = name
    self.description = description
    self.price = Decimal(str(price))
    self.stock = stock
    self.is_active = is_active
  
  def __str__(self):
    return self.name
  
  def update(self):
    self.updated_at = datetime.now()