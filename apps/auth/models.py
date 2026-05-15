"""User model for authentication."""

import enum
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func
from apps.config.server import db


class OauthType(enum.Enum):
    """OAuth provider type used during social login."""

    NONE = "NONE"
    KAKAO = "KAKAO"
    NAVER = "NAVER"
    GOOGLE = "GOOGLE"


class AccountType(enum.Enum):
    """Account privilege level (regular user vs. administrator)."""

    USER = "USER"
    ADMIN = "ADMIN"


class User(db.Model):
    """SQLAlchemy model representing an application user.

    Stores authentication credentials, profile information, account
    status flags, and aggregate statistics (follower count, reward
    points).
    """

    __tablename__ = "users"

    # Primary key
    user_id = db.Column(db.Integer, primary_key=True)

    # Authentication
    username = db.Column(db.String(50), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)

    # Profile information
    nickname = db.Column(db.String(50))
    profile_img = db.Column(db.String(255))
    address = db.Column(db.String(255))
    phone = db.Column(db.String(20))

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.now)
    last_login = db.Column(db.DateTime, nullable=True, default=datetime.now)

    # Account status
    is_expired = db.Column(db.Boolean, nullable=False, default=False)
    oauth_type = db.Column(db.Enum(OauthType), nullable=False, default=OauthType.NONE)
    account_type = db.Column(
        db.Enum(AccountType), nullable=False, default=AccountType.USER
    )

    # Statistics
    follower_count = db.Column(db.Integer, default=0)

    # Points (cosmetic store 등에서 사용)
    points = db.Column(db.Integer, default=0, nullable=False)

    # Relationships (to be defined in respective modules)
    # posts = db.relationship("Post", backref="author", lazy=True)
    # replies = db.relationship("Reply", backref="author", lazy=True)

    def set_password(self, password: str) -> None:
        """Hash *password* and store it on the instance.

        Args:
            password: Plain-text password to hash.
        """
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Verify *password* against the stored hash.

        Args:
            password: Plain-text password to check.

        Returns:
            ``True`` if *password* matches the stored hash.
        """
        return check_password_hash(self.password_hash, password)

    def renew_login(self) -> None:
        """Update :attr:`last_login` to the current timestamp."""
        self.last_login = datetime.now()

    def calculate_follower(self) -> None:
        """Refresh :attr:`follower_count` from the ``Follow`` table."""
        from apps.user.models import Follow

        self.follower_count = (
            db.session.query(func.count())
            .select_from(Follow)
            .join(User, Follow.from_user_id == User.user_id)
            .filter(Follow.to_user_id == self.user_id)
            .scalar()
        )

    def to_dict(self) -> dict:
        """Serialise the user instance to a plain dictionary.

        Returns:
            Dictionary containing all public user fields suitable for
            JSON serialisation.
        """
        return {
            "user_id": self.user_id,
            "username": self.username,
            "nickname": self.nickname,
            "email": self.email,
            "address": self.address,
            "phone": self.phone,
            "profile_img": self.profile_img,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "account_type": self.account_type.name,
            "oauth_type": self.oauth_type.name,
            "follower_count": self.follower_count,
            "points": self.points,
        }

    def __repr__(self) -> str:
        return f"<User {self.username}>"
