# apps/cosmetic/seed.py

import click
from datetime import datetime
from pathlib import Path
from flask.cli import with_appcontext

from apps.auth.models import AccountType, User
from apps.config.server import db
from apps.cosmetic.models import CosmeticItem, ItemType, UserItem
from apps.payment.models import Order


def _bulk_import_presets(presets):
    """Auto import preset items and save to DB fast.

    - Converts string types to ItemType enum
    - Skips items whose name already exists (name is unique)
    - Uses a single SELECT and bulk_save_objects for speed
    Returns (created_count, skipped_count)
    """
    if not presets:
        return 0, 0

    # Unique by name (model enforces unique=True on name)
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
            # Invalid type; skip
            skipped += 1
            continue

        to_create.append(
            CosmeticItem(
                type=itype,
                name=name,
                price=int(data.get("price") or 0),
                rarity=data.get("rarity"),
                image_path=data.get("image_path"),
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


STATIC_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
COSMETIC_STATIC_ROOT = Path(__file__).resolve().parents[1] / "static"


def _collect_cosmetic_image_paths():
    if not COSMETIC_STATIC_ROOT.is_dir():
        return {}

    image_paths = {}

    def _register(path: Path):
        if not path.is_file():
            return
        suffix = path.suffix.lower()
        if suffix not in STATIC_IMAGE_EXTENSIONS:
            return
        name = path.stem.strip().lower()
        if not name or name in image_paths:
            return
        image_paths[name] = path.relative_to(COSMETIC_STATIC_ROOT).as_posix()

    for entry in COSMETIC_STATIC_ROOT.iterdir():
        _register(entry)

    for entry in COSMETIC_STATIC_ROOT.iterdir():
        if not entry.is_dir() or not entry.name.startswith("cosmetic"):
            continue
        for path in entry.rglob("*"):
            _register(path)

    return image_paths


def _apply_static_image_paths(presets):
    image_map = _collect_cosmetic_image_paths()
    if not image_map:
        return
    for item in presets:
        if item.get("image_path"):
            continue
        name = (item.get("name") or "").strip().lower()
        if not name:
            continue
        resolved = image_map.get(name)
        if resolved:
            item["image_path"] = resolved


def _seed_admin_inventory_demo():
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


BORDER_PRESETS = [
    {
        "type": "border",
        "name": "nitro",
        "price": 0,
        "rarity": "epic",
        "theme_color": "#ff73fa",
        "image_path": None,
        "description": "Discord Nitro 스타일 그라디언트 링",
    },
    {
        "type": "border",
        "name": "glow_purple",
        "price": 1500,
        "rarity": "rare",
        "theme_color": "#a855f7",
        "image_path": None,
        "description": "보라색 소프트 글로우 링",
    },
    {
        "type": "border",
        "name": "glow_cyan",
        "price": 1500,
        "rarity": "rare",
        "theme_color": "#22d3ee",
        "image_path": None,
        "description": "시안 컬러 글로우 링",
    },
    {
        "type": "border",
        "name": "neon_pink",
        "price": 2000,
        "rarity": "epic",
        "theme_color": "#ff4fd8",
        "image_path": None,
        "description": "강한 네온 핑크 라인",
    },
    {
        "type": "border",
        "name": "double_gold",
        "price": 2500,
        "rarity": "legendary",
        "theme_color": "#facc15",
        "image_path": None,
        "description": "이중 금색 링",
    },
    {
        "type": "border",
        "name": "dashed_blue",
        "price": 800,
        "rarity": "uncommon",
        "theme_color": "#3b82f6",
        "image_path": None,
        "description": "푸른 점선 스타일 링",
    },
    {
        "type": "border",
        "name": "rainbow_cycle",
        "price": 3000,
        "rarity": "legendary",
        "theme_color": "#ffffff",
        "image_path": None,
        "description": "무지개 애니메이션 링",
    },
]

OVERLAY_PRESETS = [
    {
        "type": "overlay",
        "name": "sparkles_pink",
        "price": 1200,
        "rarity": "rare",
        "theme_color": "#f472b6",
        "image_path": None,
        "description": "핑크 반짝이 입자",
    },
    {
        "type": "overlay",
        "name": "sparkles_blue",
        "price": 1200,
        "rarity": "rare",
        "theme_color": "#60a5fa",
        "image_path": None,
        "description": "블루 반짝이 입자",
    },
    {
        "type": "overlay",
        "name": "flame_orange",
        "price": 1800,
        "rarity": "epic",
        "theme_color": "#fb923c",
        "image_path": None,
        "description": "주황색 화염 효과",
    },
    {
        "type": "overlay",
        "name": "flame_purple",
        "price": 1800,
        "rarity": "epic",
        "theme_color": "#a855f7",
        "image_path": None,
        "description": "보라색 마법 화염 효과",
    },
    {
        "type": "overlay",
        "name": "wing_white",
        "price": 2200,
        "rarity": "legendary",
        "theme_color": "#e5e7eb",
        "image_path": None,
        "description": "양 옆으로 펼쳐지는 흰색 날개 효과",
    },
    {
        "type": "overlay",
        "name": "wing_dark",
        "price": 2200,
        "rarity": "legendary",
        "theme_color": "#111827",
        "image_path": None,
        "description": "어두운 날개 실루엣 효과",
    },
    {
        "type": "overlay",
        "name": "shards_ice",
        "price": 1600,
        "rarity": "epic",
        "theme_color": "#67e8f9",
        "image_path": None,
        "description": "얼음 파편이 튀는 느낌의 효과",
    },
]

EFFECT_PRESETS = [
    {
        "type": "effect",
        "name": "pulse",
        "price": 900,
        "rarity": "uncommon",
        "theme_color": None,
        "image_path": None,
        "description": "서서히 커졌다 작아지는 펄스 효과",
    },
    {
        "type": "effect",
        "name": "float",
        "price": 900,
        "rarity": "uncommon",
        "theme_color": None,
        "image_path": None,
        "description": "위아래로 부유하는 효과",
    },
    {
        "type": "effect",
        "name": "shake",
        "price": 900,
        "rarity": "uncommon",
        "theme_color": None,
        "image_path": None,
        "description": "살짝 떨리는 흔들림 효과",
    },
    {
        "type": "effect",
        "name": "spin_slow",
        "price": 1400,
        "rarity": "rare",
        "theme_color": None,
        "image_path": None,
        "description": "천천히 회전하는 효과",
    },
    {
        "type": "effect",
        "name": "bounce_soft",
        "price": 1400,
        "rarity": "rare",
        "theme_color": None,
        "image_path": None,
        "description": "부드러운 튕김 애니메이션",
    },
    {
        "type": "effect",
        "name": "breathe",
        "price": 1400,
        "rarity": "rare",
        "theme_color": None,
        "image_path": None,
        "description": "호흡하듯 밝기가 변하는 효과",
    },
]


PRESET_ITEMS = BORDER_PRESETS + OVERLAY_PRESETS + EFFECT_PRESETS
_apply_static_image_paths(PRESET_ITEMS)


@click.command("seed_cosmetics")
@with_appcontext
def seed_cosmetics():
    """
    기본 코스메틱 프리셋을 DB에 삽입하는 커맨드.
    name이 이미 존재하면 건너뜀. 대량 삽입 최적화 사용.
    """
    created, skipped = _bulk_import_presets(PRESET_ITEMS)
    click.echo(f"Cosmetic presets: created={created}, skipped={skipped}")
    admin_count, inventory_added, purchase_demo, sale_demo = (
        _seed_admin_inventory_demo()
    )
    if not admin_count:
        click.echo("Admin cosmetics demo: no admin accounts detected.")
    else:
        click.echo(
            "Admin cosmetics demo: "
            f"admins={admin_count}, inventory_added={inventory_added}, "
            f"purchase_demo={purchase_demo}, sale_demo={sale_demo}"
        )
