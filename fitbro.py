from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import sqlite3
from datetime import date, datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import requests as http
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = 'smtp-relay.brevo.com'
SMTP_PORT = 587
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASS = os.environ.get('SMTP_PASS', '')
SMTP_FROM = os.environ.get('SMTP_FROM', '') or os.environ.get('SMTP_USER', '')

UNI_DOMAINS = ('.ac.uk', '.edu', '.edu.au', '.ac.nz', '.ac.in', '.edu.sg', '.ac.za')

def send_verification_email(to_email, code):
    if not SMTP_USER or not SMTP_PASS:
        print(f'\n[DEV] Verification code for {to_email}: {code}\n')
        return True, None
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'FitBro – Your student verification code'
    msg['From']    = SMTP_FROM
    msg['To']      = to_email
    body = (
        f'Hi,\n\n'
        f'Your FitBro student verification code is:\n\n'
        f'  {code}\n\n'
        f'It expires in 10 minutes. If you did not request this, ignore this email.\n\n'
        f'– The FitBro Team'
    )
    html = f'''<div style="font-family:sans-serif;max-width:400px;margin:auto">
        <h2 style="color:#48c774">FitBro Student Verification</h2>
        <p>Your verification code is:</p>
        <div style="font-size:36px;font-weight:700;letter-spacing:10px;color:#2c3e50;
                    background:#f0f9f4;padding:20px;border-radius:10px;text-align:center">
            {code}
        </div>
        <p style="color:#7f8c8d;font-size:13px">Expires in 10 minutes.</p>
    </div>'''
    msg.attach(MIMEText(body, 'plain'))
    msg.attach(MIMEText(html, 'html'))
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, to_email, msg.as_string())
        return True, None
    except Exception as e:
        print(f'[EMAIL ERROR] {e}')
        return False, str(e)

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)


def migrate_exercise_log():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(exercise_log)")
    columns = [col['name'] for col in cursor.fetchall()]
    if 'sets' not in columns:
        cursor.execute('ALTER TABLE exercise_log RENAME TO exercise_log_old')
        cursor.execute('''
            CREATE TABLE exercise_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                exercise_name TEXT NOT NULL,
                sets INTEGER NOT NULL DEFAULT 3,
                reps INTEGER NOT NULL DEFAULT 10,
                date TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
        ''')
        cursor.execute('DROP TABLE exercise_log_old')
        conn.commit()
    conn.close()


def migrate_workout_sessions():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS workout_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    cursor.execute("PRAGMA table_info(exercise_log)")
    columns = [col['name'] for col in cursor.fetchall()]
    if 'session_id' not in columns:
        cursor.execute('ALTER TABLE exercise_log ADD COLUMN session_id INTEGER REFERENCES workout_sessions(id)')
    if 'completed' not in columns:
        cursor.execute('ALTER TABLE exercise_log ADD COLUMN completed INTEGER DEFAULT 0')
    conn.commit()
    conn.close()

OFF_TIMEOUT = 5


def get_db():
    conn = sqlite3.connect('fitness.db')
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn


# checks if the user is logged in before letting them access a page
#protecting the routes
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

#STUDENT EMAIL VERIFICATION FUNCTION

@app.route('/api/send-verification', methods=['POST'])
def send_verification():
    data = request.json
    email    = (data.get('email') or '').strip().lower()
    username = (data.get('username') or '').strip()
    password =  data.get('password') or ''

#CHECK AGAINST A LIST OF UNI DOMAINS

    if not email or not username or not password:
        return jsonify({'success': False, 'error': 'All fields required'})

    domain = email.split('@')[-1] if '@' in email else ''
    if not any(domain.endswith(d) for d in UNI_DOMAINS):
        return jsonify({'success': False,
                        'error': 'Please use a university email (.ac.uk, .edu, etc.)'})

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Email already registered'})
    conn.close()

    #Code gets generated for email verification
    code = str(secrets.randbelow(900000) + 100000)
    session['stu_code']    = code
    session['stu_email']   = email
    session['stu_expires'] = (datetime.now() + timedelta(minutes=10)).isoformat()
    session['stu_pending'] = {'username': username, 'email': email, 'password': password}

    sent, err = send_verification_email(email, code)
    if not sent:
        return jsonify({'success': False, 'error': f'Failed to send email: {err}'})

    return jsonify({'success': True})


