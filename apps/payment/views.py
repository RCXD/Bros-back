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
from flask_jwt_extended import current_user, jwt_required
from sqlalchemy.exc import IntegrityError
from apps.config.server import db
from .models import Order, PaymentLog
from ..auth.models import User
from ..cosmetic.models import CosmeticItem
import logging
import urllib.parse

bp = Blueprint("payment", __name__)


@bp.get("/api_info")
def api_info():
    """
    주문 API 정보 제공 (개발용)
    """
    info = {
        "module": "payment",
        "base_path": "/payment",
        "description": "KakaoPay payment flows",
        "endpoints": [
            {
                "path": "/payment/ready",
                "method": "POST",
                "auth_required": True,
                "description": "Prepare KakaoPay payment",
            },
            {
                "path": "/payment/approve",
                "method": "GET",
                "auth_required": False,
                "description": "Approve KakaoPay payment",
            },
            {
                "path": "/payment/cancel",
                "method": "GET",
                "auth_required": False,
                "description": "Handle payment cancellation callback",
            },
            {
                "path": "/payment/fail",
                "method": "GET",
                "auth_required": False,
                "description": "Handle payment failure callback",
            },
            {
                "path": "/payment/purchase/result",
                "method": "GET",
                "auth_required": True,
                "description": "Query purchase status",
            },
            {
                "path": "/payment/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API overview endpoint",
            },
        ],
    }
    return jsonify(info), 200


