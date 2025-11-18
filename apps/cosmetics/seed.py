# apps/cosmetic/seed.py

import click
from flask.cli import with_appcontext

from apps.config.server import db
from apps.cosmetics.models import CosmeticItem


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


@click.command("seed_cosmetics")
@with_appcontext
def seed_cosmetics():
    """
    기본 코스메틱 20종을 DB에 삽입하는 커맨드.
    type + name 조합이 이미 있으면 건너뜀.
    """
    created = 0
    skipped = 0

    for data in PRESET_ITEMS:
        exists = CosmeticItem.query.filter_by(
            type=data["type"],
            name=data["name"],
        ).first()

        if exists:
            skipped += 1
            continue

        item = CosmeticItem(
            type=data["type"],
            name=data["name"],
            price=data["price"],
            rarity=data["rarity"],
            image_path=data["image_path"],
            theme_color=data["theme_color"],
            description=data["description"],
        )
        db.session.add(item)
        created += 1

    db.session.commit()
    click.echo(f"Cosmetic presets: created={created}, skipped={skipped}")
