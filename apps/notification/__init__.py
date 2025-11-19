"""
알림 모듈
"""
from apps.notification.models import Notification, NotificationType
from apps.notification.views import bp

__all__ = ["Notification", "NotificationType", "bp"]
