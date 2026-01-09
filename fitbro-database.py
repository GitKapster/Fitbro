import sqlite3

def init_db():
    conn = sqlite3.connect('fitness.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            age INTEGER,
            weight REAL,
            height REAL,
            daily_calorie_goal INTEGER,
            daily_protein_goal INTEGER,
            daily_carbs_goal INTEGER,
            daily_fat_goal INTEGER
        )
    ''')
    
    # Food database (all available foods)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS foods (
            id INTEGER PRIMARY KEY,
            name TEXT,
            calories INTEGER,
            protein REAL,
            carbs REAL,
            fat REAL,
            serving_size TEXT
        )
    ''')
    
    # Daily food log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS food_log (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            food_id INTEGER,
            meal_type TEXT,
            servings REAL,
            date TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (food_id) REFERENCES foods (id)
        )
    ''')
    
    # Exercise log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exercise_log (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            exercise_name TEXT,
            calories_burned INTEGER,
            duration_minutes INTEGER,
            date TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Body measurements over time
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            weight REAL,
            body_part TEXT,
            measurement REAL,
            date TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("Database created with all tables!")

if __name__ == '__main__':
    init_db()