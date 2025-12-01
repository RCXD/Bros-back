"""
코스메틱 아이템 및 관련 데이터 생성 모듈
- CosmeticItem (border, overlay, effect 프리셋)
- UserItem (관리자 인벤토리)
- Order (데모 주문)
"""

import pytest
from datetime import datetime

from apps.config.server import db
from apps.auth.models import AccountType, User
from apps.cosmetic.models import CosmeticItem, ItemType, UserItem
from apps.payment.models import Order

try:
    from logger import get_logger
except ImportError:
    from apps.common.logger import get_logger


# ============================================================================
# PRESET DEFINITIONS
# ============================================================================

BORDER_PRESETS = [
    {
        "type": ItemType.border,
        "name": "nitro",
        "price": 0,
        "rarity": "epic",
        "theme_color": "#ff73fa",
        "description": "Discord Nitro 스타일 그라디언트 링",
    },
    {
        "type": ItemType.border,
        "name": "glow_purple",
        "price": 1500,
        "rarity": "rare",
        "theme_color": "#a855f7",
        "description": "보라색 소프트 글로우 링",
    },
    {
        "type": ItemType.border,
        "name": "glow_cyan",
        "price": 1500,
        "rarity": "rare",
        "theme_color": "#22d3ee",
        "description": "시안 컬러 글로우 링",
    },
    {
        "type": ItemType.border,
        "name": "neon_pink",
        "price": 2000,
        "rarity": "epic",
        "theme_color": "#ff4fd8",
        "description": "강한 네온 핑크 라인",
    },
    {
        "type": ItemType.border,
        "name": "double_gold",
        "price": 2500,
        "rarity": "legendary",
        "theme_color": "#facc15",
        "description": "이중 금색 링",
    },
    {
        "type": ItemType.border,
        "name": "dashed_blue",
        "price": 800,
        "rarity": "uncommon",
        "theme_color": "#3b82f6",
        "description": "푸른 점선 스타일 링",
    },
    {
        "type": ItemType.border,
        "name": "rainbow_cycle",
        "price": 3000,
        "rarity": "legendary",
        "theme_color": "#ffffff",
        "description": "무지개 애니메이션 링",
    },
]

OVERLAY_PRESETS = [
    {
        "type": ItemType.overlay,
        "name": "sparkles_pink",
        "price": 1200,
        "rarity": "rare",
        "theme_color": "#f472b6",
        "description": "핑크 반짝이 입자",
    },
    {
        "type": ItemType.overlay,
        "name": "sparkles_blue",
        "price": 1200,
        "rarity": "rare",
        "theme_color": "#60a5fa",
        "description": "블루 반짝이 입자",
    },
    {
        "type": ItemType.overlay,
        "name": "flame_orange",
        "price": 1800,
        "rarity": "epic",
        "theme_color": "#fb923c",
        "description": "주황색 화염 효과",
    },
    {
        "type": ItemType.overlay,
        "name": "flame_purple",
        "price": 1800,
        "rarity": "epic",
        "theme_color": "#a855f7",
        "description": "보라색 마법 화염 효과",
    },
    {
        "type": ItemType.overlay,
        "name": "wing_white",
        "price": 2200,
        "rarity": "legendary",
        "theme_color": "#e5e7eb",
        "description": "양 옆으로 펼쳐지는 흰색 날개 효과",
    },
    {
        "type": ItemType.overlay,
        "name": "wing_dark",
        "price": 2200,
        "rarity": "legendary",
        "theme_color": "#111827",
        "description": "어두운 날개 실루엣 효과",
    },
    {
        "type": ItemType.overlay,
        "name": "shards_ice",
        "price": 1600,
        "rarity": "epic",
        "theme_color": "#67e8f9",
        "description": "얼음 파편이 튀는 느낌의 효과",
    },
]

EFFECT_PRESETS = [
    {
        "type": ItemType.effect,
        "name": "pulse",
        "price": 900,
        "rarity": "uncommon",
        "theme_color": None,
        "description": "서서히 커졌다 작아지는 펄스 효과",
    },
    {
        "type": ItemType.effect,
        "name": "float",
        "price": 900,
        "rarity": "uncommon",
        "theme_color": None,
        "description": "위아래로 부유하는 효과",
    },
    {
        "type": ItemType.effect,
        "name": "shake",
        "price": 900,
        "rarity": "uncommon",
        "theme_color": None,
        "description": "살짝 떨리는 흔들림 효과",
    },
    {
        "type": ItemType.effect,
        "name": "spin_slow",
        "price": 1400,
        "rarity": "rare",
        "theme_color": None,
        "description": "천천히 회전하는 효과",
    },
    {
        "type": ItemType.effect,
        "name": "bounce_soft",
        "price": 1400,
        "rarity": "rare",
        "theme_color": None,
        "description": "부드러운 튕김 애니메이션",
    },
    {
        "type": ItemType.effect,
        "name": "breathe",
        "price": 1400,
        "rarity": "rare",
        "theme_color": None,
        "description": "호흡하듯 밝기가 변하는 효과",
    },
]

PRESET_ITEMS = BORDER_PRESETS + OVERLAY_PRESETS + EFFECT_PRESETS


# ============================================================================
# GENERATION FUNCTIONS
# ============================================================================


