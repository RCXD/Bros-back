"""
리워드 포인트 유틸리티

사용자 활동에 따른 포인트 지급 시스템
설정은 apps/config/store_reward_control.json에서 관리
"""

import json
import os
from datetime import datetime, date
from functools import lru_cache
from typing import Optional, Dict, Any, Tuple

from apps.config.server import db
from apps.auth.models import User


# =============================================================================
# 설정 로드
# =============================================================================

_config_path = os.path.join(
    os.path.dirname(__file__), "..", "config", "store_reward_control.json"
)


def _load_config() -> Dict[str, Any]:
    """설정 파일 로드 (캐시 없이 항상 최신 로드)"""
    try:
        with open(_config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"[Reward] 설정 로드 실패: {e}")
        return {"enabled": False}


def get_config() -> Dict[str, Any]:
    """현재 리워드 설정 반환"""
    return _load_config()


def is_enabled() -> bool:
    """리워드 시스템 활성화 여부"""
    return get_config().get("enabled", False)


# =============================================================================
# 일일 제한 추적 (메모리 기반 - 프로덕션에서는 Redis 권장)
# =============================================================================

_daily_rewards: Dict[str, Dict[int, Dict[str, int]]] = {}


def _get_today_key() -> str:
    """오늘 날짜 키"""
    return date.today().isoformat()


def _get_user_daily_rewards(user_id: int, action: str) -> int:
    """사용자의 오늘 특정 액션 리워드 횟수"""
    today = _get_today_key()
    if today not in _daily_rewards:
        _daily_rewards.clear()  # 날짜 변경 시 초기화
        _daily_rewards[today] = {}

    if user_id not in _daily_rewards[today]:
        _daily_rewards[today][user_id] = {}

    return _daily_rewards[today][user_id].get(action, 0)


def _increment_daily_reward(user_id: int, action: str) -> None:
    """사용자의 오늘 특정 액션 리워드 횟수 증가"""
    today = _get_today_key()
    if today not in _daily_rewards:
        _daily_rewards.clear()
        _daily_rewards[today] = {}

    if user_id not in _daily_rewards[today]:
        _daily_rewards[today][user_id] = {}

    _daily_rewards[today][user_id][action] = (
        _daily_rewards[today][user_id].get(action, 0) + 1
    )


def _get_user_daily_total(user_id: int) -> int:
    """사용자의 오늘 총 획득 포인트"""
    today = _get_today_key()
    if today not in _daily_rewards or user_id not in _daily_rewards[today]:
        return 0

    return _daily_rewards[today][user_id].get("_total_points", 0)


def _add_daily_total(user_id: int, points: int) -> None:
    """사용자의 오늘 총 획득 포인트에 추가"""
    today = _get_today_key()
    if today not in _daily_rewards:
        _daily_rewards.clear()
        _daily_rewards[today] = {}

    if user_id not in _daily_rewards[today]:
        _daily_rewards[today][user_id] = {}

    _daily_rewards[today][user_id]["_total_points"] = (
        _daily_rewards[today][user_id].get("_total_points", 0) + points
    )


# =============================================================================
# 조회수 리워드 추적
# =============================================================================

_view_thresholds_achieved: Dict[int, set] = {}  # post_id -> achieved thresholds


def _get_achieved_thresholds(post_id: int) -> set:
    """게시글의 달성된 조회수 임계값들"""
    return _view_thresholds_achieved.get(post_id, set())


def _mark_threshold_achieved(post_id: int, threshold: int) -> None:
    """조회수 임계값 달성 기록"""
    if post_id not in _view_thresholds_achieved:
        _view_thresholds_achieved[post_id] = set()
    _view_thresholds_achieved[post_id].add(threshold)


# =============================================================================
# 포인트 지급 핵심 함수
# =============================================================================


