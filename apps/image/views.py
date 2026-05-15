"""
Image views
프로필, 게시글, 상품 이미지 조회 엔드포인트
"""

import os
from flask import Blueprint, send_from_directory, current_app, jsonify
from apps.image.models import Image


bp = Blueprint("image", __name__)


@bp.get("/api_info")
def api_info():
    """Return API endpoint information for the image module (development use).

    Returns:
        JSON response with 200 status containing a description of all image endpoints.
    """
    info = {
        "module": "image",
        "base_path": "/image",
        "description": "프로필, 게시글, 상품 이미지 조회",
        "endpoints": [
            {
                "path": "/image/profile/<uuid>",
                "method": "GET",
                "auth_required": False,
                "description": "프로필 이미지 조회",
                "path_params": {"uuid": "이미지 UUID 또는 'default_profile'"},
            },
            {
                "path": "/image/post/<uuid>",
                "method": "GET",
                "auth_required": False,
                "description": "게시글 이미지 조회",
            },
            {
                "path": "/image/product/<uuid>",
                "method": "GET",
                "auth_required": False,
                "description": "상품 이미지 조회",
            },
            {
                "path": "/image/api_info",
                "method": "GET",
                "auth_required": False,
                "description": "API 정보 조회 (개발용)",
            },
        ],
    }
    return jsonify(info), 200


@bp.get("/profile/<string:uuid>")
def get_profile_image(uuid):
    """Serve a profile image file by UUID.

    Args:
        uuid: The image UUID, or 'default_profile' to serve the default placeholder.

    Returns:
        The image file as a direct file response.
        Returns 404 if the image record exists but the file is missing from disk.
    """
    if uuid == "default_profile":
        folder = os.path.join(current_app.root_path, "static")
        return send_from_directory(folder, "default_profile.jpg")

    image = Image.query.filter_by(uuid=uuid).first_or_404(description="이미지 없음")

    # DB: static/profile_images/2025-11-12/uuid.jpg
    relative_path = image.directory
    absolute_path = os.path.join(current_app.root_path, relative_path)

    folder = os.path.dirname(absolute_path)
    filename = os.path.basename(absolute_path)

    if not os.path.exists(absolute_path):
        return jsonify({"message": f"파일 없음: {absolute_path}"}), 404

    return send_from_directory(folder, filename)


@bp.get("/post/<string:uuid>")
def get_post_image(uuid):
    """Serve a post image file by UUID.

    Args:
        uuid: The image UUID.

    Returns:
        The image file as a direct file response.
        Returns 404 if the image record does not exist.
    """
    image = Image.query.filter_by(uuid=uuid).first_or_404(description="이미지 없음")
    return send_from_directory(
        "/".join(image.directory.split("/")[:-1]), image.directory.split("/")[-1]
    )


@bp.get("/product/<string:uuid>")
def get_product_image(uuid):
    """Serve a product image file by UUID.

    Args:
        uuid: The image UUID.

    Returns:
        The image file as a direct file response.
        Returns 404 if the image record does not exist or the file is missing from disk.
    """
    image = Image.query.filter_by(uuid=uuid).first_or_404(description="이미지 없음")

    # directory는 상대 경로로 저장됨
    relative_path = image.directory
    absolute_path = os.path.join(current_app.root_path, relative_path)

    folder = os.path.dirname(absolute_path)
    filename = os.path.basename(absolute_path)

    if not os.path.exists(absolute_path):
        return jsonify({"message": f"파일 없음: {absolute_path}"}), 404

    return send_from_directory(folder, filename)
