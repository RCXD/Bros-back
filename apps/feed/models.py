from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from apps.config.server import db


class FeedItem(db.Model):
  __tablename__ = 'feed_items'
  
  id = Column(Integer, primary_key=True)
  user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
  feed_type = Column(String(20), nullable=False)  # mention, friend_post, comment, reply, recommended
  related_post_id = Column(Integer, ForeignKey('posts.id'))
  related_comment_id = Column(Integer, ForeignKey('comments.id'))
  related_user_id = Column(Integer, ForeignKey('users.id'))
  created_at = Column(DateTime, default=datetime.utcnow)
  is_read = Column(Boolean, default=False)


class FeedManager:
  @staticmethod
  def create_mention_feed(user_id: int, from_user_id: int, post_id: int = None, comment_id: int = None) -> FeedItem:
    """친구의 멘션 피드 생성"""
    feed_item = FeedItem(
      user_id=user_id,
      feed_type='mention',
      related_post_id=post_id,
      related_comment_id=comment_id,
      related_user_id=from_user_id
    )
    db.session.add(feed_item)
    db.session.commit()
    return feed_item
  
  @staticmethod
  def create_friend_activity_feed(friend_id: int, post_id: int, post_user_id: int) -> FeedItem:
    """친구의 게시글 활동 피드 생성"""
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
  def create_comment_feed(post_owner_id: int, comment_id: int, post_id: int, comment_user_id: int, is_reply: bool = False) -> FeedItem:
    """내 게시글에 대한 댓글/대댓글 피드 생성"""
    feed_type = 'reply' if is_reply else 'comment'
    feed_item = FeedItem(
      user_id=post_owner_id,
      feed_type=feed_type,
      related_post_id=post_id,
      related_comment_id=comment_id,
      related_user_id=comment_user_id
    )
    db.session.add(feed_item)
    db.session.commit()
    return feed_item
  
  @staticmethod
  def create_recommended_feed(user_id: int, post_id: int, post_user_id: int) -> FeedItem:
    """추천 게시글 피드 생성 (카테고리 기반)"""
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
  def get_user_feed(user_id: int, limit: int = 50) -> List[FeedItem]:
    """사용자의 피드 조회"""
    return FeedItem.query.filter_by(user_id=user_id)\
      .order_by(FeedItem.created_at.desc())\
      .limit(limit).all()
  
  @staticmethod
  def mark_as_read(feed_item_id: int) -> bool:
    """피드 항목을 읽음 처리"""
    feed_item = FeedItem.query.get(feed_item_id)
    if feed_item:
      feed_item.is_read = True
      db.session.commit()
      return True
    return False
