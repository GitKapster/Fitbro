# Updated fitbro.py with authentication

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import requests as http  # for calling OpenFoodFacts server-side

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

def get_db():
    conn = sqlite3.connect('fitness.db')
    conn.row_factory = sqlite3.Row
    return conn

def login_required(f):
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.json
        email = data.get('email')
        password = data.get('password')
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Invalid email or password'})
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        data = request.json
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')
        is_student = data.get('is_student', False)
        if not username or not email or not password:
            return jsonify({'success': False, 'error': 'All fields required'})
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Email already registered'})
        hashed_password = generate_password_hash(password)
        cursor.execute('''
            INSERT INTO users (username, email, password, is_student, age, height,
                             daily_calorie_goal, daily_protein_goal, daily_carbs_goal, daily_fat_goal)
            VALUES (?, ?, ?, ?, 25, 175.0, 2000, 150, 200, 65)
        ''', (username, email, hashed_password, is_student))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        session['user_id'] = user_id
        session['username'] = username
        return jsonify({'success': True})
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def home():
    return render_template('dashboard.html')

@app.route('/add-food')
@login_required
def add_food_page():
    return render_template('add_food.html')

@app.route('/meal/<meal_type>')
@login_required
def meal_detail(meal_type):
    return render_template('meal_detail.html', meal_type=meal_type)

@app.route('/stats')
@login_required
def stats():
    return render_template('stats.html')

@app.route('/community')
@login_required
def community():
    return render_template('community.html')

@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')

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

@app.route('/api/add-food', methods=['POST'])
@login_required
def add_food_api():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    user_id = session['user_id']
    log_date = data.get('date', str(date.today()))
    cursor.execute('''
        INSERT INTO food_log (user_id, food_id, meal_type, servings, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, data['food_id'], data['meal_type'], data['servings'], log_date))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

# ── NEW: Search OpenFoodFacts from the server so the browser avoids CORS ─────
# The frontend calls this instead of hitting OpenFoodFacts directly.
# Flask makes the request and passes the results back as JSON.
@app.route('/api/search-food')
@login_required
def search_food():
    q = request.args.get('q', '')
    if not q:
        return jsonify([])

    # OpenFoodFacts blocks requests with no User-Agent, so we set one
    res = http.get(
        'https://world.openfoodfacts.org/cgi/search.pl',
        params={
            'search_terms': q,
            'json':         'true',
            'page_size':    10,
            'fields':       'product_name,nutriments,brands'
        },
        headers={'User-Agent': 'FitBro-App/1.0'},
        timeout=8
    )
    products = res.json().get('products', [])

    # Only return products that have a name and calorie data
    valid = [
        {
            'name':     p['product_name'],
            'calories': p['nutriments'].get('energy-kcal_100g', 0),
            'protein':  p['nutriments'].get('proteins_100g', 0),
            'carbs':    p['nutriments'].get('carbohydrates_100g', 0),
            'fat':      p['nutriments'].get('fat_100g', 0),
            'brand':    p.get('brands', '')
        }
        for p in products
        if p.get('product_name') and p.get('nutriments', {}).get('energy-kcal_100g')
    ]

    return jsonify(valid)
# ─────────────────────────────────────────────────────────────────────────────

# ── NEW: Save an OpenFoodFacts food and log it in one go ──────────────────────
# The frontend sends the food's nutritional info (per 100g) + how many grams
# the user wants to log. We save the food to the foods table if it's new,
# then create a food_log entry with servings = grams / 100.
@app.route('/api/add-openfood', methods=['POST'])
@login_required
def add_openfood():
    data = request.json
    name      = data['name']
    calories  = round(data['calories'])   # per 100g
    protein   = data['protein']           # per 100g
    carbs     = data['carbs']             # per 100g
    fat       = data['fat']               # per 100g
    grams     = float(data.get('grams', 100))
    meal_type = data['meal_type']
    log_date  = data.get('date', str(date.today()))

    conn = get_db()
    cursor = conn.cursor()

    # Check if this food already exists so we don't add duplicates
    cursor.execute('SELECT id FROM foods WHERE name = ?', (name,))
    existing = cursor.fetchone()

    if existing:
        food_id = existing['id']
    else:
        # Insert new food — values are stored per 100g, matching the rest of the DB
        cursor.execute('''
            INSERT INTO foods (name, calories, protein, carbs, fat, serving_size)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (name, calories, protein, carbs, fat, '100g'))
        food_id = cursor.lastrowid

    # 1 serving = 100g, so 150g = 1.5 servings
    servings = round(grams / 100, 2)

    cursor.execute('''
        INSERT INTO food_log (user_id, food_id, meal_type, servings, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (session['user_id'], food_id, meal_type, servings, log_date))

    conn.commit()
    conn.close()

    return jsonify({'success': True})
# ─────────────────────────────────────────────────────────────────────────────

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

@app.route('/api/delete-food/<int:log_id>', methods=['DELETE'])
@login_required
def delete_food(log_id):
    conn = get_db()
    cursor = conn.cursor()
    user_id = session['user_id']
    cursor.execute('DELETE FROM food_log WHERE id = ? AND user_id = ?', (log_id, user_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

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