"""
Cosmetic-related database models
"""

from datetime import datetime
import enum

from apps.config.server import db


class ItemType(enum.Enum):
    border = "border"
    overlay = "overlay"
    theme = "theme"
    font = "font"
    effect = "effect"
    bedge = "badge"
    bundle = "bundle"


class CosmeticItem(db.Model):
    __tablename__ = "cosmetic_item"

    item_id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.Enum(ItemType), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    price = db.Column(db.Integer, nullable=False, default=0)  # store cents
    rarity = db.Column(db.String(32), nullable=True, index=True)
    image_path = db.Column(db.String(255), nullable=True)
    theme_color = db.Column(db.String(32), nullable=True)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class UserItem(db.Model):
    __tablename__ = "user_item"

    user_item_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True
    )
    item_id = db.Column(
        db.Integer, db.ForeignKey("cosmetic_item.item_id"), nullable=False, index=True
    )
    acquired_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_equipped = db.Column(db.Boolean, default=False, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "item_id", name="uq_user_item_once"),
    )


class UserCosmeticState(db.Model):
    __tablename__ = "user_cosmetic_state"

    # Enforce a single row per user via PK on user_id
    user_id = db.Column(db.Integer, db.ForeignKey("users.user_id"), primary_key=True)
    border_item_id = db.Column(
        db.Integer, db.ForeignKey("cosmetic_item.item_id"), nullable=True
    )
    overlay_item_id = db.Column(
        db.Integer, db.ForeignKey("cosmetic_item.item_id"), nullable=True
    )
    theme_item_id = db.Column(
        db.Integer, db.ForeignKey("cosmetic_item.item_id"), nullable=True
    )
    font_item_id = db.Column(
        db.Integer, db.ForeignKey("cosmetic_item.item_id"), nullable=True
    )
    effect_item_id = db.Column(
        db.Integer, db.ForeignKey("cosmetic_item.item_id"), nullable=True
    )
    last_updated = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class CosmeticSet(db.Model):
    __tablename__ = "cosmetic_set"

    set_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    price = db.Column(db.Integer, nullable=False, default=0)  # store cents
    description = db.Column(db.Text, nullable=True)
    preview_img = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class CosmeticSetItem(db.Model):
    __tablename__ = "cosmetic_set_item"

    set_id = db.Column(
        db.Integer, db.ForeignKey("cosmetic_set.set_id"), primary_key=True
    )
    item_id = db.Column(
        db.Integer, db.ForeignKey("cosmetic_item.item_id"), primary_key=True
    )


class CosmeticTag(db.Model):
    __tablename__ = "cosmetic_tag"

    tag_id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False, unique=True, index=True)


class CosmeticItemTag(db.Model):
    __tablename__ = "cosmetic_item_tag"

    tag_id = db.Column(
        db.Integer, db.ForeignKey("cosmetic_tag.tag_id"), primary_key=True
    )
    item_id = db.Column(
        db.Integer, db.ForeignKey("cosmetic_item.item_id"), primary_key=True
    )
