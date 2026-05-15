"""
피드 모델
"""
from datetime import datetime
from typing import Optional, List
from apps.config.server import db


class FeedItem(db.Model):
    """Feed item model representing a single entry in a user's feed."""
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
        """Converts the feed item instance to a dictionary.

        Returns:
            A dict with feed_id, user_id, feed_type, related_post_id,
            related_reply_id, related_user_id, created_at, and is_read fields.
        """
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
    """Helper class for managing feed item creation and retrieval."""
    
    @staticmethod
    def create_mention_feed(user_id: int, from_user_id: int, post_id: int = None, reply_id: int = None) -> FeedItem:
        """Creates a feed item for a mention event.

        Args:
            user_id: ID of the user who was mentioned.
            from_user_id: ID of the user who created the mention.
            post_id: ID of the related post (optional).
            reply_id: ID of the related reply (optional).

        Returns:
            The newly created FeedItem instance.
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
        """Creates a feed item when a friend publishes a new post.

        Args:
            friend_id: ID of the friend (recipient) user.
            post_id: ID of the newly created post.
            post_user_id: ID of the user who authored the post.

        Returns:
            The newly created FeedItem instance.
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
        """Creates a feed item for a new reply or nested reply on a post.

        Args:
            post_owner_id: ID of the post owner who receives the feed entry.
            reply_id: ID of the newly created reply.
            post_id: ID of the post being replied to.
            reply_user_id: ID of the user who wrote the reply.
            is_nested: True if the reply is a nested reply; False for a top-level reply.

        Returns:
            The newly created FeedItem instance.
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
        """Creates a feed item for a recommended post.

        Args:
            user_id: ID of the user who receives the recommendation.
            post_id: ID of the recommended post.
            post_user_id: ID of the user who authored the recommended post.

        Returns:
            The newly created FeedItem instance.
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
        """Retrieves paginated feed items for a user, ordered by most recent.

        Args:
            user_id: ID of the user whose feed to retrieve.
            limit: Maximum number of feed items to return.
            offset: Number of feed items to skip before returning results.

        Returns:
            A list of FeedItem instances.
        """
        return FeedItem.query.filter_by(user_id=user_id)\
            .order_by(FeedItem.created_at.desc())\
            .limit(limit)\
            .offset(offset)\
            .all()
    
    @staticmethod
    def mark_as_read(feed_id: int) -> bool:
        """Marks a single feed item as read.

        Args:
            feed_id: ID of the feed item to mark as read.

        Returns:
            True if the feed item was found and updated; False otherwise.
        """
        feed_item = FeedItem.query.get(feed_id)
        if feed_item:
            feed_item.is_read = True
            db.session.commit()
            return True
        return False
    
    @staticmethod
    def mark_all_as_read(user_id: int) -> int:
        """Marks all unread feed items for a user as read.

        Args:
            user_id: ID of the user whose feed items should be marked as read.

        Returns:
            The number of feed items that were updated.
        """
        count = FeedItem.query.filter_by(user_id=user_id, is_read=False)\
            .update({FeedItem.is_read: True})
        db.session.commit()
        return count
    
    @staticmethod
    def get_unread_count(user_id: int) -> int:
        """Returns the number of unread feed items for a user.

        Args:
            user_id: ID of the user to check.

        Returns:
            Count of unread FeedItem records for the given user.
        """
        return FeedItem.query.filter_by(user_id=user_id, is_read=False).count()
