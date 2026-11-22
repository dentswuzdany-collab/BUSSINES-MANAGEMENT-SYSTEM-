from flask import Flask, request, redirect, url_for, session, render_template, flash

app = Flask(__name__)

app.secret_key = "change-this-to-a-long-random-secret-key"
import sqlite3
import hashlib
import secrets
import hmac
from datetime import datetime, date
import calendar

# ==================================================
# ADVANCED STOCK AND BUSINESS MANAGEMENT SYSTEM
# ==================================================

DATABASE = "stock_database.db"

conn = sqlite3.connect(DATABASE)
conn.execute("PRAGMA foreign_keys = ON")
cursor = conn.cursor()


# ==================================================
# 1. DATABASE SETUP
# ==================================================

cursor.execute("""
CREATE TABLE IF NOT EXISTS stock (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item TEXT NOT NULL,
    initial_quantity INTEGER NOT NULL,
    unit_price REAL NOT NULL,
    total_amount REAL NOT NULL,
    remaining_quantity INTEGER NOT NULL,
    date_added TEXT NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS admin (
    id INTEGER PRIMARY KEY,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL
)
""")

cursor.execute("""
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
)
""")

# Separate stock delivery records
cursor.execute("""
CREATE TABLE IF NOT EXISTS deliveries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_id INTEGER NOT NULL,
    item TEXT NOT NULL,
    quantity_received INTEGER NOT NULL,
    buying_price REAL NOT NULL,
    total_cost REAL NOT NULL,
    delivery_date TEXT NOT NULL,
    FOREIGN KEY(stock_id) REFERENCES stock(id)
)
""")

conn.commit()


# ==================================================
# 2. ADMIN PASSWORD SYSTEM
# ==================================================

def hash_password(password, salt):

    return hashlib.pbkdf2_hmac(
        "sha256",
        password.encode(),
        bytes.fromhex(salt),
        200000
    ).hex()


def admin_exists():

    cursor.execute("SELECT COUNT(*) FROM admin")
    return cursor.fetchone()[0] > 0


def create_admin():

    print("\n========== CREATE ADMIN PASSWORD ==========")

    while True:

        password = input("Create admin password: ")

        if len(password) < 6:
            print("Password must contain at least 6 characters.")
            continue

        confirm = input("Confirm password: ")

        if password != confirm:
            print("Passwords do not match.")
            continue

        salt = secrets.token_hex(16)
        password_hash = hash_password(password, salt)

        cursor.execute("""
        INSERT INTO admin (id, password_hash, salt)
        VALUES (1, ?, ?)
        """, (password_hash, salt))

        conn.commit()

        print("\nAdministrator account created successfully!")
        return


def verify_admin():

    print("\n========== ADMIN AUTHENTICATION ==========")

    password = input("Enter admin password: ")

    cursor.execute("""
    SELECT password_hash, salt
    FROM admin WHERE id = 1
    """)

    record = cursor.fetchone()

    if not record:
        print("Administrator account not found.")
        return False

    saved_hash, salt = record

    entered_hash = hash_password(password, salt)

    if hmac.compare_digest(saved_hash, entered_hash):
        print("Access granted!")
        return True

    print("Incorrect password! Access denied.")
    return False


def change_password():

    print("\n========== CHANGE ADMIN PASSWORD ==========")

    if not verify_admin():
        return

    while True:

        new_password = input("Enter new password: ")

        if len(new_password) < 6:
            print("Password must have at least 6 characters.")
            continue

        confirm = input("Confirm new password: ")

        if new_password != confirm:
            print("Passwords do not match.")
            continue

        salt = secrets.token_hex(16)
        password_hash = hash_password(new_password, salt)

        cursor.execute("""
        UPDATE admin
        SET password_hash = ?, salt = ?
        WHERE id = 1
        """, (password_hash, salt))

        conn.commit()

        print("Admin password changed successfully!")
        return


# ==================================================
# 3. HELPER FUNCTIONS
# ==================================================

def money(value):
    return f"UGX {value:,.2f}"


