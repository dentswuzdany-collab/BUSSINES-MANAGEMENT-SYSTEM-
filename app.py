
import os
import psycopg
from psycopg.rows import dict_row
import hashlib
import hmac
from functools import wraps
from datetime import datetime, date
from flask import (
    Flask, g, request, redirect, url_for, session,
    flash, render_template_string, abort
)
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-before-deployment")
app.config["DATABASE"] = os.environ.get("DATABASE_PATH", "stock_database.db")
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("RENDER", "") == "true"

# ==================== DATABASE ====================

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
        g.db.execute("PRAGMA busy_timeout = 10000")
    return g.db

@app.teardown_appcontext
def close_db(error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    db.executescript("""
    CREATE TABLE IF NOT EXISTS stock (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        item TEXT NOT NULL,
        initial_quantity INTEGER NOT NULL DEFAULT 0,
        unit_price REAL NOT NULL DEFAULT 0,
        total_amount REAL NOT NULL DEFAULT 0,
        remaining_quantity INTEGER NOT NULL DEFAULT 0,
        date_added TEXT NOT NULL,
        low_stock_level INTEGER NOT NULL DEFAULT 5
    );

    CREATE TABLE IF NOT EXISTS admin (
        id INTEGER PRIMARY KEY CHECK (id = 1),
        password_hash TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS sales (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_id INTEGER NOT NULL,
        item TEXT NOT NULL,
        quantity_sold INTEGER NOT NULL,
        buying_price REAL NOT NULL,
        selling_price REAL NOT NULL,
        revenue REAL NOT NULL,
        cost REAL NOT NULL,
        profit_loss REAL NOT NULL,
        sale_date TEXT NOT NULL,
        FOREIGN KEY(stock_id) REFERENCES stock(id)
    );

    CREATE TABLE IF NOT EXISTS deliveries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stock_id INTEGER NOT NULL,
        item TEXT NOT NULL,
        quantity_received INTEGER NOT NULL,
        buying_price REAL NOT NULL,
        total_cost REAL NOT NULL,
        delivery_date TEXT NOT NULL,
        FOREIGN KEY(stock_id) REFERENCES stock(id)
    );

    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        description TEXT NOT NULL,
        amount REAL NOT NULL,
        expense_date TEXT NOT NULL
    );
    """)

    cols = {
        row["name"]
        for row in db.execute("PRAGMA table_info(stock)").fetchall()
    }

    if "low_stock_level" not in cols:
        db.execute(
            "ALTER TABLE stock ADD COLUMN low_stock_level INTEGER NOT NULL DEFAULT 5"
        )

    db.commit()

with app.app_context():
    init_db()

# ==================== COMMON FUNCTIONS ====================

def money(value):
    return f"UGX {float(value or 0):,.2f}"

def password_matches(row, password):
    keys = row.keys()
    old_salt = row["salt"] if "salt" in keys else None

    if old_salt:
        candidate = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode(),
            bytes.fromhex(old_salt),
            200000
        ).hex()

        return hmac.compare_digest(
            row["password_hash"], candidate
        )

    return check_password_hash(
        row["password_hash"], password
    )

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            flash(
                "Please sign in as administrator to continue.",
                "warning"
            )
            return redirect(url_for("login", next=request.path))

        return view(*args, **kwargs)

    return wrapped

def number(name, minimum=0, whole=False):
    raw = request.form.get(name, "").strip()

    try:
        value = int(raw) if whole else float(raw)
    except (TypeError, ValueError):
        raise ValueError(
            f"Enter a valid value for {name.replace('_', ' ')}."
        )

    if value < minimum:
        raise ValueError(
            f"{name.replace('_', ' ').capitalize()} must be at least {minimum}."
        )

    return value

def page(title, body, **context):
    is_logged_in = bool(session.get("admin_id"))

    body_context = {
        "money": money,
        "logged_in": is_logged_in
    }

    body_context.update(context)

    rendered_body = render_template_string(
        body, **body_context
    )

    return render_template_string(
        BASE,
        title=title,
        body=rendered_body,
        logged_in=is_logged_in
    )

# ==================== WEBSITE DESIGN ====================

