# app.py

from flask import Flask, render_template, request, redirect, url_for, send_file
from pymongo import MongoClient
from bson.objectid import ObjectId
from datetime import datetime, date
import pandas as pd
import io

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

# MongoDB connection
client = MongoClient('mongodb+srv://sangeeth:11062007@cluster0.bqizaeu.mongodb.net/')
db = client.restaurant_db

# Collections
menu_col = db.menu
orders_col = db.orders
tables_col = db.tables

# --- Sample data insertion for menu and tables (run once) ---
def insert_sample_data():
    if menu_col.count_documents({}) == 0:
        sample_menu = [
            {"name": "Margherita Pizza", "category": "Pizza", "price": 8.99},
            {"name": "Pepperoni Pizza", "category": "Pizza", "price": 9.99},
            {"name": "Caesar Salad", "category": "Salad", "price": 6.99},
            {"name": "Lemonade", "category": "Drink", "price": 2.99},
            {"name": "Spaghetti Bolognese", "category": "Pasta", "price": 10.99},
        ]
        menu_col.insert_many(sample_menu)
    if tables_col.count_documents({}) == 0:
        sample_tables = [{"table_number": i, "seats": 4, "available": True} for i in range(1, 11)]
        tables_col.insert_many(sample_tables)

insert_sample_data()


# Home redirects to menu page
@app.route('/')
def home():
    return redirect(url_for('menu'))

# Show Menu and place orders
@app.route('/menu', methods=['GET', 'POST'])
def menu():
    menu_items = list(menu_col.find())
    
    if request.method == 'POST':
        customer_name = request.form.get('customer_name')
        order_items = request.form.getlist('order_item')
        quantities = request.form.getlist('quantity')
        
        order_details = []
        total_price = 0
        
        for item_id, qty in zip(order_items, quantities):
            if int(qty) > 0:
                menu_item = menu_col.find_one({"_id": ObjectId(item_id)})
                subtotal = menu_item['price'] * int(qty)
                total_price += subtotal
                order_details.append({
                    "item_id": item_id,
                    "name": menu_item['name'],
                    "price": menu_item['price'],
                    "quantity": int(qty),
                    "subtotal": subtotal
                })
        
        if order_details:
            order = {
                "customer_name": customer_name,
                "order_details": order_details,
                "total_price": total_price,
                "status": "Pending",
                "order_time": datetime.now()
            }
            orders_col.insert_one(order)
            return redirect(url_for('menu', success='Order placed successfully!'))
    
    return render_template('menu.html', menu=menu_items)


# Table reservation
@app.route('/reserve', methods=['GET', 'POST'])
def reserve():
    tables = list(tables_col.find({"available": True}))
    
    if request.method == 'POST':
        customer_name = request.form.get('customer_name')
        table_number = int(request.form.get('table_number'))
        reservation_time = request.form.get('reservation_time')  # e.g. '2025-08-12T19:00'
        
        # Mark table as unavailable
        tables_col.update_one({"table_number": table_number}, {"$set": {"available": False}})
        
        # Save reservation
        db.reservations.insert_one({
            "customer_name": customer_name,
            "table_number": table_number,
            "reservation_time": datetime.strptime(reservation_time, '%Y-%m-%dT%H:%M'),
            "created_at": datetime.now()
        })
        return redirect(url_for('reserve', success='Table reserved successfully!'))
    
    return render_template('reservation.html', tables=tables)


# Staff dashboard to update orders and tables
@app.route('/staff', methods=['GET', 'POST'])
def staff():
    orders = list(orders_col.find().sort("order_time", -1))
    tables = list(tables_col.find())
    
    if request.method == 'POST':
        if 'update_order_status' in request.form:
            order_id = request.form.get('order_id')
            new_status = request.form.get('status')
            orders_col.update_one({"_id": ObjectId(order_id)}, {"$set": {"status": new_status}})
        
        if 'update_table_status' in request.form:
            table_number = int(request.form.get('table_number'))
            new_availability = True if request.form.get('availability') == 'Available' else False
            tables_col.update_one({"table_number": table_number}, {"$set": {"available": new_availability}})
        
        return redirect(url_for('staff'))
    
    return render_template('staff.html', orders=orders, tables=tables)


# Daily Sales Report download
@app.route('/sales_report')
def sales_report():
    today = date.today()
    start = datetime.combine(today, datetime.min.time())
    end = datetime.combine(today, datetime.max.time())
    
    orders = list(orders_col.find({"order_time": {"$gte": start, "$lte": end}, "status": {"$in": ["Completed", "Served"]}}))
    
    rows = []
    for order in orders:
        for item in order['order_details']:
            rows.append({
                "Customer Name": order['customer_name'],
                "Item": item['name'],
                "Quantity": item['quantity'],
                "Price": item['price'],
                "Subtotal": item['subtotal'],
                "Order Time": order['order_time'].strftime('%Y-%m-%d %H:%M:%S')
            })
    
    df = pd.DataFrame(rows)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    
    return send_file(io.BytesIO(buffer.getvalue().encode()), mimetype='text/csv', download_name='daily_sales_report.csv', as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)