def get_integer(message, minimum=0):

    while True:

        try:
            value = int(input(message))

            if value < minimum:
                print("Enter a value of at least", minimum)
                continue

            return value

        except ValueError:
            print("Enter a valid whole number.")


def get_number(message, minimum=0):

    while True:

        try:
            value = float(input(message))

            if value < minimum:
                print("Invalid amount.")
                continue

            return value

        except ValueError:
            print("Enter a valid number.")


def get_date(message):

    while True:

        value = input(message).strip()

        try:
            return datetime.strptime(
                value, "%Y-%m-%d"
            ).date()

        except ValueError:
            print("Use date format YYYY-MM-DD.")


def get_month(message):

    while True:

        value = input(message).strip()

        try:
            return datetime.strptime(
                value, "%Y-%m"
            ).strftime("%Y-%m")

        except ValueError:
            print("Use month format YYYY-MM.")


def print_separator():
    print("-" * 48)


# ==================================================
# 4. ADD NEW PRODUCT - ADMIN ONLY
# ==================================================

def add_product():

    print("\n========== ADD NEW PRODUCT ==========")

    if not verify_admin():
        return

    item = input("Enter product name: ").strip()

    if not item:
        print("Product name cannot be empty.")
        return

    quantity = get_integer(
        "Enter original quantity: ", 1
    )

    buying_price = get_number(
        "Enter buying price per unit: ", 0
    )

    total = quantity * buying_price

    cursor.execute("""
    INSERT INTO stock (
        item,
        initial_quantity,
        unit_price,
        total_amount,
        remaining_quantity,
        date_added
    )
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        item,
        quantity,
        buying_price,
        total,
        quantity,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()

    print("\nPRODUCT SUCCESSFULLY ADDED")
    print_separator()
    print("Product:", item)
    print("Original quantity:", quantity)
    print("Buying price:", money(buying_price))
    print("Original stock value:", money(total))
    print("Available quantity:", quantity)


# ==================================================
# 5. VIEW INVENTORY - OPEN ACCESS
# ==================================================

def view_inventory():

    print("\n========== CURRENT INVENTORY ==========")

    cursor.execute("SELECT * FROM stock ORDER BY id")

    records = cursor.fetchall()

    if not records:
        print("No products recorded.")
        return

    for r in records:

        print_separator()
        print("Product ID:", r[0])
        print("Product:", r[1])
        print("Original quantity:", r[2])
        print("Current average buying price:", money(r[3]))
        print("Original stock value:", money(r[4]))
        print("Available stock:", r[5])
        print("Date added:", r[6])


# ==================================================
# 6. SEARCH PRODUCT - OPEN ACCESS
# ==================================================

def search_product():

    print("\n========== SEARCH PRODUCT ==========")

    name = input("Enter product name: ").strip()

    cursor.execute("""
    SELECT id, item, initial_quantity,
           unit_price, remaining_quantity
    FROM stock
    WHERE item LIKE ?
    ORDER BY id
    """, ('%' + name + '%',))

    records = cursor.fetchall()

    if not records:
        print("Product not found.")
        return

    for r in records:

        print_separator()
        print("ID:", r[0])
        print("Product:", r[1])
        print("Original quantity:", r[2])
        print("Average buying price:", money(r[3]))
        print("Available stock:", r[4])


# ==================================================
# 7. EDIT PRODUCT - ADMIN ONLY
# ==================================================

def edit_product():

    print("\n========== EDIT PRODUCT ==========")

    if not verify_admin():
        return

    product_id = get_integer("Enter product ID: ", 1)

    cursor.execute(
        "SELECT * FROM stock WHERE id = ?",
        (product_id,)
    )

    r = cursor.fetchone()

    if not r:
        print("Product not found.")
        return

    print("\nProduct:", r[1])
    print("Original quantity:", r[2])
    print("Current average buying price:", money(r[3]))

    print("\n1. Edit product name")
    print("2. Edit buying price")
    print("3. Cancel")

    choice = input("Choose option: ").strip()

    if choice == "1":

        new_name = input("Enter new name: ").strip()

        if not new_name:
            print("Name cannot be empty.")
            return

        cursor.execute("""
        UPDATE stock SET item = ?
        WHERE id = ?
        """, (new_name, product_id))

    elif choice == "2":

        new_price = get_number(
            "Enter new buying price: ", 0
        )

        new_total = r[2] * new_price

        cursor.execute("""
        UPDATE stock
        SET unit_price = ?, total_amount = ?
        WHERE id = ?
        """, (new_price, new_total, product_id))

    elif choice == "3":
        print("Cancelled.")
        return

    else:
        print("Invalid choice.")
        return

    conn.commit()
    print("Product updated successfully!")


# ==================================================
# 8. RECORD SALES - OPEN ACCESS
# ==================================================

def record_sale():

    print("\n========== RECORD PRODUCT SALE ==========")

    product_id = get_integer("Enter product ID: ", 1)

    cursor.execute("""
    SELECT id, item, initial_quantity,
           unit_price, remaining_quantity
    FROM stock
    WHERE id = ?
    """, (product_id,))

    product = cursor.fetchone()

    if not product:
        print("Product not found.")
        return

    item = product[1]
    original = product[2]
    buying_price = product[3]
    available = product[4]

    print("\nProduct:", item)
    print("Buying price:", money(buying_price))
    print("Available stock:", available)

    if available == 0:
        print("OUT OF STOCK!")
        return

    quantity = get_integer("Enter quantity sold: ", 1)

    if quantity > available:
        print("SALE REJECTED!")
        print("Only", available, "units available.")
        return

    selling_price = get_number(
        "Enter selling price per unit: ", 0
    )

    revenue = quantity * selling_price
    cost = quantity * buying_price
    result = revenue - cost
    remaining = available - quantity

    try:

        cursor.execute("""
        UPDATE stock
        SET remaining_quantity = ?
        WHERE id = ? AND remaining_quantity >= ?
        """, (remaining, product_id, quantity))

        if cursor.rowcount != 1:
            conn.rollback()
            print("Stock changed. Sale rejected.")
            return

        cursor.execute("""
        INSERT INTO sales (
            stock_id, item, quantity_sold,
            buying_price, selling_price,
            revenue, cost, profit_loss, sale_date
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            product_id, item, quantity,
            buying_price, selling_price,
            revenue, cost, result,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()

    except sqlite3.Error as error:
        conn.rollback()
        print("Sale error:", error)
        return

    print("\n========== SALES RECEIPT ==========")
    print("Product:", item)
    print("Quantity sold:", quantity)
    print("Buying price:", money(buying_price))
    print("Selling price:", money(selling_price))
    print_separator()
    print("Total revenue:", money(revenue))
    print("Total cost:", money(cost))

    if result < 0:
        print("\nYOU SOLD AT A LOSS!")
        print("Total loss:", money(abs(result)))

    elif result > 0:
        print("\nYOU MADE A PROFIT!")
        print("Total profit:", money(result))

    else:
        print("\nBREAK EVEN!")

    print_separator()
    print("Original quantity:", original)
    print("Remaining quantity:", remaining)
    print("SALE COMPLETED!")


# ==================================================
# 9. RECORD STOCK DELIVERY - ADMIN ONLY
# ==================================================

def record_delivery():

    print("\n========== RECORD STOCK DELIVERY ==========")

    if not verify_admin():
        return

    product_id = get_integer("Enter product ID: ", 1)

    cursor.execute("""
    SELECT id, item, unit_price, remaining_quantity
    FROM stock
    WHERE id = ?
    """, (product_id,))

    product = cursor.fetchone()

    if not product:
        print("Product not found.")
        return

    item = product[1]
    old_price = product[2]
    old_quantity = product[3]

    print("\nProduct:", item)
    print("Available stock:", old_quantity)
    print("Current average buying price:", money(old_price))

    quantity = get_integer(
        "Enter quantity delivered: ", 1
    )

    delivery_price = get_number(
        "Enter buying price per delivered unit: ", 0
    )

    delivery_cost = quantity * delivery_price

    # Moving weighted average buying cost
    total_units = old_quantity + quantity

    if total_units > 0:
        new_average = (
            (old_quantity * old_price) +
            (quantity * delivery_price)
        ) / total_units
    else:
        new_average = delivery_price

    new_stock = total_units

    try:

        cursor.execute("""
        UPDATE stock
        SET remaining_quantity = ?,
            unit_price = ?
        WHERE id = ?
        """, (new_stock, new_average, product_id))

        cursor.execute("""
        INSERT INTO deliveries (
            stock_id, item, quantity_received,
            buying_price, total_cost, delivery_date
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            product_id,
            item,
            quantity,
            delivery_price,
            delivery_cost,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        conn.commit()

    except sqlite3.Error as error:
        conn.rollback()
        print("Delivery error:", error)
        return

    print("\n========== DELIVERY RECEIPT ==========")
    print("Product:", item)
    print("Quantity received:", quantity)
    print("Delivery buying price:", money(delivery_price))
    print("Delivery cost:", money(delivery_cost))
    print("Previous stock:", old_quantity)
    print("New available stock:", new_stock)
    print("New average buying price:", money(new_average))
    print("DELIVERY RECORDED SUCCESSFULLY!")


# ==================================================
# 10. STOCK DELIVERY HISTORY - ADMIN ONLY
# ==================================================

def delivery_history():

    print("\n========== STOCK DELIVERY HISTORY ==========")

    if not verify_admin():
        return

    cursor.execute("""
    SELECT id, item, quantity_received,
           buying_price, total_cost, delivery_date
    FROM deliveries
    ORDER BY id DESC
    """)

    records = cursor.fetchall()

    if not records:
        print("No deliveries recorded.")
        return

    for r in records:

        print_separator()
        print("Delivery ID:", r[0])
        print("Product:", r[1])
        print("Quantity received:", r[2])
        print("Buying price:", money(r[3]))
        print("Total delivery cost:", money(r[4]))
        print("Delivery date:", r[5])


# ==================================================
# 11. DAILY SALES REPORT - ADMIN ONLY
# ==================================================

def daily_sales_report():

    print("\n========== DAILY SALES REPORT ==========")

    if not verify_admin():
        return

    print("Enter the date to examine.")
    print("Format: YYYY-MM-DD")

    report_date = get_date(
        "Enter report date: "
    ).strftime("%Y-%m-%d")

    cursor.execute("""
    SELECT
        COALESCE(SUM(quantity_sold), 0),
        COALESCE(SUM(revenue), 0),
        COALESCE(SUM(cost), 0),
        COALESCE(SUM(profit_loss), 0),
        COUNT(*)
    FROM sales
    WHERE date(sale_date) = ?
    """, (report_date,))

    r = cursor.fetchone()

    print("\n========== DAILY REPORT ==========")
    print("Report date:", report_date)
    print("Number of sales transactions:", r[4])
    print("Total units sold:", r[0])
    print("Total sales revenue:", money(r[1]))
    print("Total cost of goods sold:", money(r[2]))

    if r[3] > 0:
        print("DAILY PROFIT:", money(r[3]))
    elif r[3] < 0:
        print("DAILY LOSS:", money(abs(r[3])))
    else:
        print("DAILY RESULT: BREAK EVEN")

    print_separator()

    cursor.execute("""
    SELECT item, SUM(quantity_sold),
           SUM(revenue), SUM(profit_loss)
    FROM sales
    WHERE date(sale_date) = ?
    GROUP BY item
    ORDER BY item
    """, (report_date,))

    records = cursor.fetchall()

    print("\nPRODUCT BREAKDOWN")

    for row in records:

        print_separator()
        print("Product:", row[0])
        print("Quantity sold:", row[1])
        print("Revenue:", money(row[2]))
        print("Profit/Loss:", money(row[3]))

    if not records:
        print("No sales recorded on this date.")


# ==================================================
# 12. MONTHLY PROFIT REPORT - ADMIN ONLY
# ==================================================

def monthly_profit_report():

    print("\n========== MONTHLY PROFIT REPORT ==========")

    if not verify_admin():
        return

    print("Enter month in YYYY-MM format.")

    month = get_month("Enter report month: ")

    cursor.execute("""
    SELECT
        COALESCE(SUM(quantity_sold), 0),
        COALESCE(SUM(revenue), 0),
        COALESCE(SUM(cost), 0),
        COALESCE(SUM(profit_loss), 0),
        COUNT(*)
    FROM sales
    WHERE strftime('%Y-%m', sale_date) = ?
    """, (month,))

    r = cursor.fetchone()

    print("\n========== MONTHLY FINANCIAL REPORT ==========")
    print("Reporting month:", month)
    print("Sales transactions:", r[4])
    print("Total units sold:", r[0])
    print("Total sales revenue:", money(r[1]))
    print("Total cost of goods sold:", money(r[2]))

    if r[3] > 0:
        print("\nMONTHLY PROFIT:", money(r[3]))
    elif r[3] < 0:
        print("\nMONTHLY LOSS:", money(abs(r[3])))
    else:
        print("\nMONTHLY RESULT: BREAK EVEN")

    print_separator()

    cursor.execute("""
    SELECT item,
           SUM(quantity_sold),
           SUM(revenue),
           SUM(cost),
           SUM(profit_loss)
    FROM sales
    WHERE strftime('%Y-%m', sale_date) = ?
    GROUP BY item
    ORDER BY SUM(revenue) DESC
    """, (month,))

    records = cursor.fetchall()

    print("\nPRODUCT FINANCIAL BREAKDOWN")

    for row in records:

        print_separator()
        print("Product:", row[0])
        print("Quantity sold:", row[1])
        print("Revenue:", money(row[2]))
        print("Cost:", money(row[3]))
        print("Profit/Loss:", money(row[4]))

    if not records:
        print("No sales recorded for this month.")


# ==================================================
# 13. SALES HISTORY - ADMIN ONLY
# ==============================================

def sales_history():

    print("\n========== SALES HISTORY ==========")

    if not verify_admin():
        return

    print("1. View all sales")
    print("2. Search sales by date")
    print("3. Search sales by product")

    choice = input("Choose option: ").strip()

    if choice == "1":

        cursor.execute("""
        SELECT * FROM sales ORDER BY id DESC
        """)

    elif choice == "2":

        report_date = get_date("Enter date (YYYY-MM-DD): ")

        cursor.execute("""
        SELECT * FROM sales
        WHERE date(sale_date) = ?
        ORDER BY id DESC
        """, (report_date,))

    elif choice == "3":

        item = input("Enter product name: ").strip()

        cursor.execute("""
        SELECT * FROM sales
        WHERE item LIKE ?
        ORDER BY id DESC
        """, ('%' + item + '%',))

    else:
        print("Invalid choice.")
        return

    records = cursor.fetchall()

    if not records:
        print("No sales records found.")
        return

    for r in records:
        print_separator()
        print("Sale ID:", r[0])
        print("Product:", r[2])
        print("Quantity:", r[3])
        print("Buying price:", money(r[4]))
        print("Selling price:", money(r[5]))
        print("Revenue:", money(r[6]))
        print("Cost:", money(r[7]))
        print("Profit/loss:", money(r[8]))
        print("Sale date:", r[9])


# ==========================================================
# 14. LOW STOCK REPORT - ADMIN ONLY
# ====================================================

def low_stock_report():

    print("\n========== LOW STOCK REPORT ==========")

    if not verify_admin():
        return

    cursor.execute("""
    SELECT id, item, remaining_quantity,
           low_stock_level, unit_price
    FROM stock
    WHERE remaining_quantity <= low_stock_level
    ORDER BY remaining_quantity ASC
    """)

    records = cursor.fetchall()

    if not records:
        print("GOOD NEWS! No products are below their stock limits.")
        return

    print("Products requiring replenishment:")

    for r in records:
        print_separator()
        print("Product ID:", r[0])
        print("Product:", r[1])
        print("Available quantity:", r[2])
        print("Minimum stock level:", r[3])
        print("Estimated replenishment value:",
              money(max(0, r[3] - r[2]) * r[4]))

        if r[2] == 0:
            print("STATUS: OUT OF STOCK")
        else:
            print("STATUS: LOW STOCK")


# ==========================================================
# 15. BUSINESS SUMMARY - ADMIN ONLY
# =========================================================

def business_summary():

    print("\n========== BUSINESS SUMMARY ==========")

    if not verify_admin():
        return

    cursor.execute("""
    SELECT
        COUNT(*),
        COALESCE(SUM(remaining_quantity * unit_price), 0),
        COALESCE(SUM(remaining_quantity), 0)
    FROM stock
    """)

    stock_data = cursor.fetchone()

    cursor.execute("""
    SELECT
        COUNT(*),
        COALESCE(SUM(revenue), 0),
        COALESCE(SUM(cost), 0),
        COALESCE(SUM(profit_loss), 0)
    FROM sales
    """)

    sales_data = cursor.fetchone()

    cursor.execute("""
    SELECT
        COUNT(*),
        COALESCE(SUM(quantity_received), 0),
        COALESCE(SUM(total_cost), 0)
    FROM deliveries
    """)

    delivery_data = cursor.fetchone()

    cursor.execute("""
    SELECT
        COUNT(*),
        COALESCE(SUM(amount), 0)
    FROM expenses
    """)

    expense_data = cursor.fetchone()

    print("\n---------- INVENTORY SUMMARY ----------")
    print("Different products:", stock_data[0])
    print("Available stock units:", stock_data[2])
    print("Current stock value:", money(stock_data[1]))

    print("\n---------- SALES SUMMARY ----------")
    print("Sales transactions:", sales_data[0])
    print("Total revenue:", money(sales_data[1]))
    print("Cost of goods sold:", money(sales_data[2]))
    print("Gross profit/loss:", money(sales_data[3]))

    print("\n---------- DELIVERY SUMMARY ----------")
    print("Number of deliveries:", delivery_data[0])
    print("Units received:", delivery_data[1])
    print("Total delivery cost:", money(delivery_data[2]))

    print("\n---------- EXPENSE SUMMARY ----------")
    print("Expense records:", expense_data[0])
    print("Total recorded expenses:", money(expense_data[1]))

    print("\n---------- OVERALL BUSINESS POSITION ----------")

    net = sales_data[3] - expense_data[1]

    print("Total revenue:", money(sales_data[1]))
    print("Gross profit/loss:", money(sales_data[3]))
    print("Business expenses:", money(expense_data[1]))
    print("Net profit/loss:", money(net))
    print("Current stock asset value:", money(stock_data[1]))

    print("\nNote: Stock value is an inventory asset,")
    print("not additional profit.")


# ==========================================================
# 16. RECORD BUSINESS EXPENSE - ADMIN ONLY
# ==========================================================

def record_expense():

    print("\n========== RECORD BUSINESS EXPENSE ==========")

    if not verify_admin():
        return

    description = input("Enter expense description: ").strip()

    if not description:
        print("Description cannot be empty.")
        return

    amount = get_number("Enter expense amount: ", 0.01)

    expense_date = input(
        "Enter expense date (YYYY-MM-DD), or press Enter for today: "
    ).strip()

    if expense_date:
        try:
            expense_date = datetime.strptime(
                expense_date, "%Y-%m-%d"
            ).strftime("%Y-%m-%d")
        except ValueError:
            print("Invalid date.")
            return
    else:
        expense_date = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
    INSERT INTO expenses (description, amount, expense_date)
    VALUES (?, ?, ?)
    """, (description, amount, expense_date))

    conn.commit()

    print("EXPENSE RECORDED SUCCESSFULLY!")
    print("Description:", description)
    print("Amount:", money(amount))
    print("Date:", expense_date)


# ==========================================================
# 17. VIEW EXPENSE HISTORY - ADMIN ONLY
# ==========================================================

def expense_history():

    print("\n========== EXPENSE HISTORY ==========")

    if not verify_admin():
        return

    cursor.execute("""
    SELECT * FROM expenses ORDER BY id DESC
    """)

    records = cursor.fetchall()

    if not records:
        print("No expenses recorded.")
        return

    for r in records:
        print_separator()
        print("Expense ID:", r[0])
        print("Description:", r[1])
        print("Amount:", money(r[2]))
        print("Date:", r[3])


# ==========================================================
# 18. MAIN MENU
# ==========================================================

def main_menu():

    print("\n")
    print("=" * 55)
    print("     ADVANCED STOCK AND BUSINESS MANAGEMENT")
    print("=" * 55)

    while True:

        print("\n============== MAIN MENU ==============")

        print("\n1. Add new product [ADMIN]")
        print("2. View inventory")
        print("3. Search product")
        print("4. Edit product [ADMIN]")
        print("5. Record product sale")
        print("6. Record stock delivery [ADMIN]")
        print("7. View stock delivery history [ADMIN]")

        print("\n---------- FINANCIAL REPORTS ----------")

        print("8. Daily sales report [ADMIN]")
        print("9. Monthly profit report [ADMIN]")
        print("10. View sales history [ADMIN]")
        print("11. Business summary [ADMIN]")
        print("12. Low stock report [ADMIN]")

        print("\n---------- BUSINESS EXPENSES ----------")

        print("13. Record business expense [ADMIN]")
        print("14. View expense history [ADMIN]")

        print("\n---------- ADMIN SETTINGS ----------")

        print("15. Change admin password [ADMIN]")

        print("\n0. Exit system")

        choice = input("\nSelect an option: ").strip()

        if choice == "1":
            add_product()

        elif choice == "2":
            view_inventory()

        elif choice == "3":
            search_product()

        elif choice == "4":
            edit_product()

        elif choice == "5":
            record_sale()

        elif choice == "6":
            record_delivery()

        elif choice == "7":
            delivery_history()

        elif choice == "8":
            daily_sales_report()

        elif choice == "9":
            monthly_profit_report()

        elif choice == "10":
            sales_history()

        elif choice == "11":
            business_summary()

        elif choice == "12":
            low_stock_report()

        elif choice == "13":
            record_expense()

        elif choice == "14":
            expense_history()

        elif choice == "15":
            change_password()

        elif choice == "0":
            print("\nThank you for using the management system.")
            print("Goodbye!")
            break

        else:
            print("INVALID OPTION! Please try again.")


# ==========================================================
# 19. PROGRAM STARTUP
# ==========================================================

if __name__ == "__main__":

    try:

        if not admin_exists():
            create_admin()

        main_menu()

    except KeyboardInterrupt:
        print("\n\nSystem interrupted.")

    except sqlite3.Error as error:
        print("\nDatabase error:", error)

    finally:
        conn.close()

@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Business Management System</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">

        <style>
            body {
                font-family: Arial, sans-serif;
                background: #f1f5f9;
                margin: 0;
                text-align: center;
            }

            header {
                background: #123456;
                color: white;
                padding: 35px 15px;
            }

            .container {
                padding: 25px 15px;
            }

            .card {
                background: white;
                max-width: 500px;
                margin: 20px auto;
                padding: 25px;
                border-radius: 12px;
                box-shadow: 0 3px 10px #ccc;
            }

            .status {
                color: green;
                font-weight: bold;
            }

            footer {
                padding: 20px;
                color: #555;
            }
        </style>
    </head>

    <body>

        <header>
            <h1>BUSINESS MANAGEMENT SYSTEM</h1>
            <p>Manage your business efficiently</p>
        </header>

        <div class="container">
            <div class="card">
                <h2>Welcome!</h2>

                <p>
                    Your Business Management System
                    is now running successfully.
                </p>

                <p class="status">
                    SYSTEM STATUS: ONLINE
                </p>
            </div>
        </div>

        <footer>
            Business Management System
        </footer>

    </body>
    </html>
    """
if __name__ == "__main__":
    app.run(debug=True)