@app.route('/api/verify-student', methods=['POST'])
def verify_student():
    data = request.json
    code = (data.get('code') or '').strip()

    stored_code    = session.get('stu_code')
    stored_expires = session.get('stu_expires')
    pending        = session.get('stu_pending')

    if not stored_code or not pending:
        return jsonify({'success': False, 'error': 'Session expired. Please start again.'})

    #Code Expirery - Check if verification code has expired (10 minutes)
    if datetime.now() > datetime.fromisoformat(stored_expires):
        return jsonify({'success': False, 'error': 'Code expired. Please request a new one.'})

    if code != stored_code:
        return jsonify({'success': False, 'error': 'Incorrect code. Please try again.'})

    # Code is valid — create the account
    username = pending['username']
    email    = pending['email']
    hashed   = generate_password_hash(pending['password'])

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({'success': False, 'error': 'Email already registered'})

    #The user gets inserted into the database
    cursor.execute('''
        INSERT INTO users (username, email, password, is_student, age, height,
                           daily_calorie_goal, daily_protein_goal, daily_carbs_goal, daily_fat_goal)
        VALUES (?, ?, ?, 1, 25, 175.0, 2000, 150, 200, 65)
    ''', (username, email, hashed))
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()

    for key in ('stu_code', 'stu_email', 'stu_expires', 'stu_pending'):
        session.pop(key, None)

    session['user_id']  = user_id
    session['username'] = username
    return jsonify({'success': True})


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

#Examples of protecting routes being used to access features

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
    return render_template('nutribot.html')

@app.route('/nutribot-info')
@login_required
def nutribot_info():
    return render_template('nutribot_detail.html')


@app.route('/profile')
@login_required
def profile():
    return render_template('profile.html')


@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html')


@app.route('/workout')
@login_required
def workout():
    return render_template('workout.html')


@app.route('/api/log-exercise', methods=['POST'])
@login_required
def log_exercise():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO exercise_log (user_id, exercise_name, sets, reps, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        session['user_id'],
        data['exercise_name'],
        data.get('sets', 3),
        data.get('reps', 10),
        data.get('date', str(date.today()))
    ))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/log-workout-session', methods=['POST'])
