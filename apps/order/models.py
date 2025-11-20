from datetime import datetime

from sqlalchemy import func

from apps.config.server import db


class Order(db.Model):
    """Persistent order record for KakaoPay interaction."""

    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    item_name = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    total_amount = db.Column(db.Integer, nullable=False, default=0)
    tid = db.Column(db.String(255))
    status = db.Column(db.String(50), nullable=False, default="PENDING")
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = db.relationship(
        "User", backref=db.backref("orders", lazy="dynamic"), lazy="joined"
    )


class PaymentLog(db.Model):
    """Store KakaoPay transaction history separately from orders."""

    __tablename__ = "payment_logs"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(64), nullable=False, index=True)
    order_ref_id = db.Column(
        db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True)
    tid = db.Column(db.String(255))
    event = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50))
    payload = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow, server_default=func.now()
    )

    order = db.relationship("Order", backref=db.backref("payment_logs", lazy="dynamic"))
