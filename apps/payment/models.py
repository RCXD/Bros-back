from datetime import datetime

from sqlalchemy import func, Enum

from apps.config.server import db


class Order(db.Model):
    """Persistent order record tracking a KakaoPay payment lifecycle."""

    __tablename__ = "orders"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True
    )
    item_id = db.Column(
        db.Integer, db.ForeignKey("cosmetic_item.item_id"), nullable=False
    )
    quantity = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(
        Enum(
            "PENDING",  # 사용자가 구매 버튼 눌렀지만 TID 미발급
            "READY",  # 결제 페이지 준비됨 (tid 발급됨)
            "IN_PROGRESS",  # 사용자가 카카오페이 결제 진행 중
            "SUCCESS",  # 결제 승인 완료
            "FAILED",  # 결제 실패
            "CANCELLED",  # 사용자가 결제 취소
            name="order_status",
        ),
        nullable=False,
        default="PENDING",
        index=True,
    )
    total_amount = db.Column(db.Integer, nullable=False, default=0)
    tid = db.Column(db.String(255))
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.now, server_default=func.now()
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.now,
        server_default=func.now(),
        onupdate=func.now(),
    )

    user = db.relationship(
        "User", backref=db.backref("orders", lazy="dynamic"), lazy="joined"
    )
    item = db.relationship("CosmeticItem", lazy="joined", viewonly=True)


class PaymentLog(db.Model):
    """Immutable audit log of every KakaoPay transaction event for an order."""

    __tablename__ = "payment_logs"

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(64), nullable=False)
    order_ref_id = db.Column(
        db.Integer, db.ForeignKey("orders.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True
    )
    tid = db.Column(db.String(255))
    event = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50))
    payload = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.now, server_default=func.now()
    )

    order = db.relationship(
        "Order",
        foreign_keys=[order_ref_id],
        backref=db.backref("payment_logs", lazy="dynamic"),
    )