def grant_points(
    user_id: int, points: int, reason: str, commit: bool = True
) -> Tuple[bool, int, str]:
    """
    사용자에게 포인트 지급

    Args:
        user_id: 대상 사용자 ID
        points: 지급할 포인트
        reason: 지급 사유 (로그용)
        commit: DB 커밋 여부

    Returns:
        (성공 여부, 실제 지급 포인트, 메시지)
    """
    if points <= 0:
        return False, 0, "포인트는 양수여야 합니다"

    config = get_config()
    if not config.get("enabled", False):
        return False, 0, "리워드 시스템 비활성화"

    # 일일 최대 포인트 체크
    daily_config = config.get("daily_limits", {})
    if daily_config.get("enabled", False):
        max_daily = daily_config.get("max_points_per_day", 500)
        current_daily = _get_user_daily_total(user_id)

        if current_daily >= max_daily:
            return False, 0, "일일 최대 포인트 도달"

        # 초과분 조정
        if current_daily + points > max_daily:
            points = max_daily - current_daily

    # 보너스 배율 적용
    bonus = config.get("bonus_multipliers", {})
    if bonus.get("enabled", False):
        multiplier = bonus.get("current_multiplier", 1.0)
        points = int(points * multiplier)

    # 포인트 지급
    user = User.query.get(user_id)
    if not user:
        return False, 0, "사용자를 찾을 수 없습니다"

    user.points += points
    _add_daily_total(user_id, points)

    if commit:
        db.session.commit()

    if config.get("debug_mode", False):
        print(f"[Reward] {user.username}({user_id}): +{points}pt ({reason})")

    return True, points, f"{points} 포인트 지급 완료"




# =============================================================================
# 액션별 리워드 함수
# =============================================================================


def reward_post_like_received(
    post_author_id: int, category: str = "default", commit: bool = True
) -> Tuple[bool, int, str]:
    """게시글에 좋아요를 받았을 때 (게시글 작성자에게 지급)"""
    config = get_config()
    action_config = config.get("action_rewards", {}).get("post_like_received", {})

    if not action_config.get("enabled", False):
        return False, 0, "비활성화됨"

    # 일일 제한 체크
    daily_limit = action_config.get("daily_limit", 50)
    current_count = _get_user_daily_rewards(post_author_id, "post_like_received")
    if current_count >= daily_limit:
        return False, 0, "일일 제한 도달"

    # 포인트 계산 (카테고리 배율 적용)
    base_points = action_config.get("points", 2)
    multipliers = action_config.get("category_multipliers", {})
    multiplier = multipliers.get(category, multipliers.get("default", 1.0))
    points = int(base_points * multiplier)

    _increment_daily_reward(post_author_id, "post_like_received")
    return grant_points(
        post_author_id, points, f"게시글 좋아요 받음 ({category})", commit
    )


def reward_post_like_given(
    liker_user_id: int, commit: bool = True
) -> Tuple[bool, int, str]:
    """게시글에 좋아요를 눌렀을 때 (좋아요 누른 사람에게 지급)"""
    config = get_config()
    action_config = config.get("action_rewards", {}).get("post_like_given", {})

    if not action_config.get("enabled", False):
        return False, 0, "비활성화됨"

    daily_limit = action_config.get("daily_limit", 20)
    current_count = _get_user_daily_rewards(liker_user_id, "post_like_given")
    if current_count >= daily_limit:
        return False, 0, "일일 제한 도달"

    points = action_config.get("points", 1)
    _increment_daily_reward(liker_user_id, "post_like_given")
    return grant_points(liker_user_id, points, "게시글 좋아요 누름", commit)


def reward_reply_created(
    author_user_id: int, commit: bool = True
) -> Tuple[bool, int, str]:
    """댓글을 작성했을 때"""
    config = get_config()
    action_config = config.get("action_rewards", {}).get("reply_created", {})

    if not action_config.get("enabled", False):
        return False, 0, "비활성화됨"

    daily_limit = action_config.get("daily_limit", 30)
    current_count = _get_user_daily_rewards(author_user_id, "reply_created")
    if current_count >= daily_limit:
        return False, 0, "일일 제한 도달"

    points = action_config.get("points", 3)
    _increment_daily_reward(author_user_id, "reply_created")
    return grant_points(author_user_id, points, "댓글 작성", commit)


