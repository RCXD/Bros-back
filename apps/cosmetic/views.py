"""
Cosmetic API - Items, Sets, User inventory/state, and uploads
"""

import base64
import os
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from functools import wraps
from apps.user.reward_utils import revoke_points

from apps.config.server import db
from apps.cosmetic.models import (
    CosmeticItem,
    CosmeticSet,
    CosmeticSetItem,
    UserItem,
    ItemType,
)
from apps.cosmetic.utils import (
    _get_or_create_user_state,
    _item_to_dict,
    _set_to_dict,
    _validate_ownership,
)
from apps.admin.views import admin_required

from apps.admin.views import admin_required

bp = Blueprint("cosmetic", __name__)


@bp.get("/api_info")
def api_info():
    """
    코스메틱 API 정보 제공 (개발용)
    """
    info = {
        "module": "cosmetic",
        "base_path": "/cosmetic",
        "description": "사용자 아이템 및 코스메틱 관리",
        "endpoints": [
            {
                "path": "/cosmetic/items",
                "method": "GET",
                "auth_required": False,
                "description": "아이템 목록 조회",
            },
            {
                "path": "/cosmetic/sets",
                "method": "GET",
                "auth_required": False,
                "description": "세트 목록 조회",
            },
            {
                "path": "/cosmetic/user/items",
                "method": "GET",
                "auth_required": True,
                "description": "사용자 소유 아이템 조회",
            },
            {
                "path": "/cosmetic/user/state",
                "method": "GET",
                "auth_required": True,
                "description": "사용자 코스메틱 상태 조회",
            },
            {
                "path": "/cosmetic/user/state",
                "method": "PUT",
                "auth_required": True,
                "description": "사용자 코스메틱 상태 업데이트",
            },
            {
                "path": "/cosmetic/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            },
        ],
    }
    return jsonify(info), 200


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
        return None, None, (jsonify({"message": "invalid_pagination_parameters"}), 400)
    if page < 1:
        return None, None, (jsonify({"message": "page must be >= 1"}), 400)
    if per_page < 1:
        return None, None, (jsonify({"message": "per_page must be >= 1"}), 400)
    per_page = min(per_page, max_per_page)
    return page, per_page, None


def _paginate_query(
    query, default_per_page=DEFAULT_PER_PAGE, max_per_page=MAX_PER_PAGE
):
    page, per_page, err = _get_pagination_params(default_per_page, max_per_page)
    if err:
        return None, err
    return query.paginate(page=page, per_page=per_page, error_out=False), None


def _save_cosmetic_upload(file_storage, subdir=None):
    if not file_storage or not file_storage.filename:
        raise ValueError("file missing")
    fname = secure_filename(file_storage.filename)
    if not fname:
        raise ValueError("invalid filename")
    subdir = subdir or "cosmetic_overlays"
    base = current_app.static_folder or os.path.join(current_app.root_path, "static")
    target_dir = os.path.join(base, subdir)
    os.makedirs(target_dir, exist_ok=True)
    path = os.path.join(target_dir, fname)
    file_storage.save(path)
    rel = os.path.relpath(path, base).replace("\\", "/")
    static_url_path = current_app.static_url_path or "/static"
    url = f"{static_url_path.rstrip('/')}/{rel.lstrip('/')}"
    return rel, url


def _delete_cosmetic_asset(image_path):
    if not image_path:
        return
    base = current_app.static_folder or os.path.join(current_app.root_path, "static")
    base_abs = os.path.abspath(base)
    asset_path = os.path.abspath(os.path.normpath(os.path.join(base_abs, image_path)))
    try:
        if os.path.commonpath([base_abs, asset_path]) != base_abs:
            return
    except ValueError:
        return
    try:
        os.remove(asset_path)
    except FileNotFoundError:
        pass


_VISUAL_ITEM_TYPES = frozenset(
    t
    for t in (
        getattr(ItemType, "overlay", None),
        getattr(ItemType, "border", None),
        getattr(ItemType, "bedge", None),
    )
    if t is not None
)


def _enforce_visual_asset_requirement(item_type, image_path):
    if item_type not in _VISUAL_ITEM_TYPES:
        return
    if image_path and image_path.strip():
        return
    raise ValueError(f"{item_type.value} items require an image or svg asset")


# ---- Items (Admin) ----

@bp.post("/items")
@jwt_required()
def create_item():
    error = admin_required()
    if error:
        return error
    data = request.get_json(silent=True)
    if data is None:
        data = request.form.to_dict(flat=True)
    file_obj = request.files.get("image") or request.files.get("file")
    subdir = request.form.get("subdir") or data.get("subdir")
    try:
        if file_obj:
            image_path, _ = _save_cosmetic_upload(file_obj, subdir=subdir)
            data["image_path"] = image_path
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    try:
        itype = data.get("type")
        if itype is None:
            return jsonify({"message": "type is required"}), 400
        try:
            itype = ItemType(itype)
        except Exception:
            return jsonify({"message": "invalid type"}), 400
        image_path = (data.get("image_path") or "").strip() or None
        _enforce_visual_asset_requirement(itype, image_path)
        item = CosmeticItem(
            type=itype,
            name=(data.get("name") or "").strip(),
            price=int(data.get("price") or 0),
            rarity=(data.get("rarity") or None),
            image_path=image_path,
            theme_color=(data.get("theme_color") or None),
            description=(data.get("description") or None),
        )
        if not item.name:
            return jsonify({"message": "name is required"}), 400
        db.session.add(item)
        db.session.commit()
        return jsonify({"item": _item_to_dict(item)}), 201
    except (ValueError, SQLAlchemyError, OSError) as exc:
        db.session.rollback()
        return jsonify({"message": str(exc)}), 400


@bp.get("/items")
@jwt_required()
def list_items():
    q = CosmeticItem.query
    itype = request.args.get("type")
    if itype:
        try:
            q = q.filter_by(type=ItemType(itype))
        except Exception:
            return jsonify({"message": "invalid type"}), 400
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
        return jsonify({"message": "not_found"}), 404
    return jsonify({"item": _item_to_dict(i)}), 200


@bp.put("/items/<int:item_id>")
@jwt_required()
def update_item(item_id):
    error = admin_required()
    if error:
        return error
    i = CosmeticItem.query.get(item_id)
    if not i:
        return jsonify({"message": "not_found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        if "type" in data:
            try:
                i.type = ItemType(data.get("type"))
            except Exception:
                return jsonify({"message": "invalid type"}), 400
        if "name" in data:
            name = (data.get("name") or "").strip()
            if not name:
                return jsonify({"message": "name cannot be empty"}), 400
            i.name = name
        if "price" in data:
            i.price = int(data.get("price") or 0)
        for key in ("rarity", "theme_color", "description"):
            if key in data:
                setattr(i, key, data.get(key))
        if "image_path" in data:
            i.image_path = (data.get("image_path") or "").strip() or None
        _enforce_visual_asset_requirement(i.type, i.image_path)
        db.session.commit()
        return jsonify({"item": _item_to_dict(i)}), 200
    except (ValueError, SQLAlchemyError) as exc:
        db.session.rollback()
        return jsonify({"message": str(exc)}), 400


@bp.delete("/items/<int:item_id>")
@jwt_required()
def delete_item(item_id):
    error = admin_required()
    if error:
        return error
    i = CosmeticItem.query.get(item_id)
    if not i:
        return jsonify({"message": "not_found"}), 404
    image_path = i.image_path
    try:
        db.session.delete(i)
        db.session.commit()
        _delete_cosmetic_asset(image_path)
        return jsonify({"message": "deleted"}), 200
    except IntegrityError as exc:
        db.session.rollback()
        return jsonify({"message": "in_use", "detail": str(exc)}), 409
    except (SQLAlchemyError, OSError) as exc:
        db.session.rollback()
        return jsonify({"message": str(exc)}), 400


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
        return jsonify({"message": "name is required"}), 400
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
        return jsonify({"message": str(exc)}), 400


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
        return jsonify({"message": "not_found"}), 404
    return jsonify({"set": _set_to_dict(s, include_items=True)}), 200


@bp.put("/sets/<int:set_id>")
@jwt_required()
def update_set(set_id):
    error = admin_required()
    if error:
        return error
    s = CosmeticSet.query.get(set_id)
    if not s:
        return jsonify({"message": "not_found"}), 404
    data = request.get_json(silent=True) or {}
    try:
        if "name" in data:
            name = (data.get("name") or "").strip()
            if not name:
                return jsonify({"message": "name cannot be empty"}), 400
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
        return jsonify({"message": str(exc)}), 400


@bp.delete("/sets/<int:set_id>")
@jwt_required()
def delete_set(set_id):
    error = admin_required()
    if error:
        return error
    s = CosmeticSet.query.get(set_id)
    if not s:
        return jsonify({"message": "not_found"}), 404
    try:
        CosmeticSetItem.query.filter_by(set_id=set_id).delete()
        db.session.delete(s)
        db.session.commit()
        return jsonify({"message": "deleted"}), 200
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"message": str(exc)}), 400


@bp.get("/sets/<int:set_id>/items")
@jwt_required()
def list_set_items(set_id):
    s = CosmeticSet.query.get(set_id)
    if not s:
        return jsonify({"message": "not_found"}), 404
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


def _collect_item_image_files(items):
    img_files = {}
    if not items:
        return img_files
    base = current_app.static_folder or os.path.join(current_app.root_path, "static")
    base_abs = os.path.abspath(base)
    static_url_path = current_app.static_url_path or "/static"
    for item in items:
        rel_path = (item.get("image_path") or "").strip()
        if not rel_path or rel_path in img_files:
            continue
        abs_path = os.path.abspath(os.path.normpath(os.path.join(base_abs, rel_path)))
        try:
            if os.path.commonpath([base_abs, abs_path]) != base_abs:
                continue
        except ValueError:
            continue
        try:
            with open(abs_path, "rb") as fh:
                encoded = base64.b64encode(fh.read()).decode("ascii")
        except (OSError, ValueError):
            continue
        img_files[rel_path] = {
            "path": rel_path,
            "url": f"{static_url_path.rstrip('/')}/{rel_path.lstrip('/')}",
            "data": encoded,
        }
    return img_files


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
    img_files = _collect_item_image_files(by_id.values())
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
                "img_files": img_files,
                "pagination": _pagination_meta(pagination),
            }
        ),
        200,
    )

@bp.post("/user/items/acquire")
@bp.post("/user/items/acquire/<int:item_id>")
@bp.post("/user/items/acquire/<int:item_id>/<int:item_price>")
@jwt_required()
def acquire_item(item_id=None, item_price=None):
    uid = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    if not data:
        data = request.form.to_dict(flat=True)

    def _first_int(*values):
        for v in values:
            try:
                return int(v)
            except (TypeError, ValueError):
                continue
        return None

    item_id = _first_int(item_id, data.get("item_id"), request.args.get("item_id"))
    item_price = _first_int(
        item_price, data.get("item_price"), request.args.get("item_price")
    )

    if item_id is None:
        return jsonify({"error": "item_id required"}), 400
    if item_price is None:
        return jsonify({"error": "item_price required"}), 400
    if not CosmeticItem.query.get(item_id):
        return jsonify({"message": "invalid_item"}), 404
    try:
        success, deducted, msg = revoke_points(
            uid, item_price, "아이템 구매로 인한 포인트 차감", True
        )
    except ValueError as e:
        return jsonify({"message": str(e)})
    if not success:
        return jsonify({"error": msg}), 400
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
        return jsonify({"message": str(exc)}), 400


@bp.post("/user/sets/acquire")
@jwt_required()
def acquire_set():
    uid = get_jwt_identity()
    data = request.get_json(silent=True) or {}
    try:
        set_id = int(data.get("set_id"))
    except Exception:
        return jsonify({"message": "set_id required"}), 400
    s = CosmeticSet.query.get(set_id)
    if not s:
        return jsonify({"message": "invalid_set"}), 404
    rel = CosmeticSetItem.query.filter_by(set_id=set_id).all()
    created, existing = [], []
    try:
        for item in rel:
            try:
                iid = item.item_id
                price = item.price
                ui = UserItem(user_id=uid, item_id=iid, acquired_at=datetime.now())
            except AttributeError:
                return jsonify({"error": "아이템 속성이 없습니다"}), 400
            try:
                try:
                    success, deducted, msg = revoke_points(
                        uid, price, "아이템 구매로 인한 포인트 차감", True
                    )
                except ValueError as e:
                    return jsonify({"message": str(e)})
                if not success:
                    return jsonify({"error": msg}), 400
            except ValueError as e:
                return jsonify({"message": e.args})
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
        return jsonify({"message": str(exc)}), 400


# ---- User Cosmetic State ----


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
            return jsonify({"message": reason, "field": field}), 400

    try:
        for k, v in updates.items():
            setattr(st, k, v)
        st.last_updated = datetime.now()
        db.session.commit()
        return jsonify({"message": "updated"}), 200
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"message": str(exc)}), 400
