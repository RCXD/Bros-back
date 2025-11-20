"""
Cosmetic API - Items, Sets, User inventory/state, and uploads
"""

import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from functools import wraps

from apps.config.server import db
from apps.cosmetic.models import (
    CosmeticItem,
    CosmeticSet,
    CosmeticSetItem,
    UserItem,
    UserCosmeticState,
    ItemType,
)
from apps.cosmetic.utils import (
    _get_or_create_user_state,
    _item_to_dict,
    _set_to_dict,
    _validate_ownership,
)
from apps.admin.views import admin_required

bp = Blueprint("cosmetic", __name__)


DEFAULT_PER_PAGE = 50
MAX_PER_PAGE = 200


def _pagination_meta(pagination):
    return {
        "page": pagination.page,
        "per_page": pagination.per_page,
        "total": pagination.total,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def _get_pagination_params(
    default_per_page=DEFAULT_PER_PAGE, max_per_page=MAX_PER_PAGE
):
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", default_per_page))
    except (TypeError, ValueError):
        return None, None, (jsonify({"error": "invalid_pagination_parameters"}), 400)
    if page < 1:
        return None, None, (jsonify({"error": "page must be >= 1"}), 400)
    if per_page < 1:
        return None, None, (jsonify({"error": "per_page must be >= 1"}), 400)
    per_page = min(per_page, max_per_page)
    return page, per_page, None


def _paginate_query(
    query, default_per_page=DEFAULT_PER_PAGE, max_per_page=MAX_PER_PAGE
):
    page, per_page, err = _get_pagination_params(default_per_page, max_per_page)
    if err:
        return None, err
    return query.paginate(page=page, per_page=per_page, error_out=False), None


# ---- Items (Admin) ----


@bp.post("/items")
@jwt_required()
def create_item():
    data = request.get_json(silent=True) or {}
    try:
        itype = data.get("type")
        if itype is None:
            return jsonify({"error": "type is required"}), 400
        try:
            itype = ItemType(itype)
        except Exception:
            return jsonify({"error": "invalid type"}), 400
        item = CosmeticItem(
            type=itype,
            name=(data.get("name") or "").strip(),
            price=int(data.get("price") or 0),
            rarity=(data.get("rarity") or None),
            image_path=(data.get("image_path") or None),
            theme_color=(data.get("theme_color") or None),
            description=(data.get("description") or None),
        )
        if not item.name:
            return jsonify({"error": "name is required"}), 400
        db.session.add(item)
        db.session.commit()
        return jsonify({"item": _item_to_dict(item)}), 201
    except (ValueError, SQLAlchemyError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.get("/items")
@jwt_required()
def list_items():
    q = CosmeticItem.query
    itype = request.args.get("type")
    if itype:
        try:
            q = q.filter_by(type=ItemType(itype))
        except Exception:
            return jsonify({"error": "invalid type"}), 400
    q = q.order_by(CosmeticItem.created_at.desc())
    pagination, err = _paginate_query(q)
    if err:
        return err
    items = pagination.items
    return (
        jsonify(
            {
                "items": [_item_to_dict(i) for i in items],
                "pagination": _pagination_meta(pagination),
            }
        ),
        200,
    )


@bp.get("/items/<int:item_id>")
@jwt_required()
def get_item(item_id):
    i = CosmeticItem.query.get(item_id)
    if not i:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"item": _item_to_dict(i)}), 200


