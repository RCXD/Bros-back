from ..extensions import db

# post의 카테고리


class SubCategory(db.Model):
    __tablename__ = "sub_categories"

    subcategory_id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.category_id"))
    subcategory_name = db.Column(db.String(255), nullable=True, unique=True)


class Category(db.Model):
    __tablename__ = "categories"

    category_id = db.Column(db.Integer, primary_key=True)
    category_name = db.Column(db.String(50), unique=True, nullable=True)
    subcategories = db.relationship("SubCategory", backref="category", lazy=True)
