from flask import Blueprint, request, jsonify
from ..extensions import db
from ..models.my_path import MyPath
from flask_jwt_extended import jwt_required, get_jwt_identity

bp = Blueprint("my_path", __name__)

# ---------------- 1. 경로 저장 ----------------
@bp.route("", methods=["POST"])
@jwt_required()
def save_path():
    user_id = get_jwt_identity()
    data = request.get_json()

    path_name = data.get("path_name", "나의 경로")
    points = data.get("points")

    if not points or not isinstance(points, list):
        return jsonify({"message": "points 형식이 올바르지 않습니다."}), 400

    path = MyPath(user_id=user_id, path_name=path_name, points=points)
    db.session.add(path)
    db.session.commit()

    return jsonify({"message": "경로 저장 완료", "path_id": path.path_id}), 200


# ---------------- 2. 내 경로 목록 ----------------
@bp.route("/me", methods=["GET"])
@jwt_required()
def list_paths():
    user_id = get_jwt_identity()
    paths = MyPath.query.filter_by(user_id=user_id).all()
    return jsonify([p.serialize() for p in paths]), 200


# ---------------- 3. 경로 상세 조회 ----------------
@bp.route("/<int:path_id>", methods=["GET"])
@jwt_required()
def get_path(path_id):
    user_id = get_jwt_identity()
    path = MyPath.query.filter_by(path_id=path_id, user_id=user_id).first()
    if not path:
        return jsonify({"message": "경로를 찾을 수 없습니다."}), 404
    return jsonify(path.serialize()), 200


# ---------------- 4. 경로 삭제 ----------------
@bp.route("/<int:path_id>", methods=["DELETE"])
@jwt_required()
def delete_path(path_id):
    user_id = get_jwt_identity()
    path = MyPath.query.filter_by(path_id=path_id, user_id=user_id).first()
    if not path:
        return jsonify({"message": "경로를 찾을 수 없습니다."}), 404

    db.session.delete(path)
    db.session.commit()
    return jsonify({"message": "경로 삭제 완료"}), 200