@bp.put("/items/<int:item_id>")
@jwt_required()
def update_item(item_id):
    error = admin_required()
    if error:
        return error
    i = CosmeticItem.query.get(item_id)
    if not i:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        if "type" in data:
            try:
                i.type = ItemType(data.get("type"))
            except Exception:
                return jsonify({"error": "invalid type"}), 400
        if "name" in data:
            name = (data.get("name") or "").strip()
            if not name:
                return jsonify({"error": "name cannot be empty"}), 400
            i.name = name
        if "price" in data:
            i.price = int(data.get("price") or 0)
        for key in ("rarity", "image_path", "theme_color", "description"):
            if key in data:
                setattr(i, key, data.get(key))
        db.session.commit()
        return jsonify({"item": _item_to_dict(i)}), 200
    except (ValueError, SQLAlchemyError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.delete("/items/<int:item_id>")
@jwt_required()
def delete_item(item_id):
    error = admin_required()
    if error:
        return error
    i = CosmeticItem.query.get(item_id)
    if not i:
        return jsonify({"error": "not_found"}), 404
    try:
        db.session.delete(i)
        db.session.commit()
        return jsonify({"message": "deleted"}), 200
    except IntegrityError as exc:
        db.session.rollback()
        return jsonify({"error": "in_use", "detail": str(exc)}), 409
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


# ---- Sets (Admin) ----


@bp.post("/sets")
@jwt_required()
def create_set():
    error = admin_required()
    if error:
        return error
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400
    price = int(data.get("price") or 0)
    try:
        s = CosmeticSet(
            name=name,
            price=price,
            description=data.get("description"),
            preview_img=data.get("preview_img"),
        )
        db.session.add(s)
        db.session.flush()

        item_ids = data.get("items") or []
        for iid in item_ids:
            db.session.add(CosmeticSetItem(set_id=s.set_id, item_id=int(iid)))
        db.session.commit()
        return jsonify({"set": _set_to_dict(s, include_items=True)}), 201
    except (ValueError, SQLAlchemyError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.get("/sets")
@jwt_required()
def list_sets():
    q = CosmeticSet.query.order_by(CosmeticSet.created_at.desc())
    pagination, err = _paginate_query(q)
    if err:
        return err
    sets = pagination.items
    return (
        jsonify(
            {
                "sets": [_set_to_dict(s) for s in sets],
                "pagination": _pagination_meta(pagination),
            }
        ),
        200,
    )


@bp.get("/sets/<int:set_id>")
@jwt_required()
def get_set(set_id):
    s = CosmeticSet.query.get(set_id)
    if not s:
        return jsonify({"error": "not_found"}), 404
    return jsonify({"set": _set_to_dict(s, include_items=True)}), 200


@bp.put("/sets/<int:set_id>")
@jwt_required()
def update_set(set_id):
    error = admin_required()
    if error:
        return error
    s = CosmeticSet.query.get(set_id)
    if not s:
        return jsonify({"error": "not_found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        if "name" in data:
            name = (data.get("name") or "").strip()
            if not name:
                return jsonify({"error": "name cannot be empty"}), 400
            s.name = name
        if "price" in data:
            s.price = int(data.get("price") or 0)
        for key in ("description", "preview_img"):
            if key in data:
                setattr(s, key, data.get(key))

        if "items" in data:
            # Replace composition
            CosmeticSetItem.query.filter_by(set_id=s.set_id).delete()
            for iid in data.get("items") or []:
                db.session.add(CosmeticSetItem(set_id=s.set_id, item_id=int(iid)))

        db.session.commit()
        return jsonify({"set": _set_to_dict(s, include_items=True)}), 200
    except (ValueError, SQLAlchemyError) as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.delete("/sets/<int:set_id>")
@jwt_required()
def delete_set(set_id):
    error = admin_required()
    if error:
        return error
    s = CosmeticSet.query.get(set_id)
    if not s:
        return jsonify({"error": "not_found"}), 404
    try:
        CosmeticSetItem.query.filter_by(set_id=set_id).delete()
        db.session.delete(s)
        db.session.commit()
        return jsonify({"message": "deleted"}), 200
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.get("/sets/<int:set_id>/items")
@jwt_required()
def list_set_items(set_id):
    s = CosmeticSet.query.get(set_id)
    if not s:
        return jsonify({"error": "not_found"}), 404
    q = (
        CosmeticItem.query.join(
            CosmeticSetItem,
            CosmeticItem.item_id == CosmeticSetItem.item_id,
        )
        .filter(CosmeticSetItem.set_id == set_id)
        .order_by(CosmeticSetItem.item_id)
    )
    pagination, err = _paginate_query(q)
    if err:
        return err
    items = pagination.items
    return (
        jsonify(
            {
                "items": [_item_to_dict(i) for i in items],
                "pagination": _pagination_meta(pagination),
            }
        ),
        200,
    )


# ---- User Inventory ----


@bp.get("/user/items")
@jwt_required()
def list_user_items():
    uid = get_jwt_identity()
    rows_query = UserItem.query.filter_by(user_id=uid).order_by(
        UserItem.acquired_at.desc()
    )
    pagination, err = _paginate_query(rows_query)
    if err:
        return err
    rows = pagination.items
    item_ids = [r.item_id for r in rows]
    items = []
    if item_ids:
        items = CosmeticItem.query.filter(CosmeticItem.item_id.in_(item_ids)).all()
    by_id = {i.item_id: _item_to_dict(i) for i in items}
    payload = [
        {
            "user_item_id": r.user_item_id,
            "acquired_at": r.acquired_at.isoformat() if r.acquired_at else None,
            "is_equipped": r.is_equipped,
            "item": by_id.get(r.item_id),
        }
        for r in rows
    ]
    return (
        jsonify(
            {
                "items": payload,
                "pagination": _pagination_meta(pagination),
            }
        ),
        200,
    )


@bp.post("/user/items/acquire")
@jwt_required()
def acquire_item():
    uid = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    try:
        item_id = int(data.get("item_id"))
    except Exception:
        return jsonify({"error": "item_id required"}), 400
    if not CosmeticItem.query.get(item_id):
        return jsonify({"error": "invalid_item"}), 404
    try:
        ui = UserItem(user_id=uid, item_id=item_id, acquired_at=datetime.now())
        db.session.add(ui)
        db.session.commit()
        return jsonify({"user_item_id": ui.user_item_id}), 201
    except IntegrityError:
        db.session.rollback()
        # already owned
        ui = UserItem.query.filter_by(user_id=uid, item_id=item_id).first()
        return (
            jsonify({"user_item_id": ui.user_item_id, "message": "already_owned"}),
            200,
        )
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.post("/user/sets/acquire")
@jwt_required()
def acquire_set():
    uid = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    try:
        set_id = int(data.get("set_id"))
    except Exception:
        return jsonify({"error": "set_id required"}), 400
    s = CosmeticSet.query.get(set_id)
    if not s:
        return jsonify({"error": "invalid_set"}), 404
    rel = CosmeticSetItem.query.filter_by(set_id=set_id).all()
    item_ids = [r.item_id for r in rel]
    created, existing = [], []
    try:
        for iid in item_ids:
            try:
                ui = UserItem(user_id=uid, item_id=iid, acquired_at=datetime.now())
                db.session.add(ui)
                db.session.flush()
                created.append(iid)
            except IntegrityError:
                db.session.rollback()
                existing.append(iid)
        db.session.commit()
        return jsonify({"acquired": created, "existing": existing}), 200
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


# ---- User Cosmetic State ----


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


@bp.get("/user/state")
@jwt_required()
def get_user_state():
    uid = get_jwt_identity()
    st = _get_or_create_user_state(uid)
    return (
        jsonify(
            {
                "user_id": st.user_id,
                "border_item_id": st.border_item_id,
                "overlay_item_id": st.overlay_item_id,
                "theme_item_id": st.theme_item_id,
                "font_item_id": st.font_item_id,
                "effect_item_id": st.effect_item_id,
                "last_updated": (
                    st.last_updated.isoformat() if st.last_updated else None
                ),
            }
        ),
        200,
    )


@bp.put("/user/state")
@jwt_required()
def update_user_state():
    uid = get_jwt_identity()
    st = _get_or_create_user_state(uid)

    data = request.get_json(silent=True)
    if data is None:
        data = request.form.to_dict(flat=True)

    def _parse_int(v):
        if v in (None, "", "null", "None"):
            return None
        return int(v)

    updates = {
        "border_item_id": _parse_int(data.get("border_item_id")),
        "overlay_item_id": _parse_int(data.get("overlay_item_id")),
        "theme_item_id": _parse_int(data.get("theme_item_id")),
        "font_item_id": _parse_int(data.get("font_item_id")),
        "effect_item_id": _parse_int(data.get("effect_item_id")),
    }

    validations = [
        ("border_item_id", ItemType.border),
        ("overlay_item_id", ItemType.overlay),
        ("theme_item_id", ItemType.theme),
        ("font_item_id", ItemType.font),
        ("effect_item_id", ItemType.effect),
    ]
    for field, req_type in validations:
        ok, reason = _validate_ownership(uid, updates[field], req_type)
        if not ok:
            return jsonify({"error": reason, "field": field}), 400

    try:
        for k, v in updates.items():
            setattr(st, k, v)
        st.last_updated = datetime.now()
        db.session.commit()
        return jsonify({"message": "updated"}), 200
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


# ---- Uploads ----


@bp.post("/upload")
@jwt_required()
def upload_overlay():
    # optional admin-only; for now allow authenticated
    if "file" not in request.files:
        return jsonify({"error": "file missing"}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "empty filename"}), 400
    fname = secure_filename(f.filename)
    subdir = request.form.get("subdir") or "cosmetic_overlays"
    base = current_app.static_folder or os.path.join(current_app.root_path, "static")
    target_dir = os.path.join(base, subdir)
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, fname)
    f.save(path)
    rel = os.path.relpath(path, base).replace("\\", "/")
    static_url_path = current_app.static_url_path or "/static"
    url = f"{static_url_path.rstrip('/')}/{rel.lstrip('/')}"
    return jsonify({"path": rel, "url": url}), 201