def reward_reply_received(
    post_author_id: int, commit: bool = True
) -> Tuple[bool, int, str]:
    """내 게시글에 댓글이 달렸을 때 (게시글 작성자에게 지급)"""
    config = get_config()
    action_config = config.get("action_rewards", {}).get("reply_received", {})

    if not action_config.get("enabled", False):
        return False, 0, "비활성화됨"

    daily_limit = action_config.get("daily_limit", 50)
    current_count = _get_user_daily_rewards(post_author_id, "reply_received")
    if current_count >= daily_limit:
        return False, 0, "일일 제한 도달"

    points = action_config.get("points", 2)
    _increment_daily_reward(post_author_id, "reply_received")
    return grant_points(post_author_id, points, "게시글에 댓글 받음", commit)


def reward_nested_reply_created(
    author_user_id: int, commit: bool = True
) -> Tuple[bool, int, str]:
    """대댓글을 작성했을 때"""
    config = get_config()
    action_config = config.get("action_rewards", {}).get("nested_reply_created", {})

    if not action_config.get("enabled", False):
        return False, 0, "비활성화됨"

    daily_limit = action_config.get("daily_limit", 30)
    current_count = _get_user_daily_rewards(author_user_id, "nested_reply_created")
    if current_count >= daily_limit:
        return False, 0, "일일 제한 도달"

    points = action_config.get("points", 2)
    _increment_daily_reward(author_user_id, "nested_reply_created")
    return grant_points(author_user_id, points, "대댓글 작성", commit)


def reward_nested_reply_received(
    reply_author_id: int, commit: bool = True
) -> Tuple[bool, int, str]:
    """내 댓글에 대댓글이 달렸을 때 (댓글 작성자에게 지급)"""
    config = get_config()
    action_config = config.get("action_rewards", {}).get("nested_reply_received", {})

    if not action_config.get("enabled", False):
        return False, 0, "비활성화됨"

    daily_limit = action_config.get("daily_limit", 50)
    current_count = _get_user_daily_rewards(reply_author_id, "nested_reply_received")
    if current_count >= daily_limit:
        return False, 0, "일일 제한 도달"

    points = action_config.get("points", 1)
    _increment_daily_reward(reply_author_id, "nested_reply_received")
    return grant_points(reply_author_id, points, "대댓글 받음", commit)


def reward_reply_like_received(
    reply_author_id: int, commit: bool = True
) -> Tuple[bool, int, str]:
    """내 댓글이 좋아요를 받았을 때"""
    config = get_config()
    action_config = config.get("action_rewards", {}).get("reply_like_received", {})

    if not action_config.get("enabled", False):
        return False, 0, "비활성화됨"

    daily_limit = action_config.get("daily_limit", 30)
    current_count = _get_user_daily_rewards(reply_author_id, "reply_like_received")
    if current_count >= daily_limit:
        return False, 0, "일일 제한 도달"

    points = action_config.get("points", 1)
    _increment_daily_reward(reply_author_id, "reply_like_received")
    return grant_points(reply_author_id, points, "댓글 좋아요 받음", commit)


def reward_reply_like_given(
    liker_user_id: int, commit: bool = True
) -> Tuple[bool, int, str]:
    """댓글에 좋아요를 눌렀을 때"""
    config = get_config()
    action_config = config.get("action_rewards", {}).get("reply_like_given", {})

    if not action_config.get("enabled", False):
        return False, 0, "비활성화됨"

    daily_limit = action_config.get("daily_limit", 20)
    current_count = _get_user_daily_rewards(liker_user_id, "reply_like_given")
    if current_count >= daily_limit:
        return False, 0, "일일 제한 도달"

    points = action_config.get("points", 1)
    _increment_daily_reward(liker_user_id, "reply_like_given")
    return grant_points(liker_user_id, points, "댓글 좋아요 누름", commit)