BASE = r"""
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>{{ title }} | Business Management System</title>

<style>
:root {
    --navy: #102a43;
    --blue: #1769aa;
    --bg: #f3f6fa;
    --ink: #243447;
    --muted: #66788a;
    --line: #e3eaf1;
}

* {
    box-sizing: border-box;
}

body {
    margin: 0;
    background: var(--bg);
    font-family: Arial, sans-serif;
    color: var(--ink);
}

header {
    background: var(--navy);
    color: white;
    padding: 18px 4%;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
}

header a {
    color: white;
    text-decoration: none;
    margin-left: 12px;
}

.brand {
    font-weight: bold;
    font-size: 18px;
}

nav {
    background: white;
    padding: 12px 4%;
    border-bottom: 1px solid var(--line);
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}

nav a, .btn {
    display: inline-block;
    background: var(--blue);
    color: white;
    text-decoration: none;
    border: 0;
    border-radius: 7px;
    padding: 10px 13px;
    font-size: 14px;
    cursor: pointer;
}

nav a {
    background: #eaf2fa;
    color: #17476d;
}

.wrap {
    max-width: 1150px;
    margin: 25px auto;
    padding: 0 16px;
}

h1 {
    font-size: 25px;
    margin: 0 0 18px;
}

h2 {
    font-size: 19px;
    margin-top: 0;
}

.grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
    gap: 14px;
}

.card, .panel {
    background: white;
    border: 1px solid var(--line);
    border-radius: 12px;
    padding: 18px;
    box-shadow: 0 3px 12px #102a430b;
    margin-bottom: 16px;
}

.metric {
    font-size: 23px;
    font-weight: bold;
    color: var(--navy);
    margin-top: 8px;
}

.muted {
    color: var(--muted);
    font-size: 13px;
}

form {
    display: grid;
    gap: 12px;
    max-width: 650px;
}

label {
    font-weight: bold;
    font-size: 14px;
}

input, select {
    width: 100%;
    padding: 12px;
    border: 1px solid #cbd5df;
    border-radius: 7px;
    font-size: 15px;
    background: white;
}

button {
    font: inherit;
}

.btn {
    width: max-content;
}

table {
    width: 100%;
    border-collapse: collapse;
    background: white;
}

th, td {
    text-align: left;
    padding: 11px;
    border-bottom: 1px solid var(--line);
    font-size: 14px;
}

th {
    background: #edf3f8;
}

.table-wrap {
    overflow-x: auto;
    border-radius: 9px;
}

.alert {
    padding: 12px 14px;
    border-radius: 8px;
    margin-bottom: 12px;
    background: #e8f2ff;
}

.alert.error {
    background: #ffeded;
    color: #9b1c1c;
}

.alert.success {
    background: #e8f7ee;
    color: #17643a;
}

.actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin: 12px 0;
}

@media(max-width:600px) {
    header {
        align-items: flex-start;
    }

    nav a {
        font-size: 12px;
        padding: 9px;
    }

    .wrap {
        margin: 18px auto;
    }

    th, td {
        padding: 8px;
        font-size: 12px;
    }
}
</style>
</head>

<body>

<header>
    <div class="brand">BUSINESS MANAGEMENT SYSTEM</div>

    <div>
    {% if logged_in %}
        <span>Administrator</span>
        <a href="{{ url_for('logout') }}">Sign out</a>
    {% else %}
        <a href="{{ url_for('login') }}">Admin sign in</a>
    {% endif %}
    </div>
</header>

{% if logged_in %}
<nav>
    <a href="{{ url_for('dashboard') }}">Dashboard</a>
    <a href="{{ url_for('inventory') }}">Inventory</a>
    <a href="{{ url_for('add_product') }}">Add product</a>
    <a href="{{ url_for('record_sale') }}">Record sale</a>
    <a href="{{ url_for('sales_history') }}">Sales history</a>
    <a href="{{ url_for('deliveries') }}">Deliveries</a>
    <a href="{{ url_for('expenses') }}">Expenses</a>
    <a href="{{ url_for('reports') }}">Reports</a>
    <a href="{{ url_for('change_password') }}">Password</a>
</nav>
{% endif %}

<div class="wrap">

{% with messages=get_flashed_messages(with_categories=true) %}
    {% for category,message in messages %}
        <div class="alert {{ category }}">{{ message }}</div>
    {% endfor %}
{% endwith %}

{{ body|safe }}

</div>
</body>
</html>
"""

