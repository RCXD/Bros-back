from pathlib import Path
import re
path = Path("apps/notification/models.py")
text = path.read_text()
lines = text.splitlines()
new_block_lines = [
    "    def to_dict(self, follow_state_map=None):",
    "        \"\"\"Serialize notification data with optional follow info.\"\"\"",
    "        from_user_info = (",
    "            {",
    "                \"user_id\": self.from_user.user_id",
    "                \"username\": self.from_user.username",
    "                \"nickname\": getattr(self.from_user, \"nickname\", None)",
    "                \"profile_img\": getattr(",
    "                    self.from_user, \"profile_img\", None",
    "                ),  # LEGACY: profile_image -> profile_img",
    "            }",
    "            if self.from_user",
    "            else None",
    "        )",
    "        if from_user_info and follow_state_map:",
    "            follow_state = follow_state_map.get(self.from_user_id)",
    "            if follow_state:",
    "                from_user_info[\"follow_state\"] = follow_state",
    "",
    "        return {",
    "            \"notification_id\": self.notification_id",
    "            \"type\": self.type.value",
    "            \"from_user_id\": self.from_user_id",
    "            \"from_user\": from_user_info",
    "            \"to_user_id\": self.to_user_id",
    "            \"post_id\": self.post_id",
    "            \"reply_id\": self.reply_id",
    "            \"mention_id\": self.mention_id",
    "            \"product_id\": self.product_id,  # LEGACY?????? ???? (apps?? ?????)",
    "            \"is_checked\": self.is_checked",
    "            \"created_at\": self.created_at.isoformat() if self.created_at else None",
    "        }",
]
new_block = "\r\n".join(new_block_lines)
new_lines = []
skip_block = False
skip_blank = False
for line in lines:
    if skip_block:
        if line.startswith("        }") and line.strip() == "}":
            skip_block = False
            skip_blank = True
        continue
    if skip_blank and line.strip() == "":
        skip_blank = False
        continue
    if line.startswith("    def to_dict"):
        new_lines.extend(new_block_lines)
        skip_block = True
        continue
    new_lines.append(line)
path.write_text("\r\n".join(new_lines))
