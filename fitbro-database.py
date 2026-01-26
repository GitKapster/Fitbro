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
    
    # Add default user
    cursor.execute('''
        INSERT OR IGNORE INTO users (id, username, age, weight, height, 
                                     daily_calorie_goal, daily_protein_goal, 
                                     daily_carbs_goal, daily_fat_goal)
        VALUES (1, 'User', 25, 75.0, 175.0, 2000, 150, 200, 65)
    ''')
    
    # Add sample food items
    foods = [
        (1, 'Chicken Breast', 165, 31, 0, 3.6, '100g'),
        (2, 'Brown Rice', 215, 5, 45, 1.6, '1 cup'),
        (3, 'Avocado', 240, 3, 13, 22, '1 whole'),
        (4, 'Banana', 105, 1.3, 27, 0.4, '1 medium'),
        (5, 'Greek Yogurt', 100, 17, 6, 0.7, '170g'),
        (6, 'Almonds', 160, 6, 6, 14, '28g'),
    ]
    
    cursor.executemany('''
        INSERT OR IGNORE INTO foods (id, name, calories, protein, carbs, fat, serving_size)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', foods)
    
    conn.commit()
    conn.close()
    print("Database created with all tables!")

if __name__ == '__main__':
    init_db()