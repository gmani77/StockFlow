from app import db
from flask_login import UserMixin
from datetime import datetime


class Organization(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)

    users = db.relationship("User", backref="organization", lazy=True)
    products = db.relationship("Product", backref="organization", lazy=True)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organization.id"),
        nullable=False
    )


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(150), nullable=False)
    sku = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    quantity = db.Column(db.Integer, default=0, nullable=False)
    cost_price = db.Column(db.Float)
    selling_price = db.Column(db.Float)
    low_stock_threshold = db.Column(db.Integer)

    organization_id = db.Column(
        db.Integer,
        db.ForeignKey("organization.id"),
        nullable=False
    )

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    __table_args__ = (
        db.UniqueConstraint(
            "organization_id",
            "sku",
            name="unique_sku_per_organization"
        ),
    )