def _bulk_import_presets(presets):
    """프리셋 아이템을 DB에 대량 삽입

    - 이미 존재하는 name은 스킵 (unique constraint)
    - bulk_save_objects로 빠른 삽입
    Returns (created_count, skipped_count)
    """
    if not presets:
        return 0, 0

    names = {p.get("name") for p in presets if p.get("name")}
    if not names:
        return 0, 0

    existing_names = {
        row[0]
        for row in db.session.query(CosmeticItem.name)
        .filter(CosmeticItem.name.in_(names))
        .all()
    }

    to_create = []
    skipped = 0
    for data in presets:
        name = (data.get("name") or "").strip()
        if not name or name in existing_names:
            skipped += 1
            continue

        raw_type = data.get("type")
        try:
            itype = raw_type if isinstance(raw_type, ItemType) else ItemType(raw_type)
        except Exception:
            skipped += 1
            continue

        to_create.append(
            CosmeticItem(
                type=itype,
                name=name,
                price=int(data.get("price") or 0),
                rarity=data.get("rarity"),
                # 미설정 시 정적 아이콘 경로를 name 기반으로 지정
                image_path=(data.get("image_path") or f"cosmetic_overlays/{name}.png"),
                theme_color=data.get("theme_color"),
                description=data.get("description"),
            )
        )

    created = 0
    if to_create:
        db.session.bulk_save_objects(to_create)
        db.session.commit()
        created = len(to_create)

    return created, skipped


def _seed_admin_inventory_demo():
    """관리자 계정에 모든 코스메틱 아이템 지급 및 데모 주문 생성

    Returns (admin_count, inventory_added, purchase_demo, sale_demo)
    """
    admin_ids = [
        row[0]
        for row in db.session.query(User.user_id)
        .filter(User.account_type == AccountType.ADMIN)
        .all()
    ]
    admin_count = len(admin_ids)
    if not admin_count:
        return 0, 0, 0, 0

    item_rows = (
        db.session.query(CosmeticItem.item_id, CosmeticItem.price)
        .order_by(CosmeticItem.item_id)
        .all()
    )
    if not item_rows:
        return admin_count, 0, 0, 0

    item_ids = [row[0] for row in item_rows]
    price_map = {row[0]: int(row[1] or 0) for row in item_rows}

    # 기존 인벤토리 확인
    existing_pairs = {
        (row[0], row[1])
        for row in db.session.query(UserItem.user_id, UserItem.item_id)
        .filter(UserItem.user_id.in_(admin_ids), UserItem.item_id.in_(item_ids))
        .all()
    }

    now = datetime.now()
    new_inventory = [
        UserItem(user_id=uid, item_id=iid, acquired_at=now)
        for uid in admin_ids
        for iid in item_ids
        if (uid, iid) not in existing_pairs
    ]

    if new_inventory:
        db.session.bulk_save_objects(new_inventory)
        db.session.commit()

    # 데모 주문 생성
    existing_demo_orders = {
        row[0]
        for row in db.session.query(Order.order_id)
        .filter(Order.order_id.like("cosmetic-demo-%"))
        .all()
    }

    demo_orders = []
    purchase_demo = 0
    sale_demo = 0

    for idx, uid in enumerate(admin_ids):
        item_id = item_ids[idx % len(item_ids)]
        price = price_map[item_id]

        purchase_id = f"cosmetic-demo-purchase-{uid}-{item_id}"
        if purchase_id not in existing_demo_orders:
            demo_orders.append(
                Order(
                    order_id=purchase_id,
                    user_id=uid,
                    item_id=item_id,
                    quantity=1,
                    total_amount=price,
                    status="SUCCESS",
                )
            )
            existing_demo_orders.add(purchase_id)
            purchase_demo += 1

        sale_id = f"cosmetic-demo-sale-{uid}-{item_id}"
        if sale_id not in existing_demo_orders:
            demo_orders.append(
                Order(
                    order_id=sale_id,
                    user_id=uid,
                    item_id=item_id,
                    quantity=1,
                    total_amount=price,
                    status="CANCELLED",
                )
            )
            existing_demo_orders.add(sale_id)
            sale_demo += 1

    if demo_orders:
        db.session.bulk_save_objects(demo_orders)
        db.session.commit()

    return admin_count, len(new_inventory), purchase_demo, sale_demo


# ============================================================================
# PYTEST ENTRY POINT
# ============================================================================


@pytest.mark.no_cleanup
def test_generate_cosmetics(fixture_app):
    """코스메틱 아이템 및 관리자 인벤토리 생성"""
    log = get_logger()

    with fixture_app.app_context():
        log.info("코스메틱 아이템 생성 중...")

        # 1. 프리셋 아이템 생성
        created, skipped = _bulk_import_presets(PRESET_ITEMS)
        log.info(f"  코스메틱 프리셋: 생성={created}, 스킵={skipped}")

        # 2. 관리자 인벤토리 및 데모 주문 생성
        admin_count, inventory_added, purchase_demo, sale_demo = (
            _seed_admin_inventory_demo()
        )

        if not admin_count:
            log.info("  관리자 데모: 관리자 계정 없음")
        else:
            log.info(
                f"  관리자 데모: admins={admin_count}, "
                f"inventory={inventory_added}, "
                f"purchases={purchase_demo}, sales={sale_demo}"
            )

        # 최종 카운트
        total_items = CosmeticItem.query.count()
        total_user_items = UserItem.query.count()
        total_orders = Order.query.count()

        log.success(
            f"코스메틱 완료: 아이템={total_items}, "
            f"인벤토리={total_user_items}, 주문={total_orders}"
        )