def reward_post_shared(
    post_author_id: int, commit: bool = True
) -> Tuple[bool, int, str]:
    """게시글이 공유되었을 때 (게시글 작성자에게 지급)"""
    config = get_config()
    action_config = config.get("action_rewards", {}).get("post_shared", {})

    if not action_config.get("enabled", False):
        return False, 0, "비활성화됨"

    daily_limit = action_config.get("daily_limit", 20)
    current_count = _get_user_daily_rewards(post_author_id, "post_shared")
    if current_count >= daily_limit:
        return False, 0, "일일 제한 도달"

    points = action_config.get("points", 5)
    _increment_daily_reward(post_author_id, "post_shared")
    return grant_points(post_author_id, points, "게시글 공유됨", commit)


def reward_follower_gained(
    followed_user_id: int, commit: bool = True
) -> Tuple[bool, int, str]:
    """다른 사람이 나를 팔로우했을 때"""
    config = get_config()
    action_config = config.get("action_rewards", {}).get("follower_gained", {})

    if not action_config.get("enabled", False):
        return False, 0, "비활성화됨"

    daily_limit = action_config.get("daily_limit", 30)
    current_count = _get_user_daily_rewards(followed_user_id, "follower_gained")
    if current_count >= daily_limit:
        return False, 0, "일일 제한 도달"

    points = action_config.get("points", 5)
    _increment_daily_reward(followed_user_id, "follower_gained")
    return grant_points(followed_user_id, points, "팔로워 증가", commit)


def reward_follow_special_user(
    follower_user_id: int, target_user: User, commit: bool = True
) -> Tuple[bool, int, str]:
    """특정 조건의 유저를 팔로우했을 때"""
    config = get_config()
    action_config = config.get("action_rewards", {}).get("follow_special_user", {})

    if not action_config.get("enabled", False):
        return False, 0, "비활성화됨"

    # 조건 체크
    conditions = action_config.get("conditions", {})

    # 최소 팔로워 수 조건
    min_followers = conditions.get("min_follower_count", 0)
    if target_user.follower_count < min_followers:
        return False, 0, "대상 조건 미충족"

    # 계정 타입 조건
    allowed_types = conditions.get("account_types", [])
    if allowed_types and target_user.account_type.name not in allowed_types:
        return False, 0, "대상 조건 미충족"

    daily_limit = action_config.get("daily_limit", 5)
    current_count = _get_user_daily_rewards(follower_user_id, "follow_special_user")
    if current_count >= daily_limit:
        return False, 0, "일일 제한 도달"

    points = action_config.get("points", 10)
    _increment_daily_reward(follower_user_id, "follow_special_user")
    return grant_points(
        follower_user_id, points, f"특별 유저 팔로우 ({target_user.username})", commit
    )


# =============================================================================
# 조회수 기반 리워드
# =============================================================================


def reward_view_threshold(
    post_id: int,
    post_author_id: int,
    current_views: int,
    category: str = "default",
    commit: bool = True,
) -> Tuple[bool, int, str]:
    """
    조회수 임계값 도달 시 리워드

    Args:
        post_id: 게시글 ID
        post_author_id: 게시글 작성자 ID
        current_views: 현재 조회수
        category: 게시글 카테고리
        commit: DB 커밋 여부

    Returns:
        (성공 여부, 총 지급 포인트, 메시지)
    """
    config = get_config()
    view_config = config.get("view_rewards", {})

    if not view_config.get("enabled", False):
        return False, 0, "비활성화됨"

    achieved = _get_achieved_thresholds(post_id)
    thresholds = view_config.get("thresholds", [])
    category_multipliers = view_config.get("category_multipliers", {})
    multiplier = category_multipliers.get(
        category, category_multipliers.get("default", 1.0)
    )

    total_points = 0
    messages = []

    for threshold in thresholds:
        views_needed = threshold.get("views", 0)
        base_points = threshold.get("points", 0)
        one_time = threshold.get("one_time", True)

        if current_views >= views_needed:
            if one_time and views_needed in achieved:
                continue  # 이미 달성함

            points = int(base_points * multiplier)
            success, granted, msg = grant_points(
                post_author_id,
                points,
                f"조회수 {views_needed} 달성 (게시글 #{post_id})",
                commit=False,  # 나중에 한 번에 커밋
            )

            if success:
                total_points += granted
                messages.append(f"{views_needed}회 달성: +{granted}pt")
                if one_time:
                    _mark_threshold_achieved(post_id, views_needed)

    if commit and total_points > 0:
        db.session.commit()

    if total_points > 0:
        return True, total_points, "; ".join(messages)
    return False, 0, "달성한 임계값 없음"


