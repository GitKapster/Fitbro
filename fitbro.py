from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import date

app = Flask(__name__)

# Connect to database
def get_db():
    conn = sqlite3.connect('fitness.db')
    conn.row_factory = sqlite3.Row
    return conn

# Home page - dashboard
@app.route('/')
def home():
    return render_template('dashboard.html')

# Add food page
@app.route('/add-food')
def add_food_page():
    return render_template('add_food.html')

# Meal detail page - shows foods for specific meal
@app.route('/meal/<meal_type>')
def meal_detail(meal_type):
    return render_template('meal_detail.html', meal_type=meal_type)

# Stats page
@app.route('/stats')
def stats():
    return render_template('stats.html')

# Community page
@app.route('/community')
def community():
    return render_template('community.html')

# Profile page
@app.route('/profile')
def profile():
    return render_template('profile.html')

# Get today's food log
@app.route('/api/food-log')
def get_food_log():
    conn = get_db()
    cursor = conn.cursor()
    
    today = str(date.today())
    
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

# Get foods for specific meal type
@app.route('/api/meal/<meal_type>')
def get_meal_foods(meal_type):
    conn = get_db()
    cursor = conn.cursor()
    
    today = str(date.today())
    
    cursor.execute('''
        SELECT f.name, f.calories, f.protein, f.carbs, f.fat, 
               fl.servings, fl.id as log_id
        FROM food_log fl
        JOIN foods f ON fl.food_id = f.id
        WHERE fl.date = ? AND fl.user_id = 1 AND fl.meal_type = ?
    ''', (today, meal_type))
    
    foods = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(food) for food in foods])

# Add food to log
@app.route('/api/add-food', methods=['POST'])
def add_food_api():
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

# Delete food from log
@app.route('/api/delete-food/<int:log_id>', methods=['DELETE'])
def delete_food(log_id):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM food_log WHERE id = ?', (log_id,))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(debug=True)