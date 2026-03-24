# Updated fitbro.py with authentication + OpenFoodFacts fallback search

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
from datetime import date
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import requests as http  # for calling OpenFoodFacts server-side

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# How long to wait for each API before giving up (seconds)
# Set low so the fallback kicks in quickly if the primary is slow
OFF_TIMEOUT = 5

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


# ── Helper: score how closely a name matches the search query ────────────────
# Lower score = better match, so we can sort ascending
# 0 = exact match, 1 = name starts with query, 2 = query appears in name
def match_score(name, query):
    n = name.lower()
    q = query.lower()
    if n == q:
        return 0
    if n.startswith(q):
        return 1
    return 2


# ── Helper: parse + filter + sort results ────────────────────────────────────
# Only keeps products whose name actually contains the search query —
# this is what removes French results like "Chaussons aux pommes" when
# the user searched "apple", since the name doesn't contain "apple" at all
def parse_and_sort(products, query):
    results = []
    q = query.lower()

    for p in products:
        name = p.get('product_name', '').strip()
        nutrients = p.get('nutriments', {})

        # skip if no name, no calories, or name doesn't contain the query word
        if not name or not nutrients.get('energy-kcal_100g'):
            continue
        if q not in name.lower():
            continue

        results.append({
            'name':     name,
            'calories': nutrients.get('energy-kcal_100g', 0),
            'protein':  nutrients.get('proteins_100g', 0),
            'carbs':    nutrients.get('carbohydrates_100g', 0),
            'fat':      nutrients.get('fat_100g', 0),
            'brand':    p.get('brands', '')
        })

    # sort so closest match comes first
    results.sort(key=lambda r: match_score(r['name'], query))
    return results


# ── Search OpenFoodFacts — tries primary first, falls back if it's down ───────
# The primary search API (/cgi/search.pl) has known reliability issues
# (around 94% uptime, very slow response times).
# If it times out or fails, we fall back to search.openfoodfacts.org
# which sits at 100% uptime.
@app.route('/api/search-food')
@login_required
def search_food():
    q = request.args.get('q', '')
    if not q:
        return jsonify([])

    headers = {'User-Agent': 'FitBro-FinalYearProject/1.0'}

    # ── Step 1: Try the primary search API ───────────────────────────────────
    try:
        res = http.get(
            'https://world.openfoodfacts.org/cgi/search.pl',
            params={
                'action':       'process',
                'search_terms': q,
                'json':         '1',
                'page_size':    10,
                'fields':       'product_name,nutriments,brands',
                'lc':           'en',  # return English product names only
                'cc':           'gb'   # prioritise UK products
            },
            headers=headers,
            timeout=OFF_TIMEOUT,  # give up after 5 seconds
            verify=False
        )
        print('Primary API status:', res.status_code)

        if res.status_code == 200:
            products = res.json().get('products', [])
            valid = parse_and_sort(products, q)

            # only return primary results if we actually got something back
            if valid:
                return jsonify(valid)
            
            print('Primary returned no valid results, trying fallback...')

    except Exception as e:
        # timed out or connection error — move straight to fallback
        print(f'Primary API failed ({e}), trying fallback...')

    # ── Step 2: Fallback to the dedicated search service ─────────────────────
    try:
        res = http.get(
            'https://search.openfoodfacts.org/search',
            params={
                'q':          q,
                'page_size':  10,
                'fields':     'product_name,nutriments,brands',
                'lang':       'en',  # English names only
                'cc':         'gb'   # UK products
            },
            headers=headers,
            timeout=OFF_TIMEOUT,
            verify=False
        )
        print('Fallback API status:', res.status_code)

        if res.status_code == 200:
            # fallback uses "hits" as its key instead of "products"
            products = res.json().get('hits', [])
            valid = parse_and_sort(products, q)
            return jsonify(valid)

    except Exception as e:
        print(f'Fallback API also failed: {e}')

    # both APIs failed — return empty so the frontend shows "no results"
    return jsonify([])
# ─────────────────────────────────────────────────────────────────────────────


# ── Save an OpenFoodFacts food and log it in one go ───────────────────────────
@app.route('/api/add-openfood', methods=['POST'])
@login_required
def add_openfood():
    data = request.json
    name      = data['name']
    calories  = round(data['calories'])
    protein   = data['protein']
    carbs     = data['carbs']
    fat       = data['fat']
    grams     = float(data.get('grams', 100))
    meal_type = data['meal_type']
    log_date  = data.get('date', str(date.today()))

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('SELECT id FROM foods WHERE name = ?', (name,))
    existing = cursor.fetchone()

    if existing:
        food_id = existing['id']
    else:
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