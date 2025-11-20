Cosmetic API README

Base URL: /cosmetic
Auth: JWT required. Admin endpoints require users.account_type == ADMIN.
Models: CosmeticItem, CosmeticSet, CosmeticSetItem, UserItem, UserCosmeticState.
Setup

Migrate DB: FLASK_APP="apps.app:create_app('development')" flask db upgrade
Static uploads: writes under static/cosmetic_overlays
Item endpoints

- Create (admin): POST /cosmetic/items JSON {"type":"overlay","name":"Gold","price":9900,"rarity":"rare","image_path":"cosmetic_overlays/gold.png","theme_color":"#FFD700","description":"Shiny"}
- List (any authenticated): GET /cosmetic/items?type=overlay
- Get (any authenticated): GET /cosmetic/items/{item_id}
- Update (admin): PUT /cosmetic/items/{item_id} JSON (partial)
- Delete (admin): DELETE /cosmetic/items/{item_id}
Types: border | overlay | theme | font | effect | bundle
Set endpoints

- Create (admin): POST /cosmetic/sets JSON {"name":"Gold Pack","price":19900,"items":[1,2],"preview_img":"cosmetic_overlays/gold-pack.png"}
- List (any authenticated): GET /cosmetic/sets
- Get (any authenticated): GET /cosmetic/sets/{set_id}
- Update (admin): PUT /cosmetic/sets/{set_id} JSON (supports replacing items)
- Delete (admin): DELETE /cosmetic/sets/{set_id}
- List items in set (any authenticated): GET /cosmetic/sets/{set_id}/items
User Inventory

List owned: GET /cosmetic/user/items
Acquire item: POST /cosmetic/user/items/acquire JSON {"item_id":1}
Acquire set: POST /cosmetic/user/sets/acquire JSON {"set_id":1}
User Cosmetic State

Get: GET /cosmetic/user/state
Update: PUT /cosmetic/user/state form or JSON with any of:
border_item_id, overlay_item_id, theme_item_id, font_item_id, effect_item_id
Must own items; type must match. Use empty or null to clear.
Uploads

Upload overlay: POST /cosmetic/upload form-data: file=@<image> optional subdir=cosmetic_overlays
Response: {"path":"cosmetic_overlays/<file>","url":"/static/cosmetic_overlays/<file>"}
Auth Example

Add header: Authorization: Bearer <JWT>
Admin-only routes return 403 for non-admin users.
