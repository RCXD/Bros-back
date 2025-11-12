from flask import jsonify


def serialize_mention(mention):
    mention_type = "POST" if mention.post_id else "REPLY"
    return {
        "message": "멘션 등록 완료",
        "mention": {
            "mention_id": mention.mention_id,
            "mentioner_id": mention.mentioner_id,
            "mentioned_user_id": mention.mentioned_user_id,
            "post_id": mention.post_id,
            "reply_id": mention.reply_id,
            "mention_type": mention_type,
            "created_at": mention.created_at.isoformat(),
            "is_checked": mention.is_checked,
        },
    }

