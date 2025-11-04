from flask import Blueprint, request, jsonify
from ..models import Reply
from ..extensions import db
from flask_jwt_extended import jwt_required, get_jwt_identity
import base64
from datetime import datetime

bp = Blueprint('replies', __name__)

