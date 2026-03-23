# Updated fitbro.py with authentication

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
import secrets

app = Flask(__name__)
# Secret key for session management - change this to something random
app.secret_key = secrets.token_hex(16)

# Connect to database
def get_db():
    conn = sqlite3.connect('fitness.db')
    conn.row_factory = sqlite3.Row
    return conn

# Check if user is logged in
def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# Login page
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Find user by email
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()
        
        # Check if user exists and password is correct
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Invalid email or password'})
    
    return render_template('login.html')

# Register page
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        is_student = data.get('is_student', False)
        
        # Basic validation
        if not username or not email or not password:
            return jsonify({'success': False, 'error': 'All fields required'})
        
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if email already exists
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Email already registered'})
        
        # Hash the password
        hashed_password = generate_password_hash(password)
        
        # Insert new user
        cursor.execute('''
            INSERT INTO users (username, email, password, is_student, age, height,
                             daily_calorie_goal, daily_protein_goal, daily_carbs_goal, daily_fat_goal)
            VALUES (?, ?, ?, ?, 25, 75.0, 175.0, 2000, 150, 200, 65)
        ''', (username, email, hashed_password, is_student))
        
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        
        # Log them in automatically
        session['user_id'] = user_id
        session['username'] = username
        
        return jsonify({'success': True})
    
    return render_template('register.html')

# Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Home page - dashboard (protected)
@app.route('/')
@login_required
def home():
    return render_template('dashboard.html')

# Add food page (protected)
@app.route('/add-food')
@login_required
def add_food_page():
    return render_template('add_food.html')

# Meal detail page (protected)
@app.route('/meal/<meal_type>')
@login_required
def meal_detail(meal_type):
    return render_template('meal_detail.html', meal_type=meal_type)

# Stats page (protected)
@app.route('/stats')
@login_required
def stats():
    return render_template('stats.html')

# Community page (protected)
@app.route('/community')
@login_required
def community():
    return render_template('community.html')

# Profile page (protected)
@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

# Get today's food log (uses logged-in user)
@app.route('/api/food-log')
@login_required
def get_food_log():
    conn = get_db()
    cursor = conn.cursor()
    
    today = str(date.today())
    user_id = session['user_id']
    
    cursor.execute('''
        SELECT f.name, f.calories, f.protein, f.carbs, f.fat, 
               fl.meal_type, fl.servings
        FROM food_log fl
        JOIN foods f ON fl.food_id = f.id
        WHERE fl.date = ? AND fl.user_id = ?
    ''', (today, user_id))
    
    foods = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(food) for food in foods])

# Get foods for specific meal type (uses logged-in user)
@app.route('/api/meal/<meal_type>')
@login_required
def get_meal_foods(meal_type):
    conn = get_db()
    cursor = conn.cursor()
    
    today = str(date.today())
    user_id = session['user_id']
    
    cursor.execute('''
        SELECT f.name, f.calories, f.protein, f.carbs, f.fat, 
               fl.servings, fl.id as log_id
        FROM food_log fl
        JOIN foods f ON fl.food_id = f.id
        WHERE fl.date = ? AND fl.user_id = ? AND fl.meal_type = ?
    ''', (today, user_id, meal_type))
    
    foods = cursor.fetchall()
    conn.close()
    
    return jsonify([dict(food) for food in foods])

# Add food to log (uses logged-in user)
@app.route('/api/add-food', methods=['POST'])
@login_required
def add_food_api():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()

    user_id = session['user_id']
    log_date = data.get('date', str(date.today()))  # ← use provided date or today

    cursor.execute('''
        INSERT INTO food_log (user_id, food_id, meal_type, servings, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, data['food_id'], data['meal_type'], data['servings'], log_date))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

# Get all dates that have food log entries for the current user (for calendar dots)
@app.route('/api/logged-dates')
@login_required
def get_logged_dates():
    conn = get_db()
    cursor = conn.cursor()
    user_id = session['user_id']

    cursor.execute('''
        SELECT DISTINCT date, SUM(f.calories * fl.servings) as total_calories
        FROM food_log fl
        JOIN foods f ON fl.food_id = f.id
        WHERE fl.user_id = ?
        GROUP BY date
    ''', (user_id,))

    rows = cursor.fetchall()
    conn.close()

    return jsonify([{'date': r['date'], 'total_calories': round(r['total_calories'])} for r in rows])


# Get full food log for a specific date
@app.route('/api/food-log/<date_str>')
@login_required
def get_food_log_by_date(date_str):
    conn = get_db()
    cursor = conn.cursor()
    user_id = session['user_id']

    cursor.execute('''
        SELECT f.name, f.calories, f.protein, f.carbs, f.fat,
               fl.meal_type, fl.servings,
               ROUND(f.calories * fl.servings) as total_calories,
               ROUND(f.protein * fl.servings, 1) as total_protein,
               ROUND(f.carbs   * fl.servings, 1) as total_carbs,
               ROUND(f.fat     * fl.servings, 1) as total_fat
        FROM food_log fl
        JOIN foods f ON fl.food_id = f.id
        WHERE fl.date = ? AND fl.user_id = ?
        ORDER BY fl.meal_type
    ''', (date_str, user_id))

    foods = cursor.fetchall()
    conn.close()

    return jsonify([dict(f) for f in foods])

# Delete food from log (with user verification)
@app.route('/api/delete-food/<int:log_id>', methods=['DELETE'])
@login_required
def delete_food(log_id):
    conn = get_db()
    cursor = conn.cursor()
    
    user_id = session['user_id']
    
    # Only delete if it belongs to the logged-in user
    cursor.execute('DELETE FROM food_log WHERE id = ? AND user_id = ?', (log_id, user_id))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

# Get current user info
@app.route('/api/user')
@login_required
def get_user():
    conn = get_db()
    cursor = conn.cursor()
    
    user_id = session['user_id']
    cursor.execute('SELECT username, email, is_student FROM users WHERE id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    return jsonify(dict(user))

if __name__ == '__main__':
    app.run(debug=True)