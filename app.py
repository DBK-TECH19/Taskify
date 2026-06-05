import os
from flask import Flask, request, jsonify, make_response
from flask_cors import CORS
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
import psycopg2
from psycopg2.extras import RealDictCursor

load_dotenv()

app = Flask(__name__)
# Robust CORS configuration targeting all paths
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
bcrypt = Bcrypt(app)

DATABASE_URL = os.getenv("DATABASE_URL")

def get_db_connection():
    url = DATABASE_URL
    if url and url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return psycopg2.connect(url, cursor_factory=RealDictCursor)

def init_db():
    """Initializes clean database schema tables from scratch."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Create Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        
        # 2. Create Tasks Table linked via foreign key
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(255) NOT NULL,
                description TEXT,
                status VARCHAR(50) DEFAULT 'Pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        ''')
        conn.commit()
        cursor.close()
        conn.close()
        print("🚀 Database structurally initialized! Clean tables are ready.")
    except Exception as e:
        print(f"❌ Database blueprint initialization failure: {e}")

@app.before_request
def handle_preflight():
    """Handles preflight OPTIONS requests before reaching endpoints."""
    if request.method == "OPTIONS":
        response = make_response()
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
        return response, 200

@app.route('/')
def home():
    return jsonify({"message": "Taskify Auth API running smoothly."}), 200

# --- 1. USER REGISTRATION ---
@app.route('/api/register', methods=['POST', 'OPTIONS'])
def register():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s) RETURNING id, username;",
            (username, hashed_password)
        )
        new_user = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "User registered successfully!", "user": new_user}), 201
    except psycopg2.errors.UniqueViolation:
        return jsonify({"error": "Username already exists."}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 2. USER LOGIN ---
@app.route('/api/login', methods=['POST', 'OPTIONS'])
def login():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    data = request.get_json() or {}
    username = data.get('username', '').strip()
    password = data.get('password', '')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s;", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and bcrypt.check_password_hash(user['password_hash'], password):
            return jsonify({
                "message": "Login successful!",
                "user": {"id": user['id'], "username": user['username']}
            }), 200
        else:
            return jsonify({"error": "Invalid username or password."}), 401
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 3. GET USER TASKS ---
@app.route('/api/tasks', methods=['GET', 'OPTIONS'])
def get_tasks():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    user_id = request.args.get('user_id')
    if not user_id or user_id in ["null", "undefined"]:
        return jsonify([]), 200
        
    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return jsonify([]), 200
        
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tasks WHERE user_id = %s ORDER BY created_at DESC;", (user_id,))
        tasks = cursor.fetchall()
        cursor.close()
        conn.close()
        return jsonify(list(tasks)), 200
    except Exception as e:
        print(f"❌ FETCH ERROR: {str(e)}")
        return jsonify([]), 200

# --- 4. CREATE TASK ---
@app.route('/api/tasks', methods=['POST', 'OPTIONS'])
def create_task():
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    data = request.get_json() or {}
    user_id = data.get('user_id')
    title = data.get('title', '').strip()
    description = data.get('description', '')

    if not user_id or user_id in ["null", "undefined"]:
        return jsonify({"error": "Unauthorized. Missing user data."}), 401
    if not title:
        return jsonify({"error": "Title required."}), 400

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid user identification sequence."}), 400

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (user_id, title, description, status) 
            VALUES (%s, %s, %s, %s) 
            RETURNING id, user_id, title, description, status, created_at;
            """,
            (user_id, title, description, 'Pending')
        )
        new_task = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(dict(new_task)), 201
    except Exception as e:
        print(f"❌ DATABASE INSERT CRASH: {str(e)}")
        return jsonify({"error": str(e)}), 500

# --- 5. UPDATE TASK STATUS ---
@app.route('/api/tasks/<int:task_id>', methods=['PUT', 'OPTIONS'])
def update_task(task_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    data = request.get_json() or {}
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tasks WHERE id = %s;", (task_id,))
        task = cursor.fetchone()
        if not task:
            cursor.close()
            conn.close()
            return jsonify({"error": "Task context missing."}), 404

        title = data.get('title', task['title']).strip()
        description = data.get('description', task['description'])
        status = data.get('status', task['status'])

        cursor.execute(
            "UPDATE tasks SET title = %s, description = %s, status = %s WHERE id = %s RETURNING *;",
            (title, description, status, task_id)
        )
        updated_task = cursor.fetchone()
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify(dict(updated_task)), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- 6. DELETE TASK ---
@app.route('/api/tasks/<int:task_id>', methods=['DELETE', 'OPTIONS'])
def delete_task(task_id):
    if request.method == 'OPTIONS':
        return jsonify({}), 200
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM tasks WHERE id = %s;", (task_id,))
        if not cursor.fetchone():
            cursor.close()
            conn.close()
            return jsonify({"error": "Task not found."}), 404

        cursor.execute("DELETE FROM tasks WHERE id = %s;", (task_id,))
        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({"message": "Deleted successfully."}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)