def reward_view_incremental(
    post_id: int,
    post_author_id: int,
    old_views: int,
    new_views: int,
    category: str = "default",
    commit: bool = True,
) -> Tuple[bool, int, str]:
    """
    조회수 증가율 기반 리워드 (매 N회마다)

    Args:
        post_id: 게시글 ID
        post_author_id: 게시글 작성자 ID
        old_views: 이전 조회수
        new_views: 새 조회수
        category: 게시글 카테고리
        commit: DB 커밋 여부
    """
    config = get_config()
    view_config = config.get("view_rewards", {})
    incremental = view_config.get("incremental", {})

    if not incremental.get("enabled", False):
        return False, 0, "비활성화됨"

    every_n = incremental.get("every_n_views", 100)
    points_per = incremental.get("points_per_increment", 5)
    max_increments = incremental.get("max_increments_per_post", 50)

    # 카테고리 배율
    category_multipliers = view_config.get("category_multipliers", {})
    multiplier = category_multipliers.get(
        category, category_multipliers.get("default", 1.0)
    )

    # 몇 번의 증분이 발생했는지 계산
    old_increments = old_views // every_n
    new_increments = new_views // every_n

    # 최대 제한 적용
    old_increments = min(old_increments, max_increments)
    new_increments = min(new_increments, max_increments)

    increments_gained = new_increments - old_increments

    if increments_gained <= 0:
        return False, 0, "증분 없음"

    points = int(increments_gained * points_per * multiplier)
    return grant_points(
        post_author_id,
        points,
        f"조회수 증분 리워드 (게시글 #{post_id}, {increments_gained}회)",
        commit,
    )


# =============================================================================
# 제휴상품 구매 리워드 (미래 구현용)
# =============================================================================


def reward_product_purchase(
    buyer_user_id: int, purchase_amount: int, commit: bool = True
) -> Tuple[bool, int, str]:
    """
    제휴상품 구매 시 리워드 (미래 구현)

    Args:
        buyer_user_id: 구매자 ID
        purchase_amount: 구매 금액 (원)
        commit: DB 커밋 여부
    """
    config = get_config()
    action_config = config.get("action_rewards", {}).get("product_purchase", {})

    if not action_config.get("enabled", False):
        return False, 0, "비활성화됨"

    percentage = action_config.get("points_percentage", 1.0)
    min_points = action_config.get("min_points", 10)
    max_points = action_config.get("max_points", 1000)

    points = int(purchase_amount * percentage / 100)
    points = max(min_points, min(points, max_points))

    return grant_points(
        buyer_user_id, points, f"제휴상품 구매 ({purchase_amount}원)", commit
    )


# =============================================================================
# 유틸리티 함수
# =============================================================================


def get_user_reward_summary(user_id: int) -> Dict[str, Any]:
    """사용자의 오늘 리워드 요약"""
    today = _get_today_key()
    user_data = _daily_rewards.get(today, {}).get(user_id, {})

    config = get_config()
    daily_limit = config.get("daily_limits", {}).get("max_points_per_day", 500)

    return {
        "user_id": user_id,
        "date": today,
        "total_points_today": user_data.get("_total_points", 0),
        "daily_limit": daily_limit,
        "remaining": max(0, daily_limit - user_data.get("_total_points", 0)),
        "actions": {k: v for k, v in user_data.items() if not k.startswith("_")},
    }


def reload_config() -> Dict[str, Any]:
    """설정 다시 로드 (런타임 중 설정 변경 시 호출)"""
    return _load_config()


