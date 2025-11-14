import requests
from flask import current_app, request, jsonify, redirect, Blueprint
from ..extensions import db
from ..models import Order

bp=Blueprint("order",__name__)

def kakao_headers():
    return {
        "Authorization": f"KakaoAK {current_app.config['KAKAO_ADMIN_KEY']}",
        "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
    }


@bp.post("/ready")
def pay_ready():
    """
    React에서 /payment/ready 로 POST
    body: { orderId, userId, itemName, quantity, amount }
    """

    data = request.json
    order_id = data["orderId"]
    user_id = data["userId"]
    item_name = data["itemName"]
    quantity = int(data.get("quantity", 1))
    total_amount = int(data["amount"])

    # DB에 주문 정보 저장 (상태 READY)
    order = Order(
        order_id=order_id,
        user_id=user_id,
        item_name=item_name,
        quantity=quantity,
        total_amount=total_amount,
        status="READY",
    )
    db.session.add(order)
    db.session.commit()

    body = {
        "cid": current_app.config["KAKAO_CID"],
        "partner_order_id": order_id,
        "partner_user_id": user_id,
        "item_name": item_name,
        "quantity": quantity,
        "total_amount": total_amount,
        "tax_free_amount": 0,
        "approval_url": f"{current_app.config['KAKAO_APPROVAL_URL']}?order_id={order_id}&user_id={user_id}",
        "cancel_url": current_app.config["KAKAO_CANCEL_URL"],
        "fail_url": current_app.config["KAKAO_FAIL_URL"],
    }

    resp = requests.post(
        "https://kapi.kakao.com/v1/payment/ready",
        headers=kakao_headers(),
        data=body,
    )
    resp.raise_for_status()
    result = resp.json()

    # tid 저장
    order.tid = result["tid"]
    db.session.commit()

    # PC 기준
    return jsonify(
        {
            "tid": result["tid"],
            "next_redirect_pc_url": result["next_redirect_pc_url"],
            "next_redirect_mobile_url": result.get("next_redirect_mobile_url"),
        }
    )


@bp.get("/approve")
def pay_approve():
    """
    카카오페이에서 approval_url로 redirect
    query: pg_token, order_id, user_id
    """

    pg_token = request.args.get("pg_token")
    order_id = request.args.get("order_id")
    user_id = request.args.get("user_id")

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

    resp = requests.post(
        "https://kapi.kakao.com/v1/payment/approve",
        headers=kakao_headers(),
        data=body,
    )
    resp.raise_for_status()
    result = resp.json()

    # 결제 승인 처리
    order.status = "APPROVED"
    db.session.commit()

    # 아주 단순하게는 결제 성공 후 프론트로 redirect
    # 예: http://localhost:5173/payment/success?order_id=...
    redirect_url = f"http://localhost:5173/payment/success?order_id={order.order_id}"
    return redirect(redirect_url)
