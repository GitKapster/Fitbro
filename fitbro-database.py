# Updated fitbro-database.py with authentication fields

import sqlite3
import os

def init_db():
    # Check if database exists and delete it to start fresh
    if os.path.exists('fitness.db'):
        print("Found existing database. Deleting to create fresh database...")
        os.remove('fitness.db')
    
    conn = sqlite3.connect('fitness.db')
    cursor = conn.cursor()
    
    # Users table - now with email and password for authentication
    cursor.execute('''
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_student BOOLEAN DEFAULT 0,
            age INTEGER DEFAULT 25,
            height REAL DEFAULT 175.0,
            daily_calorie_goal INTEGER DEFAULT 2000,
            daily_protein_goal INTEGER DEFAULT 150,
            daily_carbs_goal INTEGER DEFAULT 200,
            daily_fat_goal INTEGER DEFAULT 65,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Food database (all available foods)
    cursor.execute('''
        CREATE TABLE foods (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            calories INTEGER NOT NULL,
            protein REAL NOT NULL,
            carbs REAL NOT NULL,
            fat REAL NOT NULL,
            serving_size TEXT NOT NULL
        )
    ''')
    
    # Daily food log
    cursor.execute('''
        CREATE TABLE food_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            food_id INTEGER NOT NULL,
            meal_type TEXT NOT NULL,
            servings REAL DEFAULT 1.0,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
            FOREIGN KEY (food_id) REFERENCES foods (id) ON DELETE CASCADE
        )
    ''')
    
    # Exercise log
    cursor.execute('''
        CREATE TABLE exercise_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            exercise_name TEXT NOT NULL,
            calories_burned INTEGER NOT NULL,
            duration_minutes INTEGER NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    # Body measurements over time
    cursor.execute('''
        CREATE TABLE measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            weight REAL,
            body_part TEXT,
            measurement REAL,
            date TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    
    # Add sample food items
    foods = [
        (1, 'Chicken Breast', 165, 31, 0, 3.6, '100g'),
        (2, 'Brown Rice', 215, 5, 45, 1.6, '1 cup'),
        (3, 'Avocado', 240, 3, 13, 22, '1 whole'),
        (4, 'Banana', 105, 1.3, 27, 0.4, '1 medium'),
        (5, 'Greek Yogurt', 100, 17, 6, 0.7, '170g'),
        (6, 'Almonds', 160, 6, 6, 14, '28g'),
        (7, 'Salmon', 208, 20, 0, 13, '100g'),
        (8, 'Sweet Potato', 86, 1.6, 20, 0.1, '100g'),
        (9, 'Oatmeal', 389, 17, 66, 7, '100g'),
        (10, 'Eggs', 155, 13, 1.1, 11, '2 large'),
        (11, 'Broccoli', 55, 3.7, 11, 0.6, '1 cup'),
        (12, 'Pasta', 131, 5, 25, 1.1, '100g'),
        (13, 'Apple', 95, 0.5, 25, 0.3, '1 medium'),
        (14, 'Milk', 103, 8, 12, 2.4, '1 cup'),
        (15, 'Peanut Butter', 188, 8, 7, 16, '2 tbsp'),
    ]
    
    cursor.executemany('''
        INSERT INTO foods (id, name, calories, protein, carbs, fat, serving_size)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', foods)
    
    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()