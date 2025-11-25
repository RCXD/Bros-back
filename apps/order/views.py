# views.py

import json
import time
import requests
from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    request,
    send_from_directory,
)
from sqlalchemy.exc import IntegrityError
from apps.config.server import db
from .models import Order, PaymentLog
from ..auth.models import User
import logging

bp = Blueprint("order", __name__)


@bp.get("/api_info")
def api_info():
    """
    주문 API 정보 제공 (개발용)
    """
    info = {
        "module": "order",
        "base_path": "/order",
        "description": "주문 및 결제 관리 (KakaoPay 연동)",
        "endpoints": [
            {
                "path": "/order",
                "method": "POST",
                "auth_required": True,
                "description": "주문 생성",
                "json_body": {
                    "item_name": "상품명 (필수)",
                    "quantity": "수량 (필수)",
                    "total_amount": "총액 (필수)",
                },
            },
            {
                "path": "/order/<order_id>",
                "method": "GET",
                "auth_required": True,
                "description": "주문 조회",
            },
            {
                "path": "/order/payment/ready",
                "method": "POST",
                "auth_required": True,
                "description": "결제 준비 (KakaoPay)",
            },
            {
                "path": "/order/payment/approve",
                "method": "POST",
                "auth_required": True,
                "description": "결제 승인",
            },
            {
                "path": "/order/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            },
        ],
    }
    return jsonify(info), 200


def save_ready_order(order_id, user_id, item_name, quantity, total_amount):
    """Persist an order as READY so KakaoPay /ready can reference it."""
    order = Order(
        order_id=order_id,
        user_id=user_id,
        item_name=item_name,
        quantity=quantity,
        total_amount=total_amount,
        status="READY",
    )
    db.session.add(order)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing_order = Order.query.filter_by(order_id=order_id).first()
        if existing_order:
            return existing_order
        raise
    return order


def persist_order_tid(order, tid):
    order.tid = tid
    db.session.commit()
    return order


def log_payment_event(order, event, status=None, payload=None, tid=None):
    """Keep a lightweight audit trail for each KakaoPay call."""
    payload_dump = json.dumps(payload, ensure_ascii=False) if payload else None
    log = PaymentLog(
        order=order,
        order_id=order.order_id,
        order_ref_id=order.id,
        user_id=order.user_id,
        tid=tid,
        event=event,
        status=status,
        payload=payload_dump,
    )
    db.session.add(log)
    db.session.commit()
    return log


# shared request validation helper for /ready and /approve


def validate_request_fields(source, required_fields):
    missing = [field for field in required_fields if field not in source]
    if not missing:
        return None
    return jsonify({"error": f"Missing fields: {missing}"}), 400


def resolve_order_from_args(source):
    """Locate an order by Kakao-provided query params."""
    order_id = source.get("partner_order_id") or source.get("order_id")
    user_id = source.get("partner_user_id") or source.get("user_id")
    if not order_id or not user_id:
        return None, (jsonify({"error": "Missing order_id or user_id"}), 400)

    try:
        user_id_value = int(user_id)
    except (TypeError, ValueError):
        return None, (jsonify({"error": "Invalid user_id"}), 400)

    order = Order.query.filter_by(order_id=order_id, user_id=user_id_value).first()
    if not order:
        return None, (jsonify({"error": "Order not found"}), 404)

    return order, None


def finalize_terminal_order(order, status, event, payload):
    """Persist terminal order state then audit the Kakao callback."""
    order.status = status
    db.session.commit()
    log_payment_event(order, event, status, payload, tid=order.tid)
    return jsonify(
        {"message": f"Order marked as {status.lower()}", "order_id": order.order_id}
    )


@bp.get("/cancel")
def pay_cancel():
    """Handle a Kakao cancel redirect and persist the cancellation."""
    order, error = resolve_order_from_args(request.args)
    if error:
        return error
    payload = request.args.to_dict()
    return finalize_terminal_order(order, "CANCELED", "CANCEL", payload)


@bp.get("/fail")
def pay_fail():
    """Handle a Kakao fail redirect and persist the failure."""
    order, error = resolve_order_from_args(request.args)
    if error:
        return error
    payload = request.args.to_dict()
    return finalize_terminal_order(order, "FAILED", "FAIL", payload)


def kakao_headers():
    return {
        "Authorization": f"KakaoAK {current_app.config['KAKAO_ADMIN_KEY']}",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
    }


def kakao_post_with_retry(url, data, max_attempts=3, backoff_factor=0.5):
    delay = backoff_factor
    for attempt in range(max_attempts):
        try:
            resp = requests.post(url, headers=kakao_headers(), data=data)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            if attempt == max_attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2


@bp.post("/ready")
def pay_ready():
    """
    React → POST /payment/ready
    body: { orderId, username, itemName, quantity, amount }
    """

    data = request.get_json() or {}

    required = ["orderId", "username", "itemName", "amount"]
    validation_error = validate_request_fields(data, required)
    if validation_error:
        return validation_error

    order_id = data["orderId"]
    user_name = data["username"]
    item_name = data["itemName"]
    quantity = int(data.get("quantity", 1))
    total_amount = int(data["amount"])

    user = User.query.filter_by(username=user_name).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    user_id = user.user_id

    order = Order.query.filter_by(order_id=order_id).first()
    if order:
        if order.user_id != user_id:
            return jsonify({"error": "Order ID already in use"}), 400
        order.item_name = item_name
        order.quantity = quantity
        order.total_amount = total_amount
        order.status = "READY"
        db.session.commit()
    else:
        order = save_ready_order(
            order_id=order_id,
            user_id=user_id,
            item_name=item_name,
            quantity=quantity,
            total_amount=total_amount,
        )

    body = {
        "cid": current_app.config["KAKAO_CID"],
        "partner_order_id": order_id,
        "partner_user_id": user_id,
        "item_name": item_name,
        "quantity": quantity,
        "total_amount": total_amount,
        "tax_free_amount": 0,
        "approval_url": (
            f"{current_app.config['KAKAO_APPROVAL_URL']}"
            f"?order_id={order_id}&user_id={user_id}"
        ),
        "cancel_url": current_app.config["KAKAO_CANCEL_URL"],
        "fail_url": current_app.config["KAKAO_FAIL_URL"],
    }

    try:
        resp = kakao_post_with_retry(
            "https://kapi.kakao.com/v1/payment/ready",
            body,
        )
    except Exception as e:

        return (
            jsonify({"error": "KakaoPay ready request failed", "detail": str(e)}),
            500,
        )

    result = resp.json()

    persist_order_tid(order, result["tid"])
    log_payment_event(order, "READY", "READY", result, tid=result.get("tid"))

    return jsonify(
        {
            "tid": result["tid"],
            "next_redirect_pc_url": result.get("next_redirect_pc_url"),
            "next_redirect_mobile_url": result.get("next_redirect_mobile_url"),
        }
    )


@bp.get("/approve")
def pay_approve():
    """
    KakaoPay redirect → GET /approve
    query: pg_token, order_id, user_id
    """

    order_id = request.args.get("order_id")
    user_id = request.args.get("user_id")
    validation_error = validate_request_fields(request.args, ["order_id", "user_id"])
    if validation_error:
        return validation_error

    pg_token = request.args.get("pg_token")

    if not pg_token:
        return "Invalid pg_token", 400

    order = Order.query.filter_by(order_id=order_id, user_id=user_id).first()
    if not order or not order.tid:
        return "Invalid order", 400

    body = {
        "cid": current_app.config["KAKAO_CID"],
        "tid": order.tid,
        "partner_order_id": order.order_id,
        "partner_user_id": order.user_id,
        "pg_token": pg_token,
    }

    try:
        resp = kakao_post_with_retry(
            "https://kapi.kakao.com/v1/payment/approve",
            body,
        )
    except Exception as e:
        logging.error(f"Payment approval failed: {e}")
        order.status = "FAILED"
        db.session.commit()
        log_payment_event(
            order, "APPROVE_FAIL", "FAILED", payload=str(e), tid=order.tid
        )
        return "Payment approval failed", 500

    result = resp.json()

    order.status = "APPROVED"
    db.session.commit()
    log_payment_event(order, "APPROVE", order.status, result, tid=order.tid)

    redirect_url = (
        f"{current_app.config['FRONTEND_URL']}/order/success?order_id={order.order_id}"
    )
    return redirect(redirect_url)


def log_payment_event(order, event, status=None, payload=None, tid=None):
    """Keep a lightweight audit trail for each KakaoPay call."""
    payload_dump = json.dumps(payload, ensure_ascii=False) if payload else None
    log = PaymentLog(
        order=order,
        order_id=order.order_id,
        order_ref_id=order.id,
        user_id=order.user_id,
        tid=tid,
        event=event,
        status=status,
        payload=payload_dump,
    )
    db.session.add(log)
    db.session.commit()
    return log