def save_ready_order(
    order_id,
    user_id,
    item_id,
    quantity,
    total_amount,
):
    """Create a new READY order with item snapshot values."""
    order = Order(
        order_id=order_id,
        user_id=user_id,
        item_id=item_id,
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
    encoded_data = urllib.parse.urlencode(data)
    delay = backoff_factor
    for attempt in range(max_attempts):
        try:
            resp = requests.post(url, headers=kakao_headers(), data=encoded_data)
            print("🔹 Kakao Response Status:", resp.status_code)
            print("🔹 Kakao Response Text:", resp.text)
            resp.raise_for_status()

            return resp
        except requests.RequestException as exc:
            if attempt == max_attempts - 1:
                raise
            time.sleep(delay)
            delay *= 2


@bp.route("/ready", methods=["POST", "OPTIONS"])
def pay_ready():
    """
    React → POST /order/ready
    body: { orderId, user_id, itemId, quantity, amount }
    """
    # CORS preflight
    if request.method == "OPTIONS":
        return "", 200

    # JSON 파싱
    try:
        data = request.get_json(force=True) or {}
        print("🔹 Received JSON:", data)
    except Exception as e:
        return jsonify({"error": "Invalid JSON", "detail": str(e)}), 400

    # 필수 필드 검증
    required = ["orderId", "userId", "itemId", "amount"]
    validation_error = validate_request_fields(data, required)
    if validation_error:
        return validation_error

    # Payload 추출
    order_id = data["orderId"]
    user_id = data["userId"]
    item_id = int(data["itemId"])
    quantity = int(data.get("quantity", 1))
    total_amount = int(data["amount"])

    # 유저 확인
    user = User.query.filter_by(user_id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    user_id = user.user_id

    # 아이템 확인
    item = CosmeticItem.query.get(item_id)
    if not item:
        return jsonify({"error": "Item not found"}), 404

    # 서버 기준 가격 검증
    correct_amount = (item.price or 0) * quantity
    if total_amount != correct_amount:
        return jsonify({"error": "Amount mismatch"}), 400

    # 기존 주문 여부 확인
    order = Order.query.filter_by(order_id=order_id).first()

    if order:
        # 현재 사용자와 일치하는지 확인
        if order.user_id != user_id:
            return jsonify({"error": "Order ID already in use by another user"}), 400

        # 이미 READY/SUCCESS면 재요청 막기 (원하면 정책 조정)
        if order.status in ["READY", "SUCCESS"]:
            return jsonify({"error": f"Order already in {order.status} status"}), 400

        # 주문 정보 업데이트
        order.item_id = item_id
        order.quantity = quantity
        order.total_amount = correct_amount
        order.status = "READY"
        db.session.commit()
    else:
        # 신규 생성 (여기서 내부 commit까지 처리)
        order = save_ready_order(
            order_id=order_id,
            user_id=user_id,
            item_id=item_id,
            quantity=quantity,
            total_amount=correct_amount,
        )

    # KakaoPay 요청 body
    body = {
        "cid": current_app.config["KAKAO_CID"],
        "partner_order_id": order_id,
        "partner_user_id": user_id,
        "item_name": item.name,  # DB에는 안 저장해도, 카카오에 보낼 용도로만 사용
        "quantity": quantity,
        "total_amount": correct_amount,
        "tax_free_amount": 0,
        "approval_url": f"{current_app.config['KAKAO_APPROVAL_URL']}?order_id={order_id}&user_id={user_id}",
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
    print("🔸 Kakao /ready response:", result)

    # tid 없으면 바로 에러 반환
    tid = result.get("tid")
    if not tid:
        return (
            jsonify(
                {
                    "error": "KakaoPay did not return tid",
                    "detail": result,
                }
            ),
            502,
        )

    # 주문에 tid 저장 + 로그
    order.tid = tid
    order.status = "READY"  # 또는 "IN_PROGRESS" 등으로 세분화 가능
    db.session.commit()

    log_payment_event(order, "READY", order.status, result, tid=tid)

    # 프론트로 redirect URL 반환
    return jsonify(
        {
            "tid": tid,
            "next_redirect_pc_url": result.get("next_redirect_pc_url"),
            "next_redirect_mobile_url": result.get("next_redirect_mobile_url"),
        }
    )


@bp.route("/approve", methods=["GET", "OPTIONS"])
def pay_approve():
    """
    KakaoPay redirect → GET /approve
    query: pg_token, order_id, user_id
    """
    print("🔥 APPROVE HIT")
    # --- Step 1. Query validation ---
    validation_error = validate_request_fields(request.args, ["order_id", "user_id"])
    if validation_error:
        return validation_error

    order_id = request.args.get("order_id")
    user_id = request.args.get("user_id")
    pg_token = request.args.get("pg_token")

    if not pg_token:
        return "Invalid pg_token", 400

    # --- Step 2. Valid order check ---
    order = Order.query.filter_by(order_id=order_id, user_id=user_id).first()
    if not order or not order.tid:
        return "Invalid or incomplete order", 400

    # 🛑 이미 승인된 주문 재승인 방지
    if order.status == "SUCCESS":
        return redirect(
            f"{current_app.config['FRONTEND_URL']}/payment/success?order_id={order.order_id}"
        )

    # --- Step 3. Kakao API 호출 ---
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
        result = resp.json()
    except Exception as e:
        logging.error(f"Payment approval failed: {e}")
        order.status = "FAILED"
        db.session.commit()
        log_payment_event(
            order, "APPROVE_FAIL", "FAILED", payload=str(e), tid=order.tid
        )
        return "Payment approval failed", 500

    # --- Step 4. 승인 성공 후 처리 ---
    order.status = "SUCCESS"  # FINAL 결제 완료
    db.session.commit()
    log_payment_event(order, "APPROVE", order.status, result, tid=order.tid)

    # --- Step 5. 유저에게 CosmeticItem 지급 (UserItem 테이블 등록) ---
    from apps.cosmetic.models import UserItem

    existing = UserItem.query.filter_by(
        user_id=order.user_id, item_id=order.item_id
    ).first()

    if not existing:
        new_item = UserItem(
            user_id=order.user_id, item_id=order.item_id, is_equipped=False
        )
        db.session.add(new_item)
        db.session.commit()
        log_payment_event(
            order, "ITEM_GRANTED", order.status, {"item_id": order.item_id}
        )

    # --- Step 6. Redirect to Frontend success page ---
    redirect_url = f"{current_app.config['FRONTEND_URL']}/payment/success?order_id={order.order_id}"
    return redirect(redirect_url)


@bp.get("/purchase/result")
@jwt_required
def purchase_result():
    order_id = request.args.get("order_id")
    if not order_id:
        return jsonify({"error": "order_id required"}), 400

    uid = current_user.user_id
    order = Order.query.filter_by(order_id=order_id, user_id=uid).first()
    if not order:
        return jsonify({"error": "order_not_found"}), 404

    item = CosmeticItem.query.get(order.item_id)
    return jsonify(
        {
            "order_id": order.order_id,
            "status": order.status,
            "item_id": order.item_id,
            "item_name": item.name if item else None,
            "amount": order.total_amount,
            "granted": order.status == "SUCCESS",
        }
    )