# =============================================================================
# 메달 시스템
# =============================================================================

# 메달 등급 정의 (포인트 기준)
MEDAL_TIERS = [
    {
        "id": "bronze",
        "name": "브론즈",
        "min_points": 0,
        "icon": "🥉",
        "color": "#CD7F32",
    },
    {
        "id": "silver",
        "name": "실버",
        "min_points": 500,
        "icon": "🥈",
        "color": "#C0C0C0",
    },
    {
        "id": "gold",
        "name": "골드",
        "min_points": 2000,
        "icon": "🥇",
        "color": "#FFD700",
    },
    {
        "id": "platinum",
        "name": "플래티넘",
        "min_points": 5000,
        "icon": "💎",
        "color": "#E5E4E2",
    },
    {
        "id": "diamond",
        "name": "다이아몬드",
        "min_points": 15000,
        "icon": "💠",
        "color": "#B9F2FF",
    },
    {
        "id": "master",
        "name": "마스터",
        "min_points": 50000,
        "icon": "👑",
        "color": "#9400D3",
    },
    {
        "id": "grandmaster",
        "name": "그랜드마스터",
        "min_points": 100000,
        "icon": "🏆",
        "color": "#FF4500",
    },
]


def get_medal_by_points(points: int) -> Dict[str, Any]:
    """
    포인트에 따른 메달 등급 반환

    Args:
        points: 사용자 보유 포인트

    Returns:
        메달 정보 딕셔너리
    """
    current_medal = MEDAL_TIERS[0]
    next_medal = None

    for i, tier in enumerate(MEDAL_TIERS):
        if points >= tier["min_points"]:
            current_medal = tier
            # 다음 메달 설정
            if i + 1 < len(MEDAL_TIERS):
                next_medal = MEDAL_TIERS[i + 1]
            else:
                next_medal = None
        else:
            break

    # 다음 메달까지 진행률 계산
    progress = 0.0
    points_to_next = 0

    if next_medal:
        range_start = current_medal["min_points"]
        range_end = next_medal["min_points"]
        points_in_range = points - range_start
        range_size = range_end - range_start
        progress = min(1.0, points_in_range / range_size) if range_size > 0 else 1.0
        points_to_next = range_end - points

    return {
        "current": {
            "id": current_medal["id"],
            "name": current_medal["name"],
            "icon": current_medal["icon"],
            "color": current_medal["color"],
            "min_points": current_medal["min_points"],
        },
        "next": (
            {
                "id": next_medal["id"],
                "name": next_medal["name"],
                "icon": next_medal["icon"],
                "min_points": next_medal["min_points"],
                "points_needed": points_to_next,
            }
            if next_medal
            else None
        ),
        "progress": round(progress, 3),
        "is_max_tier": next_medal is None,
    }


def get_user_medal(user_id: int) -> Dict[str, Any]:
    """
    사용자 ID로 메달 정보 조회

    Args:
        user_id: 사용자 ID

    Returns:
        메달 정보 딕셔너리
    """
    user = User.query.get(user_id)
    if not user:
        return get_medal_by_points(0)

    return get_medal_by_points(user.points)


def get_medal_summary(user_id: int) -> Dict[str, Any]:
    """
    사용자의 메달 요약 정보 (JWT claims용 간소화 버전)

    Args:
        user_id: 사용자 ID

    Returns:
        간소화된 메달 정보
    """
    user = User.query.get(user_id)
    points = user.points if user else 0
    medal = get_medal_by_points(points)

    return {
        "medal_id": medal["current"]["id"],
        "medal_name": medal["current"]["name"],
        "medal_icon": medal["current"]["icon"],
    }


# =============================================================================
# 리그 시스템 (미래 구현용 틀)
# =============================================================================

