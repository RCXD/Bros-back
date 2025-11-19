"""
피드 모델
"""
from datetime import datetime
from typing import Optional, List
from apps.config.server import db


class FeedItem(db.Model):
    """피드 아이템 모델"""
    __tablename__ = 'feed_items'
    
    feed_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    feed_type = db.Column(db.String(20), nullable=False)  # mention, friend_post, comment, reply, recommended
    related_post_id = db.Column(db.Integer, db.ForeignKey('posts.post_id'))
    related_reply_id = db.Column(db.Integer, db.ForeignKey('replies.reply_id'))
    related_user_id = db.Column(db.Integer, db.ForeignKey('users.user_id'))
    created_at = db.Column(db.DateTime, default=datetime.now)
    is_read = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        """딕셔너리로 변환"""
        return {
            "feed_id": self.feed_id,
            "user_id": self.user_id,
            "feed_type": self.feed_type,
            "related_post_id": self.related_post_id,
            "related_reply_id": self.related_reply_id,
            "related_user_id": self.related_user_id,
            "created_at": self.created_at.isoformat(),
            "is_read": self.is_read
        }


class FeedManager:
    """피드 관리 헬퍼 클래스"""
    
    @staticmethod
    def create_mention_feed(user_id: int, from_user_id: int, post_id: int = None, reply_id: int = None) -> FeedItem:
        """
        멘션 피드 생성
        
        Args:
            user_id: 멘션된 사용자 ID
            from_user_id: 멘션한 사용자 ID
            post_id: 게시글 ID (선택)
            reply_id: 댓글 ID (선택)
        """
        feed_item = FeedItem(
            user_id=user_id,
            feed_type='mention',
            related_post_id=post_id,
            related_reply_id=reply_id,
            related_user_id=from_user_id
        )
        db.session.add(feed_item)
        db.session.commit()
        return feed_item
    
    @staticmethod
    def create_friend_activity_feed(friend_id: int, post_id: int, post_user_id: int) -> FeedItem:
        """
        친구의 게시글 활동 피드 생성
        
        Args:
            friend_id: 친구의 사용자 ID
            post_id: 게시글 ID
            post_user_id: 게시글 작성자 ID
        """
        feed_item = FeedItem(
            user_id=friend_id,
            feed_type='friend_post',
            related_post_id=post_id,
            related_user_id=post_user_id
        )
        db.session.add(feed_item)
        db.session.commit()
        return feed_item
    
    @staticmethod
    def create_reply_feed(post_owner_id: int, reply_id: int, post_id: int, reply_user_id: int, is_nested: bool = False) -> FeedItem:
        """
        댓글/대댓글 피드 생성
        
        Args:
            post_owner_id: 게시글 소유자 ID
            reply_id: 댓글 ID
            post_id: 게시글 ID
            reply_user_id: 댓글 작성자 ID
            is_nested: 대댓글 여부
        """
        feed_type = 'nested_reply' if is_nested else 'reply'
        feed_item = FeedItem(
            user_id=post_owner_id,
            feed_type=feed_type,
            related_post_id=post_id,
            related_reply_id=reply_id,
            related_user_id=reply_user_id
        )
        db.session.add(feed_item)
        db.session.commit()
        return feed_item
    
    @staticmethod
    def create_recommended_feed(user_id: int, post_id: int, post_user_id: int) -> FeedItem:
        """
        추천 게시글 피드 생성
        
        Args:
            user_id: 사용자 ID
            post_id: 추천 게시글 ID
            post_user_id: 게시글 작성자 ID
        """
        feed_item = FeedItem(
            user_id=user_id,
            feed_type='recommended',
            related_post_id=post_id,
            related_user_id=post_user_id
        )
        db.session.add(feed_item)
        db.session.commit()
        return feed_item
    
    @staticmethod
    def get_user_feed(user_id: int, limit: int = 50, offset: int = 0) -> List[FeedItem]:
        """
        사용자의 피드 조회
        
        Args:
            user_id: 사용자 ID
            limit: 조회 개수
            offset: 오프셋
        """
        return FeedItem.query.filter_by(user_id=user_id)\
            .order_by(FeedItem.created_at.desc())\
            .limit(limit)\
            .offset(offset)\
            .all()
    
    @staticmethod
    def mark_as_read(feed_id: int) -> bool:
        """
        피드 항목을 읽음 처리
        
        Args:
            feed_id: 피드 ID
        """
        feed_item = FeedItem.query.get(feed_id)
        if feed_item:
            feed_item.is_read = True
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def mark_all_as_read(user_id: int) -> int:
        """
        사용자의 모든 피드를 읽음 처리
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            업데이트된 피드 개수
        """
        count = FeedItem.query.filter_by(user_id=user_id, is_read=False)\
            .update({FeedItem.is_read: True})
        db.session.commit()
        return count
    
    @staticmethod
    def get_unread_count(user_id: int) -> int:
        """
        사용자의 읽지 않은 피드 개수 조회
        
        Args:
            user_id: 사용자 ID
        """
        return FeedItem.query.filter_by(user_id=user_id, is_read=False).count()
