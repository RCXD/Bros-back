"""
검색 관련 모델
"""

from datetime import datetime
from apps.config.server import db


class SearchHistory(db.Model):
    """검색 기록 모델"""

    __tablename__ = "search_history"

    search_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False
    )
    search_query = db.Column(db.String(500), nullable=False)
    search_type = db.Column(
        db.String(50), nullable=False
    )  # post, user, product, notification, etc.
    result_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.now)

    # 관계 설정
    user = db.relationship("User", backref=db.backref("search_history", lazy="dynamic"))

    __table_args__ = (
        db.Index("idx_search_user", "user_id", "created_at"),
        db.Index("idx_search_query", "search_query"),
    )

    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            "search_id": self.search_id,
            "user_id": self.user_id,
            "search_query": self.search_query,
            "search_type": self.search_type,
            "result_count": self.result_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SearchCache(db.Model):
    """검색 결과 캐싱 모델 (인기 검색어 등)"""

    __tablename__ = "search_cache"

    cache_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    search_query = db.Column(db.String(500), nullable=False, unique=True)
    search_type = db.Column(db.String(50), nullable=False)
    search_count = db.Column(db.Integer, default=1)
    last_searched_at = db.Column(db.DateTime, default=datetime.now)
    created_at = db.Column(db.DateTime, default=datetime.now)

    __table_args__ = (
        db.Index("idx_cache_type_count", "search_type", "search_count"),
        db.Index("idx_cache_query", "search_query"),
    )

    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            "cache_id": self.cache_id,
            "search_query": self.search_query,
            "search_type": self.search_type,
            "search_count": self.search_count,
            "last_searched_at": (
                self.last_searched_at.isoformat() if self.last_searched_at else None
            ),
        }

    @staticmethod
    def increment_search_count(query, search_type):
        """검색 횟수 증가"""
        cache = SearchCache.query.filter_by(
            search_query=query, search_type=search_type
        ).first()

        if cache:
            cache.search_count += 1
            cache.last_searched_at = datetime.now()
        else:
            cache = SearchCache(
                search_query=query,
                search_type=search_type,
                search_count=1,
                last_searched_at=datetime.now(),
            )
            db.session.add(cache)

        db.session.commit()
        return cache

    @staticmethod
    def get_popular_searches(search_type=None, limit=10):
        """인기 검색어 조회"""
        query = SearchCache.query

        if search_type:
            query = query.filter_by(search_type=search_type)

        return query.order_by(SearchCache.search_count.desc()).limit(limit).all()