# 리그 정의 (시즌별 경쟁 - 미래 구현)
LEAGUE_TIERS = [
    {"id": "unranked", "name": "언랭크", "min_rank": None, "icon": "⚪", "rewards": {}},
    {
        "id": "bronze_league",
        "name": "브론즈 리그",
        "min_rank": 1000,
        "icon": "🟤",
        "rewards": {"points_bonus": 1.0},
    },
    {
        "id": "silver_league",
        "name": "실버 리그",
        "min_rank": 500,
        "icon": "⚪",
        "rewards": {"points_bonus": 1.1},
    },
    {
        "id": "gold_league",
        "name": "골드 리그",
        "min_rank": 200,
        "icon": "🟡",
        "rewards": {"points_bonus": 1.2},
    },
    {
        "id": "platinum_league",
        "name": "플래티넘 리그",
        "min_rank": 100,
        "icon": "🔵",
        "rewards": {"points_bonus": 1.3},
    },
    {
        "id": "diamond_league",
        "name": "다이아몬드 리그",
        "min_rank": 50,
        "icon": "💎",
        "rewards": {"points_bonus": 1.5},
    },
    {
        "id": "champion_league",
        "name": "챔피언 리그",
        "min_rank": 10,
        "icon": "🏆",
        "rewards": {"points_bonus": 2.0},
    },
]


class LeagueSystem:
    """
    리그 시스템 (미래 구현용 틀)

    시즌 기반 경쟁 시스템:
    - 매 시즌(예: 1개월) 리셋
    - 시즌 내 활동 포인트로 순위 결정
    - 시즌 종료 시 리그별 보상 지급
    """

    def __init__(self):
        self.enabled = False  # 미래 활성화 예정
        self.current_season = None
        self.season_start = None
        self.season_end = None

    def get_user_league(self, user_id: int) -> Dict[str, Any]:
        """사용자의 현재 리그 정보 (미구현)"""
        if not self.enabled:
            return {
                "enabled": False,
                "message": "리그 시스템 준비 중",
                "league": LEAGUE_TIERS[0],
            }

        # TODO: 실제 리그 계산 로직
        return {
            "enabled": True,
            "season": self.current_season,
            "league": LEAGUE_TIERS[0],
            "rank": None,
            "season_points": 0,
        }

    def get_leaderboard(self, limit: int = 100) -> list:
        """시즌 리더보드 (미구현)"""
        if not self.enabled:
            return []

        # TODO: 실제 리더보드 쿼리
        return []

    def process_season_end(self):
        """시즌 종료 처리 (미구현)"""
        if not self.enabled:
            return

        # TODO:
        # 1. 최종 순위 확정
        # 2. 리그별 보상 지급
        # 3. 시즌 데이터 아카이브
        # 4. 새 시즌 시작
        pass


# 리그 시스템 싱글톤 인스턴스
league_system = LeagueSystem()


def get_user_league_info(user_id: int) -> Dict[str, Any]:
    """사용자 리그 정보 조회 (외부 호출용)"""
    return league_system.get_user_league(user_id)


def revoke_points(
    user_id: int, points: int, reason: str, commit: bool = True
) -> Tuple[bool, int, str]:
    """
    사용자에게 포인트 회수

    Args:
        user_id: 대상 사용자 ID
        points: 회수할 포인트
        reason: 회수 사유 (로그용)
        commit: DB 커밋 여부

    Returns:
        (성공 여부, 실제 회수 포인트, 메시지)
    """
    try:
        if points <= 0:
            return False, 0, "포인트는 양수여야 합니다"

        config = get_config()
        if not config.get("enabled", False):
            return False, 0, "리워드 시스템 비활성화"

        # 포인트 지급
        user = User.query.get(user_id)
        if not user:
            return False, 0, "사용자를 찾을 수 없습니다"
        
        if user.point < points:
            raise ValueError({"message":"보유중인 포인트가 부족합니다"})
        
        user.points -= points

        if commit:
            db.session.commit()

        if config.get("debug_mode", False):
            print(f"[Reward] {user.username}({user_id}): +{points}pt ({reason})")
    except ValueError:
        return False, points, "구매에 실패했습니다"
    return True, points, f"{points} 포인트 반영 완료"