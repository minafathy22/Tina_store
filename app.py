from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import logging
import pandas as pd
from datetime import datetime, timedelta
import os
import io
from datetime import datetime
from flask import Flask, request, redirect, url_for, flash, render_template
from sqlite3 import IntegrityError
from config import Config

app = Flask(__name__)
app.config.from_object(Config)

# Initialize LoginManager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# User model
class User(UserMixin):
    def __init__(self, id, username, role):
        self.id = id
        self.username = username
        self.role = role

# Predefined users with hashed passwords
users = {
    "mina": {"password": generate_password_hash("01287182366"), "role": "admin"},
    "tina": {"password": generate_password_hash("01225253899"), "role": "admin"},
    "bebo": {"password": generate_password_hash("01032279898"), "role": "admin"},
    "marco": {"password": generate_password_hash("123456"), "role": "agent"},
}

@login_manager.user_loader
def load_user(user_id):
    if user_id in users:
        return User(user_id, user_id, users[user_id]["role"])
    return None

# Database connection
def get_db_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row  # Enable dictionary-like access
    return conn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create tables
def create_tables():
    conn = get_db_connection()
    c = conn.cursor()

    # Create inventory table
    c.execute("""
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT,
            product_type TEXT,
            gender TEXT,
            size TEXT,
            quantity INTEGER,
            cost_price REAL,
            selling_price REAL,
            adding_to_inventory_date TEXT,
            original_stock INTEGER
        )
    """)

    # Create sales table
    c.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            product_name TEXT,
            product_type TEXT,
            gender TEXT,
            size TEXT,
            quantity INTEGER,
            selling_price REAL,
            discount_percentage REAL,
            total_amount REAL,
            sale_datetime TEXT,
            customer_id INTEGER,
            payment_type TEXT,
            action_date TEXT
        )
    """)

    # Create finance table with sale_id
    c.execute("""
        CREATE TABLE IF NOT EXISTS finance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_type TEXT,
            amount REAL,
            transaction_datetime date,
            action_date date,
            sale_id INTEGER,
            FOREIGN KEY (sale_id) REFERENCES sales(id)
            
        )
    """)

    # Create CRM table with loyalty program fields
    c.execute("""
        CREATE TABLE IF NOT EXISTS crm (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_name TEXT,
            contact_info TEXT UNIQUE,
            how_know_us TEXT,
            last_purchase_date date,  -- Can be NULL if no purchases
            birthday_date date,
            creation_date date,       -- New column for creation date
            segment TEXT,             -- New column for customer segmentation
            current_tier TEXT,        -- Loyalty tier (e.g., Bronze, Silver, Gold)
            total_points INTEGER,      -- Total loyalty points
            notes TEXT,               -- Additional notes about the customer
            email_notifications BOOLEAN DEFAULT TRUE,  -- Email notifications preference (default is TRUE)
            sms_notifications BOOLEAN DEFAULT TRUE,    -- SMS notifications preference (default is TRUE)
            whatsapp_notifications BOOLEAN DEFAULT TRUE -- WhatsApp notifications preference (default is TRUE)    
        )
    """)

    # Create customer_purchases table
    c.execute("""
        CREATE TABLE IF NOT EXISTS customer_purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            product_name TEXT,
            quantity INTEGER,
            total_amount REAL,
            purchase_date date,
            FOREIGN KEY (customer_id) REFERENCES crm(id)
        )
    """)

    # Create loyalty_rewards table
    c.execute("""
        CREATE TABLE IF NOT EXISTS loyalty_rewards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            points_redeemed INTEGER,
            reward_type TEXT,
            reward_date date,
            FOREIGN KEY (customer_id) REFERENCES crm(id)
        )
    """)

    conn.commit()
    conn.close()
    print("Tables and trigger created/updated successfully.")

def update_schema():
    conn = get_db_connection()
    c = conn.cursor()

    # Update sales table
    c.execute("PRAGMA table_info(sales)")
    sales_columns = [column[1] for column in c.fetchall()]
    if 'discount_amount' not in sales_columns:
        c.execute("ALTER TABLE sales ADD COLUMN discount_amount REAL")
    if 'redeemed_points' not in sales_columns:  # Add this check
        c.execute("ALTER TABLE sales ADD COLUMN redeemed_points INTEGER DEFAULT 0")  # Add the column with a default value
    if 'redeemed_points_amount' not in sales_columns:  # Add this check
        c.execute("ALTER TABLE sales ADD COLUMN redeemed_points_amount REAL DEFAULT 0.0")  # Add the column with a default value

    # Update inventory table
    c.execute("PRAGMA table_info(inventory)")
    inventory_columns = [column[1] for column in c.fetchall()]
    if 'adding_to_inventory_date' not in inventory_columns:
        c.execute("ALTER TABLE inventory ADD COLUMN adding_to_inventory_date TEXT")
    if 'original_stock' not in inventory_columns:
        c.execute("ALTER TABLE inventory ADD COLUMN original_stock INTEGER")

    # Update finance table
    c.execute("PRAGMA table_info(finance)")
    finance_columns = [column[1] for column in c.fetchall()]
    if 'sale_id' not in finance_columns:
        c.execute("ALTER TABLE finance ADD COLUMN sale_id INTEGER")
        c.execute("ALTER TABLE finance ADD FOREIGN KEY (sale_id) REFERENCES sales(id)")

    # Update crm table
    c.execute("PRAGMA table_info(crm)")
    crm_columns = [column[1] for column in c.fetchall()]
    if 'creation_date' not in crm_columns:
        c.execute("ALTER TABLE crm ADD COLUMN creation_date date")
    if 'segment' not in crm_columns:
        c.execute("ALTER TABLE crm ADD COLUMN segment TEXT")
    if 'current_tier' not in crm_columns:
        c.execute("ALTER TABLE crm ADD COLUMN current_tier TEXT")
    if 'total_points' not in crm_columns:
        c.execute("ALTER TABLE crm ADD COLUMN total_points INTEGER")
    if 'notes' not in crm_columns:
        c.execute("ALTER TABLE crm ADD COLUMN notes TEXT")
    if 'email_notifications' not in crm_columns:
        c.execute("ALTER TABLE crm ADD COLUMN email_notifications BOOLEAN DEFAULT TRUE")
    if 'sms_notifications' not in crm_columns:
        c.execute("ALTER TABLE crm ADD COLUMN sms_notifications BOOLEAN DEFAULT TRUE")
    if 'whatsapp_notifications' not in crm_columns:
        c.execute("ALTER TABLE crm ADD COLUMN whatsapp_notifications BOOLEAN DEFAULT TRUE")

    # Update customer_purchases table
    c.execute("PRAGMA table_info(customer_purchases)")
    customer_purchases_columns = [column[1] for column in c.fetchall()]
    if 'purchase_date' not in customer_purchases_columns:
        c.execute("ALTER TABLE customer_purchases ADD COLUMN purchase_date date")
    if 'discount_percentage' not in customer_purchases_columns:  # Add this check
        c.execute("ALTER TABLE customer_purchases ADD COLUMN discount_percentage REAL DEFAULT 0.0")  # Add the column with a default value
    if 'discount_amount' not in customer_purchases_columns:  # Add this check
        c.execute("ALTER TABLE customer_purchases ADD COLUMN discount_amount REAL DEFAULT 0.0")  # Add the column with a default value
    if 'redeemed_points' not in customer_purchases_columns:  # Add this check
        c.execute("ALTER TABLE customer_purchases ADD COLUMN redeemed_points INTEGER DEFAULT 0")  # Add the column with a default value
    if 'redeemed_points_amount' not in customer_purchases_columns:  # Add this check
        c.execute("ALTER TABLE customer_purchases ADD COLUMN redeemed_points_amount REAL DEFAULT 0.0")  # Add the column with a default value

    # Update loyalty_rewards table
    c.execute("PRAGMA table_info(loyalty_rewards)")
    loyalty_rewards_columns = [column[1] for column in c.fetchall()]
    if 'reward_date' not in loyalty_rewards_columns:
        c.execute("ALTER TABLE loyalty_rewards ADD COLUMN reward_date date")

    conn.commit()
    conn.close()
    print("Schema updated successfully.")

# Home Route
@app.route("/")
@login_required
def home():
    try:
        # Get date range from query parameters
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        # Validate date range
        if start_date and end_date:
            try:
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
                end_date = datetime.strptime(end_date, "%Y-%m-%d")
                if start_date > end_date:
                    flash("Start date cannot be after end date.", "error")
                    return redirect(url_for("home"))
            except ValueError:
                flash("Invalid date format. Please use YYYY-MM-DD.", "error")
                return redirect(url_for("home"))

        # Debugging: print the date range
        print("Start Date:", start_date)
        print("End Date:", end_date)

        conn = get_db_connection()

        # Fetch total sales, products, and customers within the date range
        total_sales_query = "SELECT SUM(total_amount) as total FROM sales WHERE sale_datetime BETWEEN ? AND ?"
        total_products_query = "SELECT COUNT(*) as total FROM inventory"
        total_customers_query = "SELECT COUNT(*) as total FROM crm"

        # Execute total sales query with date parameters
        total_sales = conn.execute(total_sales_query, (start_date, end_date)).fetchone()
        total_sales = total_sales["total"] if total_sales and total_sales["total"] is not None else 0

        # Execute total products query
        total_products = conn.execute(total_products_query).fetchone()
        total_products = total_products["total"] if total_products and total_products["total"] is not None else 0

        # Execute total customers query
        total_customers = conn.execute(total_customers_query).fetchone()
        total_customers = total_customers["total"] if total_customers and total_customers["total"] is not None else 0

        # Fetch sales data for trend analysis
        sales_query = """
            SELECT DATE(sale_datetime) as sale_date, SUM(total_amount) as total
            FROM sales WHERE sale_datetime BETWEEN ? AND ?
            GROUP BY DATE(sale_datetime) ORDER BY sale_date
        """
        sales_data = conn.execute(sales_query, (start_date, end_date)).fetchall() or []

        # Fetch sales by product type
        sales_by_type_query = """
            SELECT product_type, SUM(total_amount) as total
            FROM sales WHERE sale_datetime BETWEEN ? AND ?
            GROUP BY product_type
        """
        sales_by_type = conn.execute(sales_by_type_query, (start_date, end_date)).fetchall() or []

        # Fetch sales by product name
        sales_by_product_query = """
            SELECT product_name, SUM(total_amount) as total
            FROM sales WHERE sale_datetime BETWEEN ? AND ?
            GROUP BY product_name
        """
        sales_by_product = conn.execute(sales_by_product_query, (start_date, end_date)).fetchall() or []

        # Fetch sales by gender
        sales_by_gender_query = """
            SELECT gender, SUM(total_amount) as total
            FROM sales WHERE sale_datetime BETWEEN ? AND ?
            GROUP BY gender
        """
        sales_by_gender = conn.execute(sales_by_gender_query, (start_date, end_date)).fetchall() or []

        # Fetch sales by size
        sales_by_size_query = """
            SELECT size, SUM(total_amount) as total
            FROM sales WHERE sale_datetime BETWEEN ? AND ?
            GROUP BY size
        """
        sales_by_size = conn.execute(sales_by_size_query, (start_date, end_date)).fetchall() or []

        conn.close()

        # Extract data for charts
        sales_dates = [datetime.strptime(row['sale_date'], "%Y-%m-%d").strftime("%Y-%m-%d") for row in sales_data] if sales_data else []
        sales_totals = [row['total'] for row in sales_data] if sales_data else []

        sales_by_type_labels = [row['product_type'] for row in sales_by_type] if sales_by_type else []
        sales_by_type_values = [row['total'] for row in sales_by_type] if sales_by_type else []

        sales_by_product_labels = [row['product_name'] for row in sales_by_product] if sales_by_product else []
        sales_by_product_values = [row['total'] for row in sales_by_product] if sales_by_product else []

        sales_by_gender_labels = [row['gender'] for row in sales_by_gender] if sales_by_gender else []
        sales_by_gender_values = [row['total'] for row in sales_by_gender] if sales_by_gender else []

        sales_by_size_labels = [row['size'] for row in sales_by_size] if sales_by_size else []
        sales_by_size_values = [row['total'] for row in sales_by_size] if sales_by_size else []

        # Debugging: Print all variables to check the data
        print("Total Sales:", total_sales)
        print("Total Products:", total_products)
        print("Total Customers:", total_customers)
        print("Sales Dates:", sales_dates)
        print("Sales Totals:", sales_totals)
        print("Sales by Type Labels:", sales_by_type_labels)
        print("Sales by Type Values:", sales_by_type_values)
        print("Sales by Product Labels:", sales_by_product_labels)
        print("Sales by Product Values:", sales_by_product_values)
        print("Sales by Gender Labels:", sales_by_gender_labels)
        print("Sales by Gender Values:", sales_by_gender_values)
        print("Sales by Size Labels:", sales_by_size_labels)
        print("Sales by Size Values:", sales_by_size_values)

        return render_template(
            "index.html",
            total_sales=total_sales,
            total_products=total_products,
            total_customers=total_customers,
            sales_dates=sales_dates,
            sales_totals=sales_totals,
            sales_by_type_labels=sales_by_type_labels,
            sales_by_type_values=sales_by_type_values,
            sales_by_product_labels=sales_by_product_labels,
            sales_by_product_values=sales_by_product_values,
            sales_by_gender_labels=sales_by_gender_labels,  # Pass gender data
            sales_by_gender_values=sales_by_gender_values,  # Pass gender data
            sales_by_size_labels=sales_by_size_labels,      # Pass size data
            sales_by_size_values=sales_by_size_values       # Pass size data
        )

    except Exception as e:
        print(f"An error occurred in the home route: {str(e)}")
        flash("An error occurred while fetching data. Please try again.", "error")
        return redirect(url_for("home"))



# Configure logging
logging.basicConfig(filename="sales.log", level=logging.INFO)

@app.route("/sales", methods=["GET", "POST"])
@login_required
def sales():
    # Fetch products and customers from the database
    conn = get_db_connection()
    products = conn.execute("SELECT * FROM inventory").fetchall()
    customers = conn.execute("SELECT * FROM crm").fetchall()
    conn.close()

    # Convert Row objects to dictionaries
    products = [dict(product) for product in products]
    customers = [dict(customer) for customer in customers]

    if request.method == "POST":
        # Retrieve form data
        customer_id = request.form.get("customer_select")
        product_ids = request.form.getlist("product_select[]")
        quantities = request.form.getlist("quantity[]")
        prices = request.form.getlist("price[]")
        discounts = request.form.getlist("discount[]")
        payment_type = request.form.get("payment_type")
        use_loyalty_points = request.form.get("use_loyalty_points") == "true"  # Check if loyalty points are used
        loyalty_points_to_redeem = int(request.form.get("loyalty_points", 0))

        # Validate required fields
        if not validate_inputs(customer_id, product_ids, quantities, prices, discounts, payment_type):
            return redirect(url_for("sales"))

        conn = get_db_connection()
        c = conn.cursor()
        try:
            conn.execute("BEGIN TRANSACTION")

            # Fetch customer details
            customer = c.execute("SELECT * FROM crm WHERE id = ?", (customer_id,)).fetchone()
            if not customer:
                flash("Customer not found.", "error")
                return redirect(url_for("sales"))

            # Check if loyalty points are being used
            if use_loyalty_points and loyalty_points_to_redeem > customer["total_points"]:
                flash("Not enough loyalty points to redeem.", "error")
                return redirect(url_for("sales"))

            total_sale_amount = 0
            sale_summary = {
                "customer_id": customer_id,
                "products": [],
                "total_amount": 0
            }

            for product_id, quantity, price, discount in zip(product_ids, quantities, prices, discounts):
                # Validate and process each product
                if not update_inventory(c, product_id, quantity):
                    conn.rollback()
                    return redirect(url_for("sales"))

                # Fetch product details
                product = c.execute("SELECT * FROM inventory WHERE id = ?", (product_id,)).fetchone()

                # Calculate discounted total amount
                discount_percentage = float(discount)
                if discount_percentage < 0 or discount_percentage > 100:
                    flash("Discount must be between 0% and 100%.", "error")
                    conn.rollback()
                    return redirect(url_for("sales"))

                total_amount_before_discount = float(price) * int(quantity)
                discount_amount = (total_amount_before_discount * discount_percentage) / 100
                total_amount_after_discount = total_amount_before_discount - discount_amount

                # Deduct loyalty points if applicable
                redeemed_points_amount = 0
                if use_loyalty_points:
                    redeemed_points_amount = loyalty_points_to_redeem * 0.1  # 1 point = 0.1 EGP
                    total_amount_after_discount -= redeemed_points_amount

                    # Deduct points from the customer's total points
                    c.execute("UPDATE crm SET total_points = total_points - ? WHERE id = ?", 
                              (loyalty_points_to_redeem, customer_id))

                    # Record the redeemed points in the loyalty_rewards table
                    reward_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("""
                        INSERT INTO loyalty_rewards (customer_id, points_redeemed, reward_type, reward_date)
                        VALUES (?, ?, ?, ?)
                    """, (customer_id, loyalty_points_to_redeem, "points_redeemed", reward_date))

                # Record the sale
                sale_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute("""
                    INSERT INTO sales (
                        product_id, product_name, product_type, gender, size, quantity, 
                        selling_price, discount_percentage, discount_amount, redeemed_points,
                        redeemed_points_amount, total_amount, sale_datetime, customer_id, 
                        payment_type, action_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    product["id"], product["product_name"], product["product_type"], 
                    product["gender"], product["size"], quantity, price, discount_percentage,
                    discount_amount, loyalty_points_to_redeem if use_loyalty_points else 0,
                    redeemed_points_amount, total_amount_after_discount, sale_datetime, 
                    customer_id, payment_type, sale_datetime
                ))

                # Record the purchase in customer_purchases
                c.execute("""
                    INSERT INTO customer_purchases (
                        customer_id, product_name, quantity, total_amount, purchase_date,
                        discount_percentage, discount_amount, redeemed_points, redeemed_points_amount
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    customer_id, product["product_name"], quantity, total_amount_after_discount,
                    sale_datetime, discount_percentage, discount_amount,
                    loyalty_points_to_redeem if use_loyalty_points else 0, redeemed_points_amount
                ))

                # Update loyalty points (1 point for every 10 EGP spent)
                points_earned = int(total_amount_after_discount / 10)
                c.execute("""
                    UPDATE crm
                    SET total_points = total_points + ?, last_purchase_date = ?
                    WHERE id = ?
                """, (points_earned, sale_datetime, customer_id))

                # Add product to sale summary
                sale_summary["products"].append({
                    "name": product["product_name"],
                    "quantity": quantity,
                    "price": price,
                    "discount": discount
                })
                total_sale_amount += total_amount_after_discount

            # Commit the transaction
            conn.commit()
            flash(f"Sale completed successfully! Total amount: {total_sale_amount} EGP", "success")
            logging.info(f"Sale recorded for customer {customer_id} at {sale_datetime}")

        except IntegrityError as e:
            conn.rollback()
            flash(f"An error occurred: {str(e)}", "error")
            logging.error(f"Error recording sale: {str(e)}")
            return redirect(url_for("sales"))
        finally:
            conn.close()

    return render_template("sales.html", products=products, customers=customers)


def validate_inputs(customer_id, product_ids, quantities, prices, discounts, payment_type):
    """Validate that all required fields are filled."""
    if not (customer_id and product_ids and quantities and prices and discounts and payment_type):
        flash("Please fill all fields.", "error")
        return False
    return True


def update_inventory(c, product_id, quantity):
    """Update inventory and validate stock."""
    product = c.execute("SELECT * FROM inventory WHERE id = ?", (product_id,)).fetchone()
    if not product:
        flash(f"Product with ID {product_id} not found.", "error")
        return False

    try:
        quantity = int(quantity)
        if quantity <= 0:
            flash("Quantity must be a positive integer.", "error")
            return False
    except ValueError:
        flash("Invalid quantity.", "error")
        return False

    if quantity > product["quantity"]:
        flash(f"Insufficient stock for {product['product_name']}.", "error")
        return False

    new_quantity = product["quantity"] - quantity
    c.execute("UPDATE inventory SET quantity = ? WHERE id = ?", (new_quantity, product["id"]))

    # Notify if stock is low
    if new_quantity < 10:  # Threshold for low stock
        flash(f"Warning: Low stock for {product['product_name']}. Only {new_quantity} units remaining.", "warning")

    return True

# Inventory Route
@app.route("/inventory", methods=["GET", "POST"])
@login_required
def inventory():
    try:
        conn = get_db_connection()
        products = conn.execute("SELECT * FROM inventory").fetchall()
        products = [dict(product) for product in products]

        if request.method == "POST":
            if 'bulk_inventory_upload' in request.files:
                file = request.files['bulk_inventory_upload']
                if file.filename != '':
                    try:
                        df = pd.read_excel(file)
                        c = conn.cursor()
                        for index, row in df.iterrows():
                            product_name = row['Product Name']
                            product_type = row['Product Type']
                            gender = row['Gender']
                            size = row['Size']
                            quantity = row['Quantity']
                            cost_price = row['Cost Price']
                            selling_price = row['Selling Price']
                            adding_to_inventory_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                            # Check if the product exists with all fields except cost_price matching
                            existing_product_without_cost = c.execute("""
                                SELECT * FROM inventory 
                                WHERE product_name = ? AND product_type = ? AND gender = ? AND size = ?
                            """, (product_name, product_type, gender, size)).fetchone()

                            if existing_product_without_cost:
                                # Calculate average cost price
                                old_cost_price = existing_product_without_cost["cost_price"]
                                new_cost_price = (old_cost_price + cost_price) / 2  # Average cost

                                # Update quantity and original stock
                                new_quantity = existing_product_without_cost["quantity"] + quantity
                                new_original_stock = existing_product_without_cost["original_stock"] + quantity

                                # Use the new selling price from the input (form or file)
                                new_selling_price = selling_price  # Overwrite with the new selling price

                                # Update quantity, cost price, and selling price
                                c.execute("""
                                    UPDATE inventory 
                                    SET quantity = ?, original_stock = ?, cost_price = ?, selling_price = ?, adding_to_inventory_date = ?
                                    WHERE id = ?
                                """, (new_quantity, new_original_stock, new_cost_price, new_selling_price, adding_to_inventory_date, existing_product_without_cost["id"]))
                            else:
                                # Insert new product
                                c.execute("""
                                    INSERT INTO inventory (
                                        product_name, product_type, gender, size, quantity, cost_price, selling_price, adding_to_inventory_date, original_stock
                                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                """, (product_name, product_type, gender, size, quantity, cost_price, selling_price, adding_to_inventory_date, quantity))
                        conn.commit()
                        flash("Bulk inventory upload successful!", "success")
                    except Exception as e:
                        flash(f"Error processing file: {str(e)}", "error")
                else:
                    flash("No file selected for upload.", "error")
            else:
                # Handle individual product addition/update
                product_name = request.form["product_name"]
                product_type = request.form["product_type"]
                gender = request.form["gender"]
                size = request.form["size"]
                quantity = int(request.form["quantity"])
                cost_price = float(request.form["cost_price"])
                selling_price = float(request.form["selling_price"])

                if not (product_name and product_type and gender and size and quantity and cost_price and selling_price):
                    flash("Please fill all fields.", "error")
                    return redirect(url_for("inventory"))

                c = conn.cursor()

                # Check if the product exists with all fields except cost_price matching
                existing_product_without_cost = c.execute("""
                    SELECT * FROM inventory 
                    WHERE product_name = ? AND product_type = ? AND gender = ? AND size = ?
                """, (product_name, product_type, gender, size)).fetchone()

                if existing_product_without_cost:
                    # Calculate average cost price
                    old_cost_price = existing_product_without_cost["cost_price"]
                    new_cost_price = (old_cost_price + cost_price) / 2  # Average cost

                    # Update quantity and original stock
                    new_quantity = existing_product_without_cost["quantity"] + quantity
                    new_original_stock = existing_product_without_cost["original_stock"] + quantity

                    # Use the new selling price from the input (form or file)
                    new_selling_price = selling_price  # Overwrite with the new selling price

                    # Update quantity, cost price, and selling price
                    c.execute("""
                        UPDATE inventory 
                        SET quantity = ?, original_stock = ?, cost_price = ?, selling_price = ?, adding_to_inventory_date = ?
                        WHERE id = ?
                    """, (new_quantity, new_original_stock, new_cost_price, new_selling_price, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), existing_product_without_cost["id"]))
                else:
                    # Insert new product
                    adding_to_inventory_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    c.execute("""
                        INSERT INTO inventory (
                            product_name, product_type, gender, size, quantity, cost_price, selling_price, adding_to_inventory_date, original_stock
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (product_name, product_type, gender, size, quantity, cost_price, selling_price, adding_to_inventory_date, quantity))

                conn.commit()
                flash("Product added/updated in inventory!", "success")
                return redirect(url_for("inventory"))

        return render_template("inventory.html", products=products)

    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
        return redirect(url_for("inventory"))
    finally:
        conn.close()


# Delete product route
@app.route("/delete_product/<int:id>", methods=["POST"])
@login_required
def delete_product(id):
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("DELETE FROM inventory WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        flash("Product deleted successfully!", "success")
    except Exception as e:
        flash(f"An error occurred: {str(e)}", "error")
    return redirect(url_for("inventory"))

# Modify product route
@app.route("/modify_product/<int:id>", methods=["POST"])
@login_required
def modify_product(id):
    conn = get_db_connection()
    product = conn.execute("SELECT * FROM inventory WHERE id = ?", (id,)).fetchone()

    if request.method == "POST":
        # Get form data
        quantity = request.form.get("quantity")
        cost_price = request.form.get("cost_price")
        selling_price = request.form.get("selling_price")

        # Validate form data
        if not (quantity and cost_price and selling_price):
            flash("Please fill all fields.", "error")
            return redirect(url_for("inventory"))

        # Update the product in the database
        conn.execute("""
            UPDATE inventory 
            SET quantity = ?, cost_price = ?, selling_price = ?
            WHERE id = ?
        """, (quantity, cost_price, selling_price, id))
        conn.commit()
        conn.close()

        flash("Product updated successfully!", "success")
        return redirect(url_for("inventory"))

    conn.close()
    return redirect(url_for("inventory"))

    # Render the modify product form with the current product data
    return render_template("modify_product.html", product=product)

# Refunds route
@app.route("/refunds", methods=["GET", "POST"])
@login_required
def refunds():
    conn = get_db_connection()
    try:
        # Fetch sales data with customer details
        sales = conn.execute("""
            SELECT sales.*, crm.customer_name, crm.contact_info 
            FROM sales 
            JOIN crm ON sales.customer_id = crm.id
        """).fetchall()

        # Fetch all customers from CRM for the dropdown
        customers = conn.execute("SELECT * FROM crm").fetchall()

        # Convert Row objects to dictionaries
        sales = [dict(sale) for sale in sales]
        customers = [dict(customer) for customer in customers]
    except Exception as e:
        flash(f"An error occurred while fetching data: {str(e)}", "error")
        sales = []
        customers = []
    finally:
        conn.close()

    return render_template("refunds.html", sales=sales, customers=customers)

# Refund route
@app.route("/refund/<int:sale_id>", methods=["POST"])
@login_required
def refund(sale_id):
    conn = get_db_connection()
    c = conn.cursor()

    try:
        # Fetch the sale record
        sale = c.execute("SELECT * FROM sales WHERE id = ?", (sale_id,)).fetchone()
        if not sale:
            flash("Sale not found.", "error")
            return redirect(url_for("refunds"))

        # Get the refund quantity from the form
        refund_quantity = int(request.form.get("refund_quantity"))
        if refund_quantity > sale["quantity"]:
            flash("Refund quantity cannot exceed the original sale quantity.", "error")
            return redirect(url_for("refunds"))

        # Calculate the refund amount
        refund_amount = (sale["total_amount"] / sale["quantity"]) * refund_quantity

        # Update inventory (restore partial quantity)
        c.execute("UPDATE inventory SET quantity = quantity + ? WHERE id = ?", (refund_quantity, sale["product_id"]))

        # Record the refund in the finance table with sale_id
        refund_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("""
            INSERT INTO finance (transaction_type, amount, transaction_datetime, action_date, sale_id)
            VALUES (?, ?, ?, ?, ?)
        """, ("refund", -refund_amount, refund_datetime, refund_datetime, sale_id))

        # Update the sale record (reduce quantity and total amount)
        new_quantity = sale["quantity"] - refund_quantity
        new_total_amount = sale["total_amount"] - refund_amount

        if new_quantity > 0:
            c.execute("UPDATE sales SET quantity = ?, total_amount = ? WHERE id = ?",
                      (new_quantity, new_total_amount, sale_id))
        else:
            # If the entire sale is refunded, delete the sale record
            c.execute("DELETE FROM sales WHERE id = ?", (sale_id,))

        # Add a new row in customer_purchases for the refund
        c.execute("""
            INSERT INTO customer_purchases (customer_id, product_name, quantity, total_amount, purchase_date)
            VALUES (?, ?, ?, ?, ?)
        """, (
            sale["customer_id"],
            sale["product_name"],
            -refund_quantity,  # Negative quantity for refund
            -refund_amount,    # Negative amount for refund
            refund_datetime    # Use the refund datetime
        ))

        conn.commit()
        flash("Refund processed successfully!", "success")
    except Exception as e:
        conn.rollback()  # Rollback in case of error
        flash(f"An error occurred: {str(e)}", "error")
    finally:
        conn.close()

    return redirect(url_for("refunds"))

# Finance Route
@app.route("/finance", methods=["GET", "POST"])
@login_required
def finance():
    if request.method == "POST":
        transaction_type = request.form["transaction_type"]
        amount = float(request.form["amount"])
        transaction_date = request.form.get("transaction_date", datetime.now().strftime("%Y-%m-%d"))
        description = request.form.get("description", "")

        if transaction_type and amount:
            try:
                conn = get_db_connection()
                c = conn.cursor()
                transaction_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                c.execute("""
                    INSERT INTO finance (transaction_type, amount, transaction_datetime, action_date, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (transaction_type, amount, transaction_datetime, transaction_date, description))
                conn.commit()
                flash("Transaction recorded successfully!", "success")
            except Exception as e:
                flash(f"An error occurred: {str(e)}", "error")
            finally:
                conn.close()
        else:
            flash("Please fill all fields.", "error")

    # Fetch recent transactions
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM finance ORDER BY transaction_datetime DESC LIMIT 10")
    transactions = c.fetchall()

    # Calculate totals
    c.execute("SELECT transaction_type, SUM(amount) as total FROM finance GROUP BY transaction_type")
    totals = c.fetchall()
    total_income = sum(t["total"] for t in totals if t["transaction_type"] == "income")
    total_expenses = sum(t["total"] for t in totals if t["transaction_type"] != "income")
    net_balance = total_income - total_expenses

    conn.close()

    return render_template(
        "finance.html",
        transactions=transactions,
        total_income=total_income,
        total_expenses=total_expenses,
        net_balance=net_balance
    )


# CRM Route
@app.route("/crm", methods=["GET", "POST"])
@login_required
def crm():
    if request.method == "GET":
        conn = get_db_connection()
        customers = conn.execute("SELECT * FROM crm").fetchall()

        # Fetch purchase history for each customer
        customers_with_purchases = []
        for customer in customers:
            purchases = conn.execute("""
                SELECT * FROM customer_purchases 
                WHERE customer_id = ?
                ORDER BY purchase_date DESC
            """, (customer["id"],)).fetchall()
            customer_dict = dict(customer)
            customer_dict["purchases"] = [dict(purchase) for purchase in purchases]
            customers_with_purchases.append(customer_dict)

        conn.close()
        return render_template("crm.html", customers=customers_with_purchases)

    elif request.method == "POST":
        if 'bulk_customer_upload' in request.files:
            file = request.files['bulk_customer_upload']
            if file.filename != '':
                try:
                    df = pd.read_excel(file)
                    conn = get_db_connection()
                    c = conn.cursor()
                    errors = []
                    success_count = 0

                    for index, row in df.iterrows():
                        customer_name = row['Customer Name']
                        contact_info = row['Customer Mobile']
                        how_know_us = row['How did the customer know us?']
                        birthday_date = row['Birthday Date']
                        creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        current_tier = row.get('Current Tier', 'Bronze')
                        total_points = row.get('Total Points', 0)

                        # Check if the mobile number already exists
                        existing_customer = c.execute("SELECT * FROM crm WHERE contact_info = ?", (contact_info,)).fetchone()
                        if existing_customer:
                            errors.append(f"Mobile number {contact_info} already exists.")
                            continue

                        # Insert new customer
                        c.execute("""
                            INSERT INTO crm (
                                customer_name, contact_info, how_know_us, last_purchase_date, birthday_date, creation_date, current_tier, total_points
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (customer_name, contact_info, how_know_us, None, birthday_date, creation_date, current_tier, total_points))
                        success_count += 1

                    conn.commit()
                    conn.close()

                    if errors:
                        return jsonify({
                            "success": False,
                            "message": f"Bulk upload completed with {success_count} successes and {len(errors)} errors.",
                            "errors": errors
                        })
                    else:
                        return jsonify({
                            "success": True,
                            "message": f"Bulk upload successful! {success_count} customers added."
                        })

                except Exception as e:
                    return jsonify({
                        "success": False,
                        "message": f"Error processing file: {str(e)}"
                    })
            else:
                return jsonify({
                    "success": False,
                    "message": "No file selected for upload."
                })

        else:
            customer_name = request.form.get("customer_name")
            contact_info = request.form.get("contact_info")
            how_know_us = request.form.get("how_know_us")
            birthday_date = request.form.get("birthday_date")
            current_tier = request.form.get("current_tier", "Bronze")
            total_points = request.form.get("total_points", 0)

            # Validate required fields
            if not customer_name or not contact_info or not how_know_us:
                return jsonify({
                    "success": False,
                    "message": "Please fill all required fields: Customer Name, Mobile, and How They Know Us."
                })

            conn = get_db_connection()
            c = conn.cursor()

            # Check if the mobile number already exists
            existing_customer = c.execute("SELECT * FROM crm WHERE contact_info = ?", (contact_info,)).fetchone()
            if existing_customer:
                return jsonify({
                    "success": False,
                    "message": "Mobile number already exists."
                })

            # Set creation_date to the current datetime
            creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Insert new customer
            c.execute("""
                INSERT INTO crm (
                    customer_name, contact_info, how_know_us, last_purchase_date, birthday_date, creation_date, current_tier, total_points
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (customer_name, contact_info, how_know_us, None, birthday_date, creation_date, current_tier, total_points))

            # Get the ID of the newly inserted customer
            new_customer_id = c.lastrowid

            conn.commit()
            conn.close()

            # Return JSON response for AJAX
            return jsonify({
                "success": True,
                "message": "Customer added successfully!",
                "customer": {
                    "id": new_customer_id,
                    "customer_name": customer_name,
                    "contact_info": contact_info,
                    "how_know_us": how_know_us,
                    "birthday_date": birthday_date,
                    "current_tier": current_tier,
                    "total_points": total_points,
                }
            })
            
# Route to update mobile number
@app.route("/update_mobile/<int:customer_id>", methods=["POST"])
@login_required
def update_mobile(customer_id):
    data = request.get_json()
    new_mobile = data.get("mobile")

    conn = get_db_connection()
    c = conn.cursor()

    # Check if the mobile number already exists
    existing_customer = c.execute("SELECT * FROM crm WHERE contact_info = ? AND id != ?", (new_mobile, customer_id)).fetchone()
    if existing_customer:
        conn.close()
        return jsonify({"success": False, "message": "Mobile number already exists."})

    # Update the mobile number
    c.execute("UPDATE crm SET contact_info = ? WHERE id = ?", (new_mobile, customer_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True})

# Route to view a customer's profile
@app.route("/customer_profile/<int:customer_id>")
@login_required
def customer_profile(customer_id):
    conn = None
    try:
        conn = get_db_connection()
        
        # Fetch customer details
        customer = conn.execute("SELECT * FROM crm WHERE id = ?", (customer_id,)).fetchone()
        if not customer:
            return "Customer not found.", 404

        # Fetch purchase history for the customer
        purchases = conn.execute("""
            SELECT * FROM customer_purchases 
            WHERE customer_id = ?
            ORDER BY purchase_date DESC
        """, (customer_id,)).fetchall()

        # Fetch loyalty rewards
        rewards = conn.execute("""
            SELECT * FROM loyalty_rewards 
            WHERE customer_id = ?
            ORDER BY reward_date DESC
        """, (customer_id,)).fetchall()

        # Convert Row objects to dictionaries for easier use in the template
        customer_dict = dict(customer)
        customer_dict["purchases"] = [dict(purchase) for purchase in purchases]
        customer_dict["rewards"] = [dict(reward) for reward in rewards]

        return render_template("customer_profile.html", customer=customer_dict)

    except Exception as e:
        # Log the error for debugging
        print(f"Error fetching customer profile: {str(e)}")
        return "An error occurred while fetching the customer profile.", 500

    finally:
        # Ensure the database connection is always closed
        if conn:
            conn.close()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redeem Points Route
from datetime import datetime
from flask import Flask, request, jsonify
import logging

# Configure logging
logger = logging.getLogger(__name__)


# Redeem Points Route
@app.route("/redeem_points/<int:customer_id>", methods=["POST"])
@login_required
def redeem_points(customer_id):
    # Validate JSON input
    data = request.get_json()
    if not data:
        logger.warning("No data provided in the request.")
        return jsonify({"success": False, "message": "No data provided in the request."}), 400

    # Extract and validate required fields
    points_redeemed = data.get("points_redeemed")
    reward_type = data.get("reward_type")

    if not isinstance(points_redeemed, int) or points_redeemed <= 0:
        logger.warning(f"Invalid or missing 'points_redeemed' for customer {customer_id}.")
        return jsonify({"success": False, "message": "Invalid or missing 'points_redeemed'. Must be a positive integer."}), 400

    if not reward_type or not isinstance(reward_type, str) or reward_type.strip() == "":
        logger.warning(f"Invalid or missing 'reward_type' for customer {customer_id}.")
        return jsonify({"success": False, "message": "Invalid or missing 'reward_type'. Must be a non-empty string."}), 400

    conn = get_db_connection()
    try:
        c = conn.cursor()

        # Fetch customer's current points
        customer = c.execute("SELECT total_points FROM crm WHERE id = ?", (customer_id,)).fetchone()
        if not customer:
            logger.warning(f"Customer {customer_id} not found.")
            return jsonify({"success": False, "message": "Customer not found."}), 404

        current_points = customer["total_points"]

        # Check if the customer has enough points
        if current_points < points_redeemed:
            logger.warning(f"Not enough points to redeem for customer {customer_id}.")
            return jsonify({"success": False, "message": "Not enough points to redeem."}), 400

        # Deduct points and record the reward
        new_points = current_points - points_redeemed
        reward_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Update customer's points
        c.execute("UPDATE crm SET total_points = ? WHERE id = ?", (new_points, customer_id))

        # Record the reward in loyalty_rewards table
        c.execute("""
            INSERT INTO loyalty_rewards (customer_id, points_redeemed, reward_type, reward_date)
            VALUES (?, ?, ?, ?)
        """, (customer_id, points_redeemed, reward_type, reward_date))

        # Commit the transaction
        conn.commit()
        logger.info(f"Points redeemed successfully for customer {customer_id}: {points_redeemed} points for {reward_type}.")
        return jsonify({
            "success": True,
            "message": "Points redeemed successfully.",
            "new_points": new_points,
            "reward_type": reward_type,
            "reward_date": reward_date
        })

    except Exception as e:
        # Rollback in case of error
        conn.rollback()
        logger.error(f"Error redeeming points for customer {customer_id}: {str(e)}")
        return jsonify({"success": False, "message": f"An error occurred: {str(e)}"}), 500

    finally:
        # Ensure the connection is always closed
        if conn:
            conn.close()

# Save notes Route
@app.route("/save_notes/<int:customer_id>", methods=["POST"])
@login_required
def save_notes(customer_id):
    data = request.get_json()
    notes = data.get("notes")

    # Validate input
    if not notes or not isinstance(notes, str):
        return jsonify({"success": False, "message": "Invalid or missing 'notes' field. Must be a non-empty string."}), 400

    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Check if the customer exists
        customer = c.execute("SELECT id FROM crm WHERE id = ?", (customer_id,)).fetchone()
        if not customer:
            return jsonify({"success": False, "message": "Customer not found."}), 404

        # Update the notes
        c.execute("UPDATE crm SET notes = ? WHERE id = ?", (notes, customer_id))
        conn.commit()
        return jsonify({"success": True, "message": "Notes saved successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

# Get Customer Route
@app.route("/get_customer/<int:customer_id>", methods=["GET"])
@login_required
def get_customer(customer_id):
    conn = get_db_connection()
    try:
        # Fetch customer details
        customer = conn.execute("SELECT * FROM crm WHERE id = ?", (customer_id,)).fetchone()
        if not customer:
            return jsonify({"success": False, "message": "Customer not found."}), 404

        # Fetch purchase history
        purchases = conn.execute("""
            SELECT * FROM customer_purchases 
            WHERE customer_id = ?
            ORDER BY purchase_date DESC
        """, (customer_id,)).fetchall()

        # Fetch redeemed points history
        rewards = conn.execute("""
            SELECT * FROM loyalty_rewards 
            WHERE customer_id = ?
            ORDER BY reward_date DESC
        """, (customer_id,)).fetchall()

        # Convert Row objects to dictionaries
        customer_dict = dict(customer)
        customer_dict["purchases"] = [dict(purchase) for purchase in purchases]
        customer_dict["rewards"] = [dict(reward) for reward in rewards]

        # Include success flag in the response
        response = {
            "success": True,
            "customer": customer_dict
        }

        return jsonify(response)

    except Exception as e:
        # Log the error for debugging
        print(f"Error fetching customer data: {str(e)}")
        return jsonify({"success": False, "message": "An error occurred while fetching customer data."}), 500

    finally:
        conn.close()

# save_communication_preferences
@app.route("/save_communication_preferences/<int:customer_id>", methods=["POST"])
@login_required
def save_communication_preferences(customer_id):
    data = request.get_json()
    email_notifications = data.get("email_notifications", False)
    sms_notifications = data.get("sms_notifications", False)
    whatsapp_notifications = data.get("whatsapp_notifications", False)

    # Validate input
    if not isinstance(email_notifications, bool) or not isinstance(sms_notifications, bool) or not isinstance(whatsapp_notifications, bool):
        return jsonify({"success": False, "message": "Invalid input. All preferences must be boolean values."}), 400

    conn = get_db_connection()
    c = conn.cursor()
    try:
        # Check if the customer exists
        customer = c.execute("SELECT id FROM crm WHERE id = ?", (customer_id,)).fetchone()
        if not customer:
            return jsonify({"success": False, "message": "Customer not found."}), 404

        # Update communication preferences
        c.execute("""
            UPDATE crm 
            SET email_notifications = ?, sms_notifications = ?, whatsapp_notifications = ? 
            WHERE id = ?
        """, (email_notifications, sms_notifications, whatsapp_notifications, customer_id))
        conn.commit()
        return jsonify({"success": True, "message": "Preferences saved successfully."})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

# Reports Route
@app.route("/reports", methods=["GET", "POST"])
@login_required
def reports():
    if current_user.role != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("home"))

    if request.method == "POST":
        report_type = request.form["report_type"]
        start_date = request.form.get("start_date")
        end_date = request.form.get("end_date")
        customer_name = request.form.get("customer_name")
        product_category = request.form.get("product_category")
        selected_month = request.form.get("selected_month")  # For customers_by_birth_month

        conn = get_db_connection()

        try:
            if report_type == "sales_by_date":
                query = """
                    SELECT 
                        s.sale_datetime AS sale_date,
                        c.customer_name,
                        c.contact_info AS customer_mobile,
                        s.product_name,
                        s.quantity,
                        s.total_amount
                    FROM sales s
                    JOIN crm c ON s.customer_id = c.id
                    WHERE s.sale_datetime BETWEEN ? AND ?
                """
                params = [start_date, end_date]
                if customer_name:
                    query += " AND c.customer_name = ?"
                    params.append(customer_name)
                df = pd.read_sql_query(query, conn, params=params)
                report_html = df.to_html(index=False)

            elif report_type == "customers_by_birth_month":
                query = """
                    SELECT 
                        c.customer_name,
                        c.contact_info AS customer_mobile,
                        strftime('%d', c.birthday_date) AS birth_day,
                        strftime('%m', c.birthday_date) AS birth_month
                    FROM crm c
                    WHERE ? = '' OR strftime('%m', c.birthday_date) = ?
                    ORDER BY birth_day
                """
                params = [selected_month, selected_month]
                df = pd.read_sql_query(query, conn, params=params)
                report_html = df.to_html(index=False)

            elif report_type == "churned_customers":
                query = """
                    SELECT 
                        c.customer_name,
                        c.contact_info AS customer_mobile,
                        MAX(s.sale_datetime) AS last_purchase_date
                    FROM sales s
                    JOIN crm c ON s.customer_id = c.id
                    GROUP BY c.customer_name
                    HAVING last_purchase_date < DATE('now', '-1 months')
                """
                df = pd.read_sql_query(query, conn)
                report_html = df.to_html(index=False)

            elif report_type == "top_customers":
                query = """
                    SELECT 
                        c.customer_name,
                        c.contact_info AS customer_mobile,
                        SUM(s.total_amount) AS total_sales
                    FROM sales s
                    JOIN crm c ON s.customer_id = c.id
                    GROUP BY c.customer_name
                    ORDER BY total_sales DESC
                    LIMIT 10
                """
                df = pd.read_sql_query(query, conn)
                report_html = df.to_html(index=False)

            elif report_type == "product_performance":
                query = """
                    SELECT 
                        s.product_name,
                        c.customer_name,
                        c.contact_info AS customer_mobile,
                        SUM(s.quantity) AS total_quantity,
                        SUM(s.total_amount) AS total_sales
                    FROM sales s
                    JOIN crm c ON s.customer_id = c.id
                    WHERE s.sale_datetime BETWEEN ? AND ?
                    GROUP BY s.product_name, c.customer_name
                    ORDER BY total_sales DESC
                """
                params = [start_date, end_date]
                if product_category:
                    query += " AND s.product_type = ?"
                    params.append(product_category)
                df = pd.read_sql_query(query, conn, params=params)
                report_html = df.to_html(index=False)

            elif report_type == "refund_analysis":
                query = """
                    SELECT 
                        s.product_name,
                        c.customer_name,
                        c.contact_info AS customer_mobile,
                        s.quantity,
                        s.total_amount,
                        f.transaction_datetime
                    FROM sales s
                    JOIN crm c ON s.customer_id = c.id
                    JOIN finance f ON s.id = f.sale_id
                    WHERE f.transaction_type = 'refund'
                """
                df = pd.read_sql_query(query, conn)
                report_html = df.to_html(index=False)

            elif report_type == "inventory_aging":
                query = """
                    SELECT 
                        i.product_name,
                        c.customer_name,
                        c.contact_info AS customer_mobile,
                        i.adding_to_inventory_date
                    FROM inventory i
                    LEFT JOIN sales s ON i.id = s.product_id
                    LEFT JOIN crm c ON s.customer_id = c.id
                    WHERE i.adding_to_inventory_date < DATE('now', '-6 months')
                """
                df = pd.read_sql_query(query, conn)
                report_html = df.to_html(index=False)

            # New Reports
            elif report_type == "sales_by_payment_type":
                query = """
                    SELECT 
                        s.payment_type,
                        SUM(s.total_amount) AS total_sales
                    FROM sales s
                    WHERE s.sale_datetime BETWEEN ? AND ?
                    GROUP BY s.payment_type
                """
                params = [start_date, end_date]
                df = pd.read_sql_query(query, conn, params=params)
                report_html = df.to_html(index=False)

            elif report_type == "customer_lifetime_value":
                query = """
                    SELECT 
                        c.customer_name,
                        c.contact_info AS customer_mobile,
                        SUM(s.total_amount) AS total_spent
                    FROM sales s
                    JOIN crm c ON s.customer_id = c.id
                    GROUP BY c.customer_name
                    ORDER BY total_spent DESC
                """
                df = pd.read_sql_query(query, conn)
                report_html = df.to_html(index=False)

            elif report_type == "inventory_turnover":
                query = """
                    SELECT 
                        i.product_name,
                        SUM(s.quantity) AS total_sold,
                        i.quantity AS current_stock,
                        (SUM(s.quantity) / i.original_stock) * 100 AS turnover_rate
                    FROM inventory i
                    LEFT JOIN sales s ON i.id = s.product_id
                    GROUP BY i.product_name
                """
                df = pd.read_sql_query(query, conn)
                report_html = df.to_html(index=False)

            elif report_type == "customer_acquisition_channels":
                query = """
                    SELECT 
                        c.how_know_us AS acquisition_channel,
                        COUNT(c.id) AS total_customers,
                        SUM(s.total_amount) AS total_sales
                    FROM crm c
                    LEFT JOIN sales s ON c.id = s.customer_id
                    GROUP BY c.how_know_us
                """
                df = pd.read_sql_query(query, conn)
                report_html = df.to_html(index=False)

            else:
                flash("Invalid report type.", "error")
                return redirect(url_for("reports"))

            return render_template("reports.html", report_html=report_html, report_type=report_type)

        except Exception as e:
            flash(f"An error occurred: {str(e)}", "error")
        finally:
            conn.close()

    return render_template("reports.html")

# Export to excel route
@app.route("/export_to_excel", methods=["POST"])
@login_required
def export_to_excel():
    if current_user.role != "admin":
        flash("You do not have permission to access this page.", "error")
        return redirect(url_for("home"))

    # Get form data
    report_type = request.form["report_type"]
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    customer_name = request.form.get("customer_name")
    product_category = request.form.get("product_category")
    selected_month = request.form.get("selected_month")  # For customers_by_birth_month

    conn = get_db_connection()

    try:
        # Define the query and sheet name based on the report type
        if report_type == "sales_by_date":
            query = """
                SELECT 
                    s.sale_datetime AS sale_date,
                    c.customer_name,
                    c.contact_info AS customer_mobile,
                    s.product_name,
                    s.quantity,
                    s.total_amount
                FROM sales s
                JOIN crm c ON s.customer_id = c.id
                WHERE s.sale_datetime BETWEEN ? AND ?
            """
            params = [start_date, end_date]
            if customer_name:
                query += " AND c.customer_name = ?"
                params.append(customer_name)
            sheet_name = "Sales by Date"

        elif report_type == "customers_by_birth_month":
            query = """
                SELECT 
                    c.customer_name,
                    c.contact_info AS customer_mobile,
                    strftime('%d', c.birthday_date) AS birth_day,
                    strftime('%m', c.birthday_date) AS birth_month
                FROM crm c
                WHERE ? = '' OR strftime('%m', c.birthday_date) = ?
                ORDER BY birth_day
            """
            params = [selected_month, selected_month]
            sheet_name = "Customers by Birth Month"

        elif report_type == "churned_customers":
            query = """
                SELECT 
                    c.customer_name,
                    c.contact_info AS customer_mobile,
                    MAX(s.sale_datetime) AS last_purchase_date
                FROM sales s
                JOIN crm c ON s.customer_id = c.id
                GROUP BY c.customer_name
                HAVING last_purchase_date < DATE('now', '-1 months')
            """
            params = []
            sheet_name = "Churned Customers"

        elif report_type == "top_customers":
            query = """
                SELECT 
                    c.customer_name,
                    c.contact_info AS customer_mobile,
                    SUM(s.total_amount) AS total_sales
                FROM sales s
                JOIN crm c ON s.customer_id = c.id
                GROUP BY c.customer_name
                ORDER BY total_sales DESC
                LIMIT 10
            """
            params = []
            sheet_name = "Top Customers by Sales"

        elif report_type == "product_performance":
            query = """
                SELECT 
                    s.product_name,
                    c.customer_name,
                    c.contact_info AS customer_mobile,
                    SUM(s.quantity) AS total_quantity,
                    SUM(s.total_amount) AS total_sales
                FROM sales s
                JOIN crm c ON s.customer_id = c.id
                WHERE s.sale_datetime BETWEEN ? AND ?
                GROUP BY s.product_name, c.customer_name
                ORDER BY total_sales DESC
            """
            params = [start_date, end_date]
            if product_category:
                query += " AND s.product_type = ?"
                params.append(product_category)
            sheet_name = "Product Performance"

        elif report_type == "refund_analysis":
            query = """
                SELECT 
                    s.product_name,
                    c.customer_name,
                    c.contact_info AS customer_mobile,
                    s.quantity,
                    s.total_amount,
                    f.transaction_datetime
                FROM sales s
                JOIN crm c ON s.customer_id = c.id
                JOIN finance f ON s.id = f.sale_id
                WHERE f.transaction_type = 'refund'
            """
            params = []
            if start_date and end_date:
                query += " AND f.transaction_datetime BETWEEN ? AND ?"
                params.extend([start_date, end_date])
            if customer_name:
                query += " AND c.customer_name = ?"
                params.append(customer_name)
            if product_category:
                query += " AND s.product_type = ?"
                params.append(product_category)
            sheet_name = "Refund Analysis"

        elif report_type == "inventory_aging":
            query = """
                SELECT 
                    i.product_name,
                    c.customer_name,
                    c.contact_info AS customer_mobile,
                    i.adding_to_inventory_date
                FROM inventory i
                LEFT JOIN sales s ON i.id = s.product_id
                LEFT JOIN crm c ON s.customer_id = c.id
                WHERE i.adding_to_inventory_date < DATE('now', '-6 months')
            """
            params = []
            sheet_name = "Inventory Aging Report"

        # New Reports
        elif report_type == "sales_by_payment_type":
            query = """
                SELECT 
                    s.payment_type,
                    SUM(s.total_amount) AS total_sales
                FROM sales s
                WHERE s.sale_datetime BETWEEN ? AND ?
                GROUP BY s.payment_type
            """
            params = [start_date, end_date]
            sheet_name = "Sales by Payment Type"

        elif report_type == "customer_lifetime_value":
            query = """
                SELECT 
                    c.customer_name,
                    c.contact_info AS customer_mobile,
                    SUM(s.total_amount) AS total_spent
                FROM sales s
                JOIN crm c ON s.customer_id = c.id
                GROUP BY c.customer_name
                ORDER BY total_spent DESC
            """
            params = []
            sheet_name = "Customer Lifetime Value"

        elif report_type == "inventory_turnover":
            query = """
                SELECT 
                    i.product_name,
                    SUM(s.quantity) AS total_sold,
                    i.quantity AS current_stock,
                    (SUM(s.quantity) / i.original_stock) * 100 AS turnover_rate
                FROM inventory i
                LEFT JOIN sales s ON i.id = s.product_id
                GROUP BY i.product_name
            """
            params = []
            sheet_name = "Inventory Turnover"

        elif report_type == "customer_acquisition_channels":
            query = """
                SELECT 
                    c.how_know_us AS acquisition_channel,
                    COUNT(c.id) AS total_customers,
                    SUM(s.total_amount) AS total_sales
                FROM crm c
                LEFT JOIN sales s ON c.id = s.customer_id
                GROUP BY c.how_know_us
            """
            params = []
            sheet_name = "Customer Acquisition Channels"

        else:
            flash("Invalid report type.", "error")
            return redirect(url_for("reports"))

        # Execute the query and create the Excel file
        df = pd.read_sql_query(query, conn, params=params)
        if df.empty:
            flash("No data to export.", "error")
            return redirect(url_for("reports"))

        # Create an in-memory Excel file
        excel_file = io.BytesIO()
        with pd.ExcelWriter(excel_file, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        excel_file.seek(0)

        # Send the file to the user
        return send_file(
            excel_file,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"{report_type}_report.xlsx"
        )

    except Exception as e:
        flash(f"An error occurred while exporting the report: {str(e)}", "error")
        return redirect(url_for("reports"))

    finally:
        conn.close()

# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form['username']
        password = request.form['password']
        if username in users and check_password_hash(users[username]["password"], password):
            user = User(username, username, users[username]["role"])
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid username or password', 'error')
    return render_template("login.html")

# Logout route
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == "__main__":
    create_tables()  # Create tables if they don't exist
    update_schema()  # Update schema if needed
    app.run(debug=True)  # Run the Flask application