@login_required
def log_workout_session():
    data = request.json
    name = data.get('name', '').strip()
    exercises = data.get('exercises', [])
    if not name or not exercises:
        return jsonify({'success': False})
    today = str(date.today())
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO workout_sessions (user_id, name, date) VALUES (?, ?, ?)',
        (session['user_id'], name, today)
    )
    workout_session_id = cursor.lastrowid
    for e in exercises:
        cursor.execute('''
            INSERT INTO exercise_log (user_id, exercise_name, sets, reps, date, session_id)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (session['user_id'], e['exercise_name'], e['sets'], e['reps'], today, workout_session_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/exercise-log')
@login_required
def get_exercise_log():
    conn = get_db()
    cursor = conn.cursor()
    today = str(date.today())
    user_id = session['user_id']

    cursor.execute('''
        SELECT ws.id as session_id, ws.name as session_name,
               el.id, el.exercise_name, el.sets, el.reps, el.completed
        FROM workout_sessions ws
        JOIN exercise_log el ON el.session_id = ws.id
        WHERE ws.user_id = ? AND ws.date = ?
        ORDER BY ws.id, el.id
    ''', (user_id, today))
    sessions_dict = {}
    for row in cursor.fetchall():
        sid = row['session_id']
        if sid not in sessions_dict:
            sessions_dict[sid] = {'id': sid, 'name': row['session_name'], 'exercises': []}
        sessions_dict[sid]['exercises'].append({
            'id': row['id'],
            'exercise_name': row['exercise_name'],
            'sets': row['sets'],
            'reps': row['reps'],
            'completed': bool(row['completed'])
        })

    cursor.execute('''
        SELECT id, exercise_name, sets, reps
        FROM exercise_log
        WHERE user_id = ? AND date = ? AND session_id IS NULL
        ORDER BY id DESC
    ''', (user_id, today))
    individual = [dict(e) for e in cursor.fetchall()]

    conn.close()
    return jsonify({'sessions': list(sessions_dict.values()), 'individual': individual})


@app.route('/api/delete-exercise/<int:log_id>', methods=['DELETE'])
@login_required
def delete_exercise(log_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM exercise_log WHERE id = ? AND user_id = ?', (log_id, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/delete-session/<int:workout_session_id>', methods=['DELETE'])
@login_required
def delete_session(workout_session_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM workout_sessions WHERE id = ? AND user_id = ?',
                   (workout_session_id, session['user_id']))
    if not cursor.fetchone():
        conn.close()
        return jsonify({'success': False})
    cursor.execute('DELETE FROM exercise_log WHERE session_id = ?', (workout_session_id,))
    cursor.execute('DELETE FROM workout_sessions WHERE id = ?', (workout_session_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/exercise-log/<int:ex_id>/complete', methods=['PATCH'])
@login_required
def complete_exercise(ex_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('UPDATE exercise_log SET completed = 1 WHERE id = ? AND user_id = ?',
                   (ex_id, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/food-log')
@login_required
def get_food_log():
    conn = get_db()
    cursor = conn.cursor()
    today = str(date.today())
    user_id = session['user_id']
    cursor.execute('''
        SELECT f.name, f.calories, f.protein, f.carbs, f.fat,
               fl.meal_type, fl.servings, fl.id as log_id
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


# returns the last 7 days of nutrition totals grouped by date
# used by the NutriBot page to analyse the users recent eating habits
@app.route('/api/nutrition-summary')
@login_required
def nutrition_summary():
    conn = get_db()
    cursor = conn.cursor()
    user_id = session['user_id']
    cursor.execute('''
        SELECT fl.date,
               ROUND(SUM(f.calories * fl.servings))      as total_calories,
               ROUND(SUM(f.protein  * fl.servings), 1)   as total_protein,
               ROUND(SUM(f.carbs    * fl.servings), 1)   as total_carbs,
               ROUND(SUM(f.fat      * fl.servings), 1)   as total_fat
        FROM food_log fl
        JOIN foods f ON fl.food_id = f.id
        WHERE fl.user_id = ?
        AND fl.date >= date('now', '-6 days')
        GROUP BY fl.date
        ORDER BY fl.date DESC
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


# words that suggest a food is processed or not a basic ingredient
# results containing these words get pushed lower in the search rankings
PROCESSED_WORDS = {
    'flavour', 'flavoured', 'flavor', 'flavored',
    'seasoned', 'seasoning', 'spiced', 'spicy',
    'style', 'taste', 'infused', 'marinated',
    'curry', 'bbq', 'sweet', 'smoky', 'smoked',
    'juice', 'drink', 'beverage', 'smoothie',
    'sauce', 'extract', 'syrup', 'concentrate',
    'instant', 'ready', 'frozen', 'tinned', 'canned',
    'processed', 'reformed', 'coated', 'breaded',
    'powder', 'mix', 'blend', 'composite',
    'noodles', 'soup', 'chips', 'crisps', 'snack',
    'nuggets', 'fingers', 'bites', 'strips',
    'bar', 'biscuit', 'cookie', 'cake', 'crackers',
    'spread', 'dip', 'paste',
    'organic', 'organics', '100%', 'eve', 'llc', 'inc', '&'
}


# gives each result a score based on how well it matches what the user typed
# then by name length, shorter names rank higher within the same quality level
# score 0 exact match, 1 starts with query and is a whole food
# score 2 query is somewhere in the name and is a whole food
# score 3 starts with query but contains processed food words
# score 4 query is somewhere in the name and contains processed food words
def match_score(name, query):
    n = name.lower()
    q = query.lower()
    words = set(n.split())
    word_count = len(n.split())
    has_processed = bool(words & PROCESSED_WORDS)

    if n == q:
        return (0, word_count)
    if n.startswith(q):
        return (1, word_count) if not has_processed else (3, word_count)
    return (2, word_count) if not has_processed else (4, word_count)


# filters out results with no name or no calories
# also removes anything where the query word is not actually in the name
# then sorts everything so the best matches come first
def parse_and_sort(products, query):
    results = []
    q = query.lower()

    for p in products:
        name = p.get('product_name', '').strip()
        nutrients = p.get('nutriments', {})

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

    results.sort(key=lambda r: match_score(r['name'], query))
    return results

#OPENFOODFACTS API

# tries the main OpenFoodFacts API first
# if that fails or returns nothing it tries the backup API
@app.route('/api/search-food')
@login_required
def search_food():
    q = request.args.get('q', '')
    if not q:
        return jsonify([])

    headers = {'User-Agent': 'FitBro-FinalYearProject/1.0'}

    try:
        res = http.get(
            'https://world.openfoodfacts.org/cgi/search.pl',
            params={
                'action':       'process',
                'search_terms': q,
                'json':         '1',
                'page_size':    25,
                'sort_by':      'unique_scans_n',
                'fields':       'product_name,nutriments,brands',
                'lc':           'en',
                'cc':           'gb'
            },
            headers=headers,
            timeout=OFF_TIMEOUT,
            verify=False
        )
        if res.status_code == 200:
            products = res.json().get('products', [])
            valid = parse_and_sort(products, q)
            if valid:
                return jsonify(valid)

    except Exception as e:
        print(f'Main API failed: {e}')

    try:
        res = http.get(
            'https://search.openfoodfacts.org/search',
            params={
                'q':         q,
                'page_size': 25,
                'fields':    'product_name,nutriments,brands',
                'lang':      'en',
                'cc':        'gb'
            },
            headers=headers,
            timeout=OFF_TIMEOUT,
            verify=False
        )
        if res.status_code == 200:
            products = res.json().get('hits', [])
            valid = parse_and_sort(products, q)
            return jsonify(valid)

    except Exception as e:
        print(f'Backup API failed: {e}')

    return jsonify([])


# saves the food to the foods table if it doesnt exist already
# then logs it against the users account for the chosen meal
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

    # all nutrition values are per 100g so 150g = 1.5 servings
    servings = round(grams / 100, 2)

    cursor.execute('''
        INSERT INTO food_log (user_id, food_id, meal_type, servings, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (session['user_id'], food_id, meal_type, servings, log_date))

    conn.commit()
    conn.close()
    return jsonify({'success': True})


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
               fl.meal_type, fl.servings, fl.id as log_id,
               ROUND(f.calories * fl.servings)      as total_calories,
               ROUND(f.protein  * fl.servings, 1)   as total_protein,
               ROUND(f.carbs    * fl.servings, 1)   as total_carbs,
               ROUND(f.fat      * fl.servings, 1)   as total_fat
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
    cursor.execute('''
        SELECT username, email, is_student,
               daily_calorie_goal, daily_protein_goal,
               daily_carbs_goal, daily_fat_goal
        FROM users WHERE id = ?
    ''', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return jsonify(dict(user))


# saves updated calorie and macro goals for the logged in user
@app.route('/api/update-goals', methods=['POST'])
@login_required
def update_goals():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE users SET
            daily_calorie_goal = ?,
            daily_protein_goal = ?,
            daily_carbs_goal   = ?,
            daily_fat_goal     = ?
        WHERE id = ?
    ''', (
        int(data.get('calories', 2000)),
        int(data.get('protein',  150)),
        int(data.get('carbs',    200)),
        int(data.get('fat',      65)),
        session['user_id']
    ))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/api/delete-account', methods=['POST'])
@login_required
def delete_account():
    user_id = session['user_id']
    conn = get_db()
    conn.execute('DELETE FROM users WHERE id = ?', (user_id,))
    conn.commit()
    conn.close()
    session.clear()
    return jsonify({'success': True})



if __name__ == '__main__':
    migrate_exercise_log()
    migrate_workout_sessions()
    app.run(debug=True)