"""
검색 모듈
"""

from flask import Blueprint

bp = Blueprint("search", __name__, url_prefix="/search")

from apps.search import views
