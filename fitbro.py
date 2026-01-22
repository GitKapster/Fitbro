from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import date

app = Flask(__name__)

# Helper function to connect to database
def get_db():
    conn = sqlite3.connect('fitness.db')
    conn.row_factory = sqlite3.Row  # Returns rows as dictionaries
    return conn

# Home page - dashboard
@app.route('/')
def home():
    return render_template('dashboard.html')

# Adding Food Page - add_food
@app.route('/add-food')
def add_food_page():  # Changed name here
    return render_template('add_food.html')

# Get today's food log
@app.route('/api/food-log')
def get_food_log():
    conn = get_db()
    cursor = conn.cursor()
    
    today = str(date.today())
    
    # Get all foods logged today
    cursor.execute('''
        SELECT f.name, f.calories, f.protein, f.carbs, f.fat, 
               fl.meal_type, fl.servings
        FROM food_log fl
        JOIN foods f ON fl.food_id = f.id
        WHERE fl.date = ? AND fl.user_id = 1
    ''', (today,))
    
    foods = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(food) for food in foods])

# Add food to log
@app.route('/api/add-food', methods=['POST'])
def add_food_api():  # Changed name here
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO food_log (user_id, food_id, meal_type, servings, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (1, data['food_id'], data['meal_type'], data['servings'], str(date.today())))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)