# ==================== HOME PAGE ====================

@app.route("/")
def home():
    db = get_db()

    stats = db.execute("""
        SELECT COUNT(*) products,
        COALESCE(SUM(remaining_quantity),0) units
        FROM stock
    """).fetchone()

    body = """
    <div class="panel">
        <h1>Welcome to your Business Management System</h1>

        <p>
        Manage stock, sales, deliveries, expenses
        and business performance from one place.
        </p>

        <p>
        <b>Registered products:</b> {{ products }}
        &nbsp;
        <b>Units in stock:</b> {{ units }}
        </p>

        {% if logged_in %}
            <a class="btn" href="{{ url_for('dashboard') }}">
                Open dashboard
            </a>
        {% else %}
            <a class="btn" href="{{ url_for('login') }}">
                Administrator sign in
            </a>
        {% endif %}
    </div>
    """

    return page(
        "Home",
        body,
        products=stats["products"],
        units=stats["units"]
    )

# ==================== ADMIN SETUP ====================

@app.route("/setup", methods=["GET", "POST"])
def setup():
    db = get_db()

    exists = db.execute(
        "SELECT 1 FROM admin WHERE id=1"
    ).fetchone()

    if exists:
        return page(
            "Setup",
            """
            <div class='panel'>
                <h1>Administrator already configured</h1>
                <a class='btn' href='/login'>Sign in</a>
            </div>
            """
        )

    body = """
    <div class="panel">
        <h1>Create administrator account</h1>

        <p>
        Use this page only for the first setup.
        Choose a strong password of at least 8 characters.
        </p>

        <form method="post">

            <label>New password</label>
            <input type="password" name="password"
                   minlength="8" required>

            <label>Confirm password</label>
            <input type="password" name="confirm"
                   minlength="8" required>

            <button class="btn">Create administrator</button>

        </form>
    </div>
    """

    if request.method == "POST":

        password = request.form.get("password", "")

        if len(password) < 8 or password != request.form.get("confirm", ""):
            flash(
                "Passwords must match and contain at least 8 characters.",
                "error"
            )

        else:
            admin_cols = {
                r["name"]
                for r in db.execute(
                    "PRAGMA table_info(admin)"
                ).fetchall()
            }

            if "salt" in admin_cols:
                db.execute(
                    "INSERT INTO admin(id,password_hash,salt) VALUES(1,?,?)",
                    (generate_password_hash(password), "")
                )
            else:
                db.execute(
                    "INSERT INTO admin(id,password_hash) VALUES(1,?)",
                    (generate_password_hash(password),)
                )

            db.commit()

            flash(
                "Administrator created. Please sign in.",
                "success"
            )

            return redirect(url_for("login"))

    return page("First-time setup", body)

# ==================== LOGIN ====================

@app.route("/login", methods=["GET", "POST"])
def login():

    body = """
    <div class="panel">
        <h1>Administrator sign in</h1>

        <form method="post">

            <label>Password</label>
            <input type="password" name="password" required>

            <button class="btn">Sign in</button>

        </form>

        <p class="muted">
            First time here?
            <a href="/setup">Create administrator account</a>.
        </p>
    </div>
    """

    if request.method == "POST":

        row = get_db().execute(
            "SELECT * FROM admin WHERE id=1"
        ).fetchone()

        if row and password_matches(
            row,
            request.form.get("password", "")
        ):

            session.clear()
            session["admin_id"] = 1

            flash("Signed in successfully.", "success")

            return redirect(url_for("dashboard"))

        flash(
            "Incorrect password, or administrator setup has not been completed.",
            "error"
        )

    return page("Sign in", body)

@app.route("/logout")
def logout():
    session.clear()

    flash("You have signed out.", "success")

    return redirect(url_for("home"))

# ==================== DASHBOARD ====================

@app.route("/dashboard")
@admin_required
def dashboard():

    db = get_db()

    stock = db.execute("""
        SELECT COUNT(*) products,
        COALESCE(SUM(remaining_quantity),0) units,
        COALESCE(SUM(remaining_quantity*unit_price),0) value
        FROM stock
    """).fetchone()

    sales = db.execute("""
        SELECT COALESCE(SUM(revenue),0) revenue,
        COALESCE(SUM(cost),0) cost,
        COALESCE(SUM(profit_loss),0) gross,
        COUNT(*) transactions
        FROM sales
    """).fetchone()

    expenses = db.execute(
        "SELECT COALESCE(SUM(amount),0) total FROM expenses"
    ).fetchone()["total"]

    low = db.execute("""
        SELECT COUNT(*) n
        FROM stock
        WHERE remaining_quantity<=low_stock_level
    """).fetchone()["n"]

    body = """
    <h1>Business dashboard</h1>

    <div class="grid">

        <div class="card">
            Registered products
            <div class="metric">{{ s.products }}</div>
        </div>

        <div class="card">
            Available stock units
            <div class="metric">{{ s.units }}</div>
        </div>

        <div class="card">
            Current stock value
            <div class="metric">{{ money(s.value) }}</div>
        </div>

        <div class="card">
            Total sales revenue
            <div class="metric">{{ money(t.revenue) }}</div>
        </div>

        <div class="card">
            Gross profit / loss
            <div class="metric">{{ money(t.gross) }}</div>
        </div>

        <div class="card">
            Business expenses
            <div class="metric">{{ money(e) }}</div>
        </div>

        <div class="card">
            Net profit / loss
            <div class="metric">{{ money(t.gross-e) }}</div>
        </div>

        <div class="card">
            Sales transactions
            <div class="metric">{{ t.transactions }}</div>
        </div>

        <div class="card">
            Low-stock alerts
            <div class="metric">{{ low }}</div>
        </div>

    </div>

    <div class="panel">
        <h2>Quick actions</h2>

        <div class="actions">
            <a class="btn" href="/products/add">Add product</a>
            <a class="btn" href="/sales/add">Record sale</a>
            <a class="btn" href="/deliveries/add">Record delivery</a>
            <a class="btn" href="/expenses">Record expense</a>
            <a class="btn" href="/reports">View reports</a>
        </div>

        <p class="muted">
        Net profit shown here is gross sales profit less recorded expenses.
        Stock value is an inventory asset, not profit.
        </p>
    </div>
    """

    return page(
        "Dashboard",
        body,
        s=stock,
        t=sales,
        e=expenses,
        low=low
    )

# ==================== INVENTORY ====================

@app.route("/inventory")
@admin_required
def inventory():

    rows = get_db().execute(
        "SELECT * FROM stock ORDER BY item"
    ).fetchall()

    body = """
    <h1>Inventory</h1>

    <div class="actions">
        <a class="btn" href="/products/add">Add new product</a>
    </div>

    <div class="table-wrap">
    <table>

        <tr>
            <th>ID</th>
            <th>Product</th>
            <th>Available</th>
            <th>Buying price</th>
            <th>Low-stock limit</th>
            <th>Action</th>
        </tr>

        {% for r in rows %}
        <tr>
            <td>{{ r.id }}</td>
            <td>{{ r.item }}</td>
            <td>{{ r.remaining_quantity }}</td>
            <td>{{ money(r.unit_price) }}</td>
            <td>{{ r.low_stock_level }}</td>
            <td><a href="/products/{{ r.id }}/edit">Edit</a></td>
        </tr>

        {% else %}
        <tr>
            <td colspan="6">No products have been added.</td>
        </tr>
        {% endfor %}

    </table>
    </div>
    """

    return page("Inventory", body, rows=rows)

@app.route("/products/add", methods=["GET", "POST"])
@admin_required
def add_product():

    body = """
    <div class="panel">
        <h1>Add product</h1>

        <form method="post">

            <label>Product name</label>
            <input name="item" required>

            <label>Quantity</label>
            <input type="number" name="quantity" min="1" required>

            <label>Buying price per unit (UGX)</label>
            <input type="number" step="0.01" min="0"
                   name="price" required>

            <label>Low-stock alert level</label>
            <input type="number" min="0" name="low"
                   value="5" required>

            <button class="btn">Save product</button>

        </form>
    </div>
    """

    if request.method == "POST":

        try:
            item = request.form.get("item", "").strip()

            if not item:
                raise ValueError("Product name is required.")

            qty = number("quantity", 1, True)
            price = number("price")
            low = number("low", 0, True)

            db = get_db()

            db.execute("""
                INSERT INTO stock(
                    item, initial_quantity, unit_price,
                    total_amount, remaining_quantity,
                    date_added, low_stock_level
                )
                VALUES(?,?,?,?,?,?,?)
            """, (
                item,
                qty,
                price,
                qty * price,
                qty,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                low
            ))

            db.commit()

            flash("Product added successfully.", "success")

            return redirect(url_for("inventory"))

        except ValueError as exc:
            flash(str(exc), "error")

    return page("Add product", body)

@app.route("/products/<int:product_id>/edit", methods=["GET", "POST"])
@admin_required
def edit_product(product_id):

    db = get_db()

    product = db.execute(
        "SELECT * FROM stock WHERE id=?",
        (product_id,)
    ).fetchone()

    if not product:
        abort(404)

    body = """
    <div class="panel">
        <h1>Edit product</h1>

        <form method="post">

            <label>Product name</label>
            <input name="item" value="{{ p.item }}" required>

            <label>Buying price per unit (UGX)</label>
            <input type="number" step="0.01" min="0"
                   name="price" value="{{ p.unit_price }}" required>

            <label>Low-stock alert level</label>
            <input type="number" min="0"
                   name="low" value="{{ p.low_stock_level }}" required>

            <button class="btn">Update product</button>

        </form>
    </div>
    """

    if request.method == "POST":

        try:
            item = request.form.get("item", "").strip()

            if not item:
                raise ValueError("Product name is required.")

            price = number("price")
            low = number("low", 0, True)

            db.execute("""
                UPDATE stock
                SET item=?, unit_price=?,
                    total_amount=initial_quantity*?,
                    low_stock_level=?
                WHERE id=?
            """, (item, price, price, low, product_id))

            db.commit()

            flash("Product updated.", "success")

            return redirect(url_for("inventory"))

        except ValueError as exc:
            flash(str(exc), "error")

    return page("Edit product", body, p=product)

# ==================== SALES ====================

