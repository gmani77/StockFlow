
from flask_wtf.csrf import CSRFProtect
from dotenv import load_dotenv
import os

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash
)

from flask_sqlalchemy import SQLAlchemy

from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


db = SQLAlchemy()
login_manager = LoginManager()


def create_app():
    app = Flask(__name__)

    load_dotenv()

    # ---------------- CONFIGURATION ----------------

    secret_key = os.getenv("SECRET_KEY")

    if not secret_key:
        raise RuntimeError("SECRET_KEY environment variable is missing.")

    app.config["SECRET_KEY"] = secret_key

    # Use the default SQLite database.
    # This avoids the unavailable /var/data directory on Render free plan.
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///stockflow.db"

    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # ---------------- SECURITY ----------------

    CSRFProtect(app)

    # ---------------- INITIALIZE EXTENSIONS ----------------

    db.init_app(app)
    login_manager.init_app(app)

    login_manager.login_view = "login"

    from app.modules.models import User, Organization, Product

    # ---------------- USER LOADER ----------------

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ---------------- HOME ----------------

    @app.route("/")
    def home():
        return """
            <h1>Welcome to StockFlow!</h1>
            <p>Your inventory management system is running.</p>
            <a href="/login">Login</a>
        """

    # ---------------- SIGNUP ----------------

    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        if request.method == "POST":

            organization_name = request.form.get(
                "organization_name", ""
            ).strip()

            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            if not organization_name or not email or not password:
                flash("All fields are required.", "danger")
                return redirect(url_for("signup"))

            if len(password) < 8:
                flash(
                    "Password must be at least 8 characters.",
                    "danger"
                )
                return redirect(url_for("signup"))

            existing_user = User.query.filter_by(
                email=email
            ).first()

            if existing_user:
                flash(
                    "This email is already registered.",
                    "danger"
                )
                return redirect(url_for("signup"))

            organization = Organization(name=organization_name)

            db.session.add(organization)
            db.session.flush()

            hashed_password = generate_password_hash(password)

            user = User(
                email=email,
                password=hashed_password,
                organization_id=organization.id
            )

            db.session.add(user)
            db.session.commit()

            flash(
                "Account created successfully! Please log in.",
                "success"
            )

            return redirect(url_for("login"))

        return render_template("signup.html")

    # ---------------- LOGIN ----------------

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":

            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            user = User.query.filter_by(email=email).first()

            if user and check_password_hash(user.password, password):
                login_user(user)

                flash("Login successful!", "success")

                return redirect(url_for("dashboard"))

            flash("Invalid email or password.", "danger")

            return redirect(url_for("login"))

        return render_template("login.html")

    # ---------------- LOGOUT ----------------

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()

        flash("You have been logged out successfully.", "success")

        return redirect(url_for("login"))

    # ---------------- DASHBOARD ----------------

    @app.route("/dashboard")
    @login_required
    def dashboard():

        products = Product.query.filter_by(
            organization_id=current_user.organization_id
        ).all()

        total_products = len(products)

        total_quantity = sum(
            product.quantity for product in products
        )

        low_stock_products = [
            product for product in products
            if product.quantity <= (
                product.low_stock_threshold
                if product.low_stock_threshold is not None
                else 5
            )
        ]

        low_stock_count = len(low_stock_products)

        return render_template(
            "dashboard.html",
            products=products,
            total_products=total_products,
            total_quantity=total_quantity,
            low_stock_products=low_stock_products,
            low_stock_count=low_stock_count
        )

    # ---------------- PRODUCT LIST AND SEARCH ----------------

    @app.route("/products")
    @login_required
    def products_page():

        search = request.args.get("search", "").strip()

        query = Product.query.filter_by(
            organization_id=current_user.organization_id
        )

        if search:
            query = query.filter(
                db.or_(
                    Product.name.ilike(f"%{search}%"),
                    Product.sku.ilike(f"%{search}%")
                )
            )

        products = query.order_by(
            Product.created_at.desc()
        ).all()

        return render_template(
            "products.html",
            products=products,
            search=search
        )

    # ---------------- ADD PRODUCT ----------------

    @app.route("/products/add", methods=["GET", "POST"])
    @login_required
    def add_product():

        if request.method == "POST":

            name = request.form.get("name", "").strip()
            sku = request.form.get("sku", "").strip()
            description = request.form.get("description", "").strip()

            try:
                quantity = int(request.form.get("quantity", 0))

                cost_price = request.form.get("cost_price") or None
                selling_price = request.form.get("selling_price") or None

                low_stock_threshold = (
                    request.form.get("low_stock_threshold") or None
                )

                cost_price = float(cost_price) if cost_price else None

                selling_price = (
                    float(selling_price) if selling_price else None
                )

                low_stock_threshold = (
                    int(low_stock_threshold)
                    if low_stock_threshold else None
                )

            except ValueError:
                flash("Please enter valid numbers.", "danger")
                return redirect(url_for("add_product"))

            if not name or not sku:
                flash(
                    "Product name and SKU are required.",
                    "danger"
                )
                return redirect(url_for("add_product"))

            if (
                quantity < 0
                or (cost_price is not None and cost_price < 0)
                or (selling_price is not None and selling_price < 0)
                or (
                    low_stock_threshold is not None
                    and low_stock_threshold < 0
                )
            ):
                flash("Values cannot be negative.", "danger")
                return redirect(url_for("add_product"))

            existing_product = Product.query.filter_by(
                organization_id=current_user.organization_id,
                sku=sku
            ).first()

            if existing_product:
                flash(
                    "This SKU already exists in your organization.",
                    "danger"
                )
                return redirect(url_for("add_product"))

            product = Product(
                name=name,
                sku=sku,
                description=description,
                quantity=quantity,
                cost_price=cost_price,
                selling_price=selling_price,
                low_stock_threshold=low_stock_threshold,
                organization_id=current_user.organization_id
            )

            db.session.add(product)
            db.session.commit()

            flash("Product added successfully!", "success")

            return redirect(url_for("dashboard"))

        return render_template("add_product.html")

    # ---------------- EDIT PRODUCT ----------------

    @app.route(
        "/products/edit/<int:product_id>",
        methods=["GET", "POST"]
    )
    @login_required
    def edit_product(product_id):

        product = Product.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first_or_404()

        if request.method == "POST":

            name = request.form.get("name", "").strip()
            sku = request.form.get("sku", "").strip()
            description = request.form.get("description", "").strip()

            if not name or not sku:
                flash(
                    "Product name and SKU are required.",
                    "danger"
                )
                return redirect(
                    url_for("edit_product", product_id=product.id)
                )

            existing_sku = Product.query.filter(
                Product.organization_id == current_user.organization_id,
                Product.sku == sku,
                Product.id != product.id
            ).first()

            if existing_sku:
                flash("This SKU already exists.", "danger")
                return redirect(
                    url_for("edit_product", product_id=product.id)
                )

            try:
                quantity = int(request.form.get("quantity", 0))

                cost_price = request.form.get(
                    "cost_price", ""
                ).strip()

                selling_price = request.form.get(
                    "selling_price", ""
                ).strip()

                threshold = request.form.get(
                    "low_stock_threshold", ""
                ).strip()

                cost_price = float(cost_price) if cost_price else None

                selling_price = (
                    float(selling_price) if selling_price else None
                )

                threshold = int(threshold) if threshold else None

                if (
                    quantity < 0
                    or (threshold is not None and threshold < 0)
                ):
                    flash(
                        "Quantity and threshold cannot be negative.",
                        "danger"
                    )
                    return redirect(
                        url_for("edit_product", product_id=product.id)
                    )

                if (
                    (cost_price is not None and cost_price < 0)
                    or (
                        selling_price is not None
                        and selling_price < 0
                    )
                ):
                    flash("Prices cannot be negative.", "danger")
                    return redirect(
                        url_for("edit_product", product_id=product.id)
                    )

            except ValueError:
                flash("Please enter valid numbers.", "danger")
                return redirect(
                    url_for("edit_product", product_id=product.id)
                )

            product.name = name
            product.sku = sku
            product.description = description
            product.quantity = quantity
            product.cost_price = cost_price
            product.selling_price = selling_price
            product.low_stock_threshold = threshold

            db.session.commit()

            flash("Product updated successfully!", "success")

            return redirect(url_for("products_page"))

        return render_template(
            "edit_product.html",
            product=product
        )

    # ---------------- DELETE PRODUCT ----------------

    @app.route(
        "/products/delete/<int:product_id>",
        methods=["POST"]
    )
    @login_required
    def delete_product(product_id):

        product = Product.query.filter_by(
            id=product_id,
            organization_id=current_user.organization_id
        ).first_or_404()

        db.session.delete(product)
        db.session.commit()

        flash("Product deleted successfully!", "success")

        return redirect(url_for("products_page"))

    # ---------------- CREATE DATABASE TABLES ----------------

    with app.app_context():
        db.create_all()

    return app
