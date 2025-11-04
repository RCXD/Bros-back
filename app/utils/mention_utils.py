from flask import jsonify


def serialize_mention(mention: dict):
    return {
        "message": "멘션 등록 완료",
        "mention": {
            "mention_id": mention.mention_id,
            "content_type": mention.content_type.value,
            "object_id": mention.object_id,
            "user_id": mention.user_id,
            "post_id": mention.post_id,
            "created_at": mention.created_at.isoformat(),
        },
    }
