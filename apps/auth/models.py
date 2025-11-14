"""
User model for authentication
"""
import enum
from datetime import datetime
from werkzeug.security import check_password_hash, generate_password_hash
from sqlalchemy import func
from apps.config.server import db


class OauthType(enum.Enum):
    """OAuth provider types"""
    NONE = "NONE"
    KAKAO = "KAKAO"
    NAVER = "NAVER"
    GOOGLE = "GOOGLE"


class AccountType(enum.Enum):
    """Account privilege levels"""
    USER = "USER"
    ADMIN = "ADMIN"


class User(db.Model):
    """User model"""
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
    account_type = db.Column(db.Enum(AccountType), nullable=False, default=AccountType.USER)
    
    # Statistics
    follower_count = db.Column(db.Integer, default=0)
    
    # Relationships (to be defined in respective modules)
    # posts = db.relationship("Post", backref="author", lazy=True)
    # replies = db.relationship("Reply", backref="author", lazy=True)
    
    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verify password"""
        return check_password_hash(self.password_hash, password)
    
    def renew_login(self):
        """Update last login timestamp"""
        self.last_login = datetime.now()
    
    def calculate_follower(self):
        """Calculate follower count"""
        from apps.user.models import Follow
        self.follower_count = (
            db.session.query(func.count())
            .select_from(Follow)
            .join(User, Follow.follower_id == User.user_id)
            .filter(Follow.following_id == self.user_id)
            .scalar()
        )
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "nickname": self.nickname,
            "email": self.email,
            "address": self.address,
            "profile_img": self.profile_img,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "account_type": self.account_type.name,
            "oauth_type": self.oauth_type.name,
            "follower_count": self.follower_count,
        }
    
    def __repr__(self):
        return f'<User {self.username}>'