@app.route("/sales/add", methods=["GET", "POST"])
@admin_required
def record_sale():

    db = get_db()

    products = db.execute("""
        SELECT id,item,remaining_quantity,unit_price
        FROM stock ORDER BY item
    """).fetchall()

    body = """
    <div class="panel">
        <h1>Record sale</h1>

        <form method="post">

            <label>Product</label>

            <select name="stock_id" required>
                {% for p in products %}
                <option value="{{ p.id }}">
                    {{ p.item }} — {{ p.remaining_quantity }} available
                    — {{ money(p.unit_price) }} buying price
                </option>
                {% endfor %}
            </select>

            <label>Quantity sold</label>
            <input type="number" name="quantity" min="1" required>

            <label>Selling price per unit (UGX)</label>
            <input type="number" name="selling_price"
                   min="0" step="0.01" required>

            <button class="btn">Save sale</button>

        </form>
    </div>
    """

    if request.method == "POST":

        try:
            pid = number("stock_id", 1, True)
            qty = number("quantity", 1, True)
            sell = number("selling_price")

            product = db.execute(
                "SELECT * FROM stock WHERE id=?",
                (pid,)
            ).fetchone()

            if not product:
                raise ValueError("Selected product does not exist.")

            if qty > product["remaining_quantity"]:
                raise ValueError(
                    f"Only {product['remaining_quantity']} units are available."
                )

            buy = product["unit_price"]

            revenue = qty * sell
            cost = qty * buy

            db.execute("""
                UPDATE stock
                SET remaining_quantity=remaining_quantity-?
                WHERE id=? AND remaining_quantity>=?
            """, (qty, pid, qty))

            if db.execute("SELECT changes()").fetchone()[0] != 1:
                raise ValueError("Stock changed; sale was not saved.")

            db.execute("""
                INSERT INTO sales(
                    stock_id,item,quantity_sold,buying_price,
                    selling_price,revenue,cost,profit_loss,sale_date
                )
                VALUES(?,?,?,?,?,?,?,?,?)
            """, (
                pid,
                product["item"],
                qty,
                buy,
                sell,
                revenue,
                cost,
                revenue - cost,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            db.commit()

            flash(
                f"Sale saved. Revenue {money(revenue)}; "
                f"profit/loss {money(revenue-cost)}.",
                "success"
            )

            return redirect(url_for("sales_history"))

        except ValueError as exc:
            db.rollback()
            flash(str(exc), "error")

    return page("Record sale", body, products=products)

@app.route("/sales")
@admin_required
def sales_history():

    rows = get_db().execute("""
        SELECT * FROM sales
        ORDER BY id DESC LIMIT 300
    """).fetchall()

    body = """
    <h1>Sales history</h1>

    <div class="table-wrap">
    <table>

        <tr>
            <th>Date</th>
            <th>Product</th>
            <th>Qty</th>
            <th>Revenue</th>
            <th>Cost</th>
            <th>Profit / loss</th>
        </tr>

        {% for r in rows %}
        <tr>
            <td>{{ r.sale_date }}</td>
            <td>{{ r.item }}</td>
            <td>{{ r.quantity_sold }}</td>
            <td>{{ money(r.revenue) }}</td>
            <td>{{ money(r.cost) }}</td>
            <td>{{ money(r.profit_loss) }}</td>
        </tr>

        {% else %}
        <tr><td colspan="6">No sales recorded.</td></tr>
        {% endfor %}

    </table>
    </div>
    """

    return page("Sales history", body, rows=rows)

# ==================== DELIVERIES ====================

@app.route("/deliveries")
@admin_required
def deliveries():

    rows = get_db().execute("""
        SELECT * FROM deliveries
        ORDER BY id DESC LIMIT 300
    """).fetchall()

    body = """
    <h1>Stock delivery history</h1>

    <a class="btn" href="/deliveries/add">Record delivery</a>

    <div class="table-wrap">
    <table>

        <tr>
            <th>Date</th>
            <th>Product</th>
            <th>Quantity</th>
            <th>Buying price</th>
            <th>Total cost</th>
        </tr>

        {% for r in rows %}
        <tr>
            <td>{{ r.delivery_date }}</td>
            <td>{{ r.item }}</td>
            <td>{{ r.quantity_received }}</td>
            <td>{{ money(r.buying_price) }}</td>
            <td>{{ money(r.total_cost) }}</td>
        </tr>

        {% else %}
        <tr><td colspan="5">No deliveries recorded.</td></tr>
        {% endfor %}

    </table>
    </div>
    """

    return page("Deliveries", body, rows=rows)

@app.route("/deliveries/add", methods=["GET", "POST"])
@admin_required
def add_delivery():

    db = get_db()

    products = db.execute("""
        SELECT id,item,remaining_quantity,unit_price
        FROM stock ORDER BY item
    """).fetchall()

    body = """
    <div class="panel">
        <h1>Record stock delivery</h1>

        <form method="post">

            <label>Product</label>

            <select name="stock_id" required>
                {% for p in products %}
                <option value="{{ p.id }}">
                    {{ p.item }} — current stock {{ p.remaining_quantity }}
                </option>
                {% endfor %}
            </select>

            <label>Quantity received</label>
            <input type="number" name="quantity" min="1" required>

            <label>Buying price per delivered unit (UGX)</label>
            <input type="number" step="0.01" min="0"
                   name="price" required>

            <button class="btn">Save delivery</button>

        </form>
    </div>
    """

    if request.method == "POST":

        try:
            pid = number("stock_id", 1, True)
            qty = number("quantity", 1, True)
            price = number("price")

            p = db.execute(
                "SELECT * FROM stock WHERE id=?",
                (pid,)
            ).fetchone()

            if not p:
                raise ValueError("Selected product does not exist.")

            old_qty = p["remaining_quantity"]
            old_price = p["unit_price"]

            new_qty = old_qty + qty

            average = (
                (old_qty * old_price) + (qty * price)
            ) / new_qty

            total = qty * price

            db.execute("""
                UPDATE stock
                SET remaining_quantity=?, unit_price=?
                WHERE id=?
            """, (new_qty, average, pid))

            db.execute("""
                INSERT INTO deliveries(
                    stock_id,item,quantity_received,
                    buying_price,total_cost,delivery_date
                )
                VALUES(?,?,?,?,?,?)
            """, (
                pid,
                p["item"],
                qty,
                price,
                total,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))

            db.commit()

            flash(
                "Delivery recorded and stock updated.",
                "success"
            )

            return redirect(url_for("deliveries"))

        except ValueError as exc:
            db.rollback()
            flash(str(exc), "error")

    return page("Record delivery", body, products=products)

# ==================== EXPENSES ====================

@app.route("/expenses", methods=["GET", "POST"])
@admin_required
def expenses():

    db = get_db()

    if request.method == "POST":

        try:
            desc = request.form.get("description", "").strip()

            if not desc:
                raise ValueError("Enter an expense description.")

            amount = number("amount", 0.01)

            expense_date = (
                request.form.get("expense_date")
                or date.today().isoformat()
            )

            datetime.strptime(expense_date, "%Y-%m-%d")

            db.execute("""
                INSERT INTO expenses(description,amount,expense_date)
                VALUES(?,?,?)
            """, (desc, amount, expense_date))

            db.commit()

            flash("Expense recorded.", "success")

            return redirect(url_for("expenses"))

        except ValueError as exc:
            flash(str(exc), "error")

    rows = db.execute("""
        SELECT * FROM expenses
        ORDER BY expense_date DESC,id DESC LIMIT 300
    """).fetchall()

    body = """
    <h1>Business expenses</h1>

    <div class="panel">
        <h2>Record expense</h2>

        <form method="post">

            <label>Description</label>
            <input name="description" required>

            <label>Amount (UGX)</label>
            <input type="number" name="amount"
                   min="0.01" step="0.01" required>

            <label>Date</label>
            <input type="date" name="expense_date"
                   value="{{ today }}" required>

            <button class="btn">Save expense</button>

        </form>
    </div>

    <div class="table-wrap">
    <table>

        <tr>
            <th>Date</th>
            <th>Description</th>
            <th>Amount</th>
        </tr>

        {% for r in rows %}
        <tr>
            <td>{{ r.expense_date }}</td>
            <td>{{ r.description }}</td>
            <td>{{ money(r.amount) }}</td>
        </tr>

        {% else %}
        <tr><td colspan="3">No expenses recorded.</td></tr>
        {% endfor %}

    </table>
    </div>
    """

    return page(
        "Expenses",
        body,
        rows=rows,
        today=date.today().isoformat()
    )

# ==================== REPORTS ====================

@app.route("/reports")
@admin_required
def reports():

    db = get_db()

    daily = db.execute("""
        SELECT COUNT(*) transactions,
        COALESCE(SUM(revenue),0) revenue,
        COALESCE(SUM(cost),0) cost,
        COALESCE(SUM(profit_loss),0) profit
        FROM sales
        WHERE date(sale_date)=date('now','localtime')
    """).fetchone()

    monthly = db.execute("""
        SELECT COUNT(*) transactions,
        COALESCE(SUM(revenue),0) revenue,
        COALESCE(SUM(cost),0) cost,
        COALESCE(SUM(profit_loss),0) profit
        FROM sales
        WHERE strftime('%Y-%m',sale_date)=strftime('%Y-%m','now','localtime')
    """).fetchone()

    expenses_total = db.execute("""
        SELECT COALESCE(SUM(amount),0) total
        FROM expenses
    """).fetchone()["total"]

    low = db.execute("""
        SELECT * FROM stock
        WHERE remaining_quantity<=low_stock_level
        ORDER BY remaining_quantity
    """).fetchall()

    body = """
    <h1>Financial and stock reports</h1>

    <div class="grid">

        <div class="card">
            <h2>Today's sales</h2>
            Transactions: {{ d.transactions }}
            <p>Revenue: <b>{{ money(d.revenue) }}</b></p>
            <p>Cost: {{ money(d.cost) }}</p>
            <p>Gross profit/loss: {{ money(d.profit) }}</p>
        </div>

        <div class="card">
            <h2>This month's sales</h2>
            Transactions: {{ m.transactions }}
            <p>Revenue: <b>{{ money(m.revenue) }}</b></p>
            <p>Cost: {{ money(m.cost) }}</p>
            <p>Gross profit/loss: {{ money(m.profit) }}</p>
        </div>

        <div class="card">
            <h2>All recorded expenses</h2>
            <div class="metric">{{ money(expenses_total) }}</div>
            <p class="muted">
                Overall net result = gross sales profit/loss
                minus all recorded expenses.
            </p>
        </div>

    </div>

    <div class="panel">
        <h2>Low-stock report</h2>

        <div class="table-wrap">
        <table>

            <tr>
                <th>Product</th>
                <th>Available</th>
                <th>Alert level</th>
                <th>Status</th>
            </tr>

            {% for p in low %}
            <tr>
                <td>{{ p.item }}</td>
                <td>{{ p.remaining_quantity }}</td>
                <td>{{ p.low_stock_level }}</td>
                <td>
                    {% if p.remaining_quantity==0 %}
                        OUT OF STOCK
                    {% else %}
                        LOW STOCK
                    {% endif %}
                </td>
            </tr>

            {% else %}
            <tr><td colspan="4">No low-stock alerts.</td></tr>
            {% endfor %}

        </table>
        </div>
    </div>

    <div class="actions">
        <a class="btn" href="/sales">Full sales history</a>
        <a class="btn" href="/deliveries">Delivery history</a>
        <a class="btn" href="/expenses">Expense history</a>
    </div>
    """

    return page(
        "Reports",
        body,
        d=daily,
        m=monthly,
        expenses_total=expenses_total,
        low=low
    )

# ==================== CHANGE PASSWORD ====================

@app.route("/admin/password", methods=["GET", "POST"])
@admin_required
def change_password():

    body = """
    <div class="panel">
        <h1>Change administrator password</h1>

        <form method="post">

            <label>Current password</label>
            <input type="password" name="old" required>

            <label>New password (at least 8 characters)</label>
            <input type="password" name="new"
                   minlength="8" required>

            <label>Confirm new password</label>
            <input type="password" name="confirm"
                   minlength="8" required>

            <button class="btn">Change password</button>

        </form>
    </div>
    """

    if request.method == "POST":

        db = get_db()

        row = db.execute(
            "SELECT * FROM admin WHERE id=1"
        ).fetchone()

        new = request.form.get("new", "")

        if not row or not password_matches(
            row,
            request.form.get("old", "")
        ):
            flash("Current password is incorrect.", "error")

        elif len(new) < 8 or new != request.form.get("confirm", ""):
            flash(
                "New passwords must match and contain at least 8 characters.",
                "error"
            )

        else:
            admin_cols = {
                r["name"]
                for r in db.execute(
                    "PRAGMA table_info(admin)"
                ).fetchall()
            }

            if "salt" in admin_cols:
                db.execute("""
                    UPDATE admin
                    SET password_hash=?, salt=''
                    WHERE id=1
                """, (generate_password_hash(new),))
            else:
                db.execute("""
                    UPDATE admin
                    SET password_hash=?
                    WHERE id=1
                """, (generate_password_hash(new),))

            db.commit()

            flash(
                "Administrator password changed.",
                "success"
            )

            return redirect(url_for("dashboard"))

    return page("Change password", body)

# ==================== ERROR HANDLING ====================

@app.errorhandler(404)
def not_found(error):

    return page(
        "Page not found",
        """
        <div class='panel'>
            <h1>Page not found</h1>
            <p>The requested page does not exist.</p>
            <a class='btn' href='/'>Home</a>
        </div>
        """
    ), 404

@app.errorhandler(500)
def server_error(error):

    app.logger.exception("Unexpected server error")

    return page(
        "Server error",
        """
        <div class='panel'>
            <h1>Something went wrong</h1>
            <p>Check the Render logs for the detailed error.</p>
        </div>
        """
    ), 500

# ==================== START APPLICATION ====================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=False
    )
