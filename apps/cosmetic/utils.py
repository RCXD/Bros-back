"""
Shared helper utilities used across the cosmetics Blueprint.
"""
from datetime import datetime

from flask import jsonify
from flask_jwt_extended import get_jwt_identity

from apps.auth.models import AccountType, User
from apps.config.server import db
from apps.cosmetic.models import (
    CosmeticItem,
    CosmeticSet,
    CosmeticSetItem,
    UserCosmeticState,
    UserItem,
)

def _is_admin(user_id):
    u = User.query.filter_by(user_id=user_id).first()
    return bool(u and u.account_type == AccountType.ADMIN)

def _item_to_dict(item: CosmeticItem):
    return {
        "item_id": item.item_id,
        "type": item.type.value if item.type else None,
        "name": item.name,
        "price": item.price,
        "rarity": item.rarity,
        "image_path": item.image_path,
        "theme_color": item.theme_color,
        "description": item.description,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _set_to_dict(s: CosmeticSet, include_items=False):
    payload = {
        "set_id": s.set_id,
        "name": s.name,
        "price": s.price,
        "description": s.description,
        "preview_img": s.preview_img,
        "created_at": s.created_at.isoformat() if s.created_at else None,
        "updated_at": s.updated_at.isoformat() if s.updated_at else None,
    }
    if include_items:
        item_ids = [
            row.item_id
            for row in CosmeticSetItem.query.with_entities(CosmeticSetItem.item_id)
            .filter_by(set_id=s.set_id)
            .all()
        ]
        payload["items"] = item_ids
    return payload


def _get_or_create_user_state(uid):
    st = UserCosmeticState.query.filter_by(user_id=uid).first()
    if not st:
        st = UserCosmeticState(user_id=uid, last_updated=datetime.now())
        db.session.add(st)
        db.session.commit()
    return st


def _validate_ownership(uid, item_id, required_type=None):
    if item_id is None:
        return True, None
    itm = CosmeticItem.query.get(item_id)
    if not itm:
        return False, "invalid_item"
    if required_type and itm.type != required_type:
        return False, "type_mismatch"
    if not UserItem.query.filter_by(user_id=uid, item_id=item_id).first():
        return False, "not_owned"
    return True, None
