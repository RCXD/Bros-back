"""
상품 모델
"""
from datetime import datetime
from decimal import Decimal
from apps.config.server import db


class Product(db.Model):
    """상품 모델"""
    __tablename__ = 'products'
    
    product_id = db.Column(db.Integer, primary_key=True)
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
    
    def __repr__(self):
        return f'<Product {self.product_id}: {self.name}>'
    
    def update(self):
        """업데이트 시각 갱신"""
        self.updated_at = datetime.now()