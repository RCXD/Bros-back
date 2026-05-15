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
from apps.user.reward_utils import revoke_points

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


@bp.get("/api_info")
def api_info():
    """Return cosmetic module API metadata for development reference.

    Returns:
        JSON response with module info and endpoint list, HTTP 200.
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
    """Build a pagination metadata dict from a SQLAlchemy Pagination object.

    Args:
        pagination: A SQLAlchemy Pagination instance.

    Returns:
        A dict with ``page``, ``per_page``, ``total``, ``pages``, ``has_next``,
        and ``has_prev`` keys.
    """
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
    """Parse and validate ``page`` and ``per_page`` query parameters.

    Args:
        default_per_page: Default page size when ``per_page`` is not provided.
        max_per_page: Maximum allowed page size; larger values are capped.

    Returns:
        A tuple ``(page, per_page, None)`` on success, or
        ``(None, None, (Response, 400))`` if parameters are invalid.
    """
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
    """Apply pagination to a SQLAlchemy query using request query parameters.

    Args:
        query: The SQLAlchemy Query to paginate.
        default_per_page: Default page size (default ``DEFAULT_PER_PAGE``).
        max_per_page: Maximum page size cap (default ``MAX_PER_PAGE``).

    Returns:
        A tuple ``(Pagination, None)`` on success, or ``(None, (Response, 400))``
        if pagination parameters are invalid.
    """
    if err:
        return None, err
    return query.paginate(page=page, per_page=per_page, error_out=False), None


# ---- Items (Admin) ----


@bp.post("/items")
@jwt_required()
def create_item():
    """Create a new CosmeticItem (authenticated users only).

    Expects a JSON body with ``type`` (required), ``name`` (required), and
    optional ``price``, ``rarity``, ``image_path``, ``theme_color``,
    ``description`` fields.

    Returns:
        JSON with the created item dict, HTTP 201.
        HTTP 400 if required fields are missing, the type is invalid, or a DB
        error occurs.
    """
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
    """Return a paginated list of CosmeticItems with an optional type filter.

    Args (query string):
        type: Optional ``ItemType`` value to filter by.
        page: Page number (default 1).
        per_page: Items per page (default 50, max 200).

    Returns:
        JSON with ``items`` list and ``pagination`` metadata, HTTP 200.
        HTTP 400 if the type value is invalid.
    """
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
    """Return a single CosmeticItem by its primary key.

    Args:
        item_id: Integer primary key of the CosmeticItem.

    Returns:
        JSON with the item dict, HTTP 200.
        HTTP 404 if the item is not found.
    """


@bp.put("/items/<int:item_id>")
@jwt_required()
def update_item(item_id):
    """Update fields on an existing CosmeticItem (admin only).

    Applies a partial update using only fields present in the JSON body.

    Args:
        item_id: Integer primary key of the CosmeticItem to update.

    Returns:
        JSON with the updated item dict, HTTP 200.
        HTTP 400 if field values are invalid or a DB error occurs.
        HTTP 403 if the caller is not an admin.
        HTTP 404 if the item is not found.
    """
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
    """Delete a CosmeticItem by its primary key (admin only).

    Args:
        item_id: Integer primary key of the CosmeticItem to delete.

    Returns:
        JSON with a confirmation message, HTTP 200.
        HTTP 400 if a DB error occurs.
        HTTP 403 if the caller is not an admin.
        HTTP 404 if the item is not found.
        HTTP 409 if the item is referenced by other records.
    """
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
    """Create a new CosmeticSet with optional item composition (admin only).

    Expects a JSON body with ``name`` (required), ``price``, ``description``,
    ``preview_img``, and an optional ``items`` list of item IDs.

    Returns:
        JSON with the created set dict (including items), HTTP 201.
        HTTP 400 if required fields are missing or a DB error occurs.
        HTTP 403 if the caller is not an admin.
    """
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
    """Return a paginated list of CosmeticSets ordered by creation date.

    Args (query string):
        page: Page number (default 1).
        per_page: Items per page (default 50, max 200).

    Returns:
        JSON with ``sets`` list and ``pagination`` metadata, HTTP 200.
    """
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
    """Return a single CosmeticSet including its composed items.

    Args:
        set_id: Integer primary key of the CosmeticSet.

    Returns:
        JSON with the set dict (items included), HTTP 200.
        HTTP 404 if the set is not found.
    """


@bp.put("/sets/<int:set_id>")
@jwt_required()
def update_set(set_id):
    """Update fields on an existing CosmeticSet (admin only).

    Providing an ``items`` list in the body replaces the entire set composition.

    Args:
        set_id: Integer primary key of the CosmeticSet to update.

    Returns:
        JSON with the updated set dict (items included), HTTP 200.
        HTTP 400 if field values are invalid or a DB error occurs.
        HTTP 403 if the caller is not an admin.
        HTTP 404 if the set is not found.
    """
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
    """Delete a CosmeticSet and its item composition rows (admin only).

    Args:
        set_id: Integer primary key of the CosmeticSet to delete.

    Returns:
        JSON with a confirmation message, HTTP 200.
        HTTP 400 if a DB error occurs.
        HTTP 403 if the caller is not an admin.
        HTTP 404 if the set is not found.
    """
        db.session.delete(s)
        db.session.commit()
        return jsonify({"message": "deleted"}), 200
    except SQLAlchemyError as exc:
        db.session.rollback()
        return jsonify({"error": str(exc)}), 400


@bp.get("/sets/<int:set_id>/items")
@jwt_required()
def list_set_items(set_id):
    """Return a paginated list of CosmeticItems belonging to a specific set.

    Args:
        set_id: Integer primary key of the CosmeticSet.

    Returns:
        JSON with ``items`` list and ``pagination`` metadata, HTTP 200.
        HTTP 404 if the set is not found.
    """
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
    """Return a paginated list of CosmeticItems owned by the authenticated user.

    Returns:
        JSON with ``items`` list (each entry includes the item dict and acquisition
        metadata) and ``pagination`` metadata, HTTP 200.
    """
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
    """Deduct points from the authenticated user and grant them a CosmeticItem.

    Expects a JSON body with ``item_id`` and ``item_price``.

    Returns:
        JSON with the new ``user_item_id``, HTTP 201.
        JSON with ``user_item_id`` and ``"already_owned"`` message, HTTP 200
        if the user already owns the item.
        HTTP 400 if required fields are missing, point deduction fails, or a DB
        error occurs.
        HTTP 404 if the item does not exist.
    """
    except Exception:
        return jsonify({"error": "item_id required"}), 400
    try:
        item_price = int(data.get("item_price"))
    except Exception:
        return jsonify({"error": "item_price required"}), 400
    if not CosmeticItem.query.get(item_id):
        return jsonify({"error": "invalid_item"}), 404
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
        return jsonify({"error": str(exc)}), 400


@bp.post("/user/sets/acquire")
@jwt_required()
def acquire_set():
    """Deduct points for each item in a CosmeticSet and grant them to the user.

    Expects a JSON body with ``set_id``.

    Returns:
        JSON with ``acquired`` and ``existing`` item ID lists, HTTP 200.
        HTTP 400 if ``set_id`` is missing, point deduction fails, or a DB error
        occurs.
        HTTP 404 if the set does not exist.
    """
    except Exception:
        return jsonify({"error": "set_id required"}), 400
    s = CosmeticSet.query.get(set_id)
    if not s:
        return jsonify({"error": "invalid_set"}), 404
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
        return jsonify({"error": str(exc)}), 400


# ---- User Cosmetic State ----


def _get_or_create_user_state(uid):
    """Retrieve or create a UserCosmeticState record for the given user.

    Args:
        uid: The user ID to look up or create a state record for.

    Returns:
        The existing or newly created UserCosmeticState instance.
    """
    if not st:
        st = UserCosmeticState(user_id=uid, last_updated=datetime.now())
        db.session.add(st)
        db.session.commit()
    return st


def _validate_ownership(uid, item_id, required_type=None):
    """Check that a user owns a CosmeticItem and that it matches the expected type.

    Args:
        uid: The user ID to validate ownership for.
        item_id: The item ID to check, or None (treated as valid/unset).
        required_type: Optional ``ItemType`` the item must match.

    Returns:
        A tuple ``(True, None)`` if valid, or ``(False, error_reason_string)``
        if the item does not exist, has the wrong type, or is not owned.
    """
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
    """Return the current cosmetic state (equipped item IDs) for the authenticated user.

    Returns:
        JSON with the user's cosmetic state including all slot item IDs and
        ``last_updated`` timestamp, HTTP 200.
    """
    return (
        jsonify(
            {
                "user_id": st.user_id,
                "border_item_id": st.border_item_id,
                "overlay_item_id": st.overlay_item_id,
                "theme_item_id": st.theme_item_id,
                "font_item_id": st.font_item_id,
                "effect_item_id": st.effect_item_id,
                "badge_item_id": st.badge_item_id,
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
    """Update the equipped cosmetic item slots for the authenticated user.

    Accepts a JSON body or form data.  Each slot field (``border_item_id``,
    ``overlay_item_id``, ``theme_item_id``, ``font_item_id``, ``effect_item_id``,
    ``badge_item_id``) must be null or an item ID owned by the user matching the
    slot's expected type.

    Returns:
        JSON with a confirmation message, HTTP 200.
        HTTP 400 if ownership or type validation fails, or a DB error occurs.
    """

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
        "badge_item_id": _parse_int(data.get("badge_item_id")),
    }

    validations = [
        ("border_item_id", ItemType.border),
        ("overlay_item_id", ItemType.overlay),
        ("theme_item_id", ItemType.theme),
        ("font_item_id", ItemType.font),
        ("effect_item_id", ItemType.effect),
        ("badge_item_id", ItemType.badge),
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
    """Upload a cosmetic overlay image file to the server's static directory.

    Accepts a multipart form with a ``file`` field and an optional ``subdir``
    field specifying the target subdirectory under ``static/`` (default
    ``cosmetic_overlays``).

    Returns:
        JSON with the relative ``path`` and public ``url`` of the saved file,
        HTTP 201.
        HTTP 400 if the file is missing or has an empty filename.
    """
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
