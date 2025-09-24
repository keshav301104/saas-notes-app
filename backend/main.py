import os
import psycopg2
import bcrypt
import jwt
import uuid
import time
from datetime import datetime, timedelta
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- Flask App Initialization ---
app = Flask(__name__)
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET')
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(hours=1)
app.config['CORS_HEADERS'] = 'Content-Type'

# --- Database Connection ---
DATABASE_URL = os.getenv('DATABASE_URL')
def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

# --- Seed the database with initial data ---
def seed_database():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT COUNT(*) FROM tenants;")
        if cur.fetchone()[0] > 0:
            print("Database already seeded. Skipping.")
            return

        print("Starting database seeding...")
        
        # Generate UUIDs for tenants
        acme_tenant_id = str(uuid.uuid4())
        globex_tenant_id = str(uuid.uuid4())

        # Insert tenants
        cur.execute("""
            INSERT INTO tenants (id, slug, name, plan) VALUES
            (%s, %s, %s, %s),
            (%s, %s, %s, %s);
        """, (acme_tenant_id, 'acme', 'Acme', 'Free', globex_tenant_id, 'globex', 'Globex', 'Free'))

        # Hash passwords for test accounts
        hashed_password = bcrypt.hashpw('password'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

        # Insert test users
        cur.execute("""
            INSERT INTO users (id, tenant_id, email, password_hash, role) VALUES
            (%s, %s, %s, %s, %s),
            (%s, %s, %s, %s, %s);
        """, (str(uuid.uuid4()), acme_tenant_id, 'admin@acme.test', hashed_password, 'Admin', 
              str(uuid.uuid4()), acme_tenant_id, 'user@acme.test', hashed_password, 'Member'))

        cur.execute("""
            INSERT INTO users (id, tenant_id, email, password_hash, role) VALUES
            (%s, %s, %s, %s, %s),
            (%s, %s, %s, %s, %s);
        """, (str(uuid.uuid4()), globex_tenant_id, 'admin@globex.test', hashed_password, 'Admin', 
              str(uuid.uuid4()), globex_tenant_id, 'user@globex.test', hashed_password, 'Member'))

        conn.commit()
        print("Database seeded successfully.")
    except Exception as e:
        conn.rollback()
        print(f"Database seeding failed: {e}")
    finally:
        cur.close()
        conn.close()

# Execute seeding function on app startup
seed_database()

# --- Authentication Middleware ---
def verify_token(f):
    def wrapper(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return jsonify({"message": "Authorization token is missing!"}), 401
        
        token = auth_header.split(" ")[1]
        try:
            payload = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            request.user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token has expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Invalid token"}), 401
        
        return f(*args, **kwargs)
    return wrapper

# --- API Endpoints ---

# Health check endpoint
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok"})

# Login endpoint
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, tenant_id, role, password_hash FROM users WHERE email = %s", (email,))
        user = cur.fetchone()

        if user and bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):
            token_payload = {
                "id": user[0],
                "tenant_id": user[1],
                "role": user[2],
                "exp": datetime.now() + app.config['JWT_ACCESS_TOKEN_EXPIRES']
            }
            token = jwt.encode(token_payload, app.config['JWT_SECRET_KEY'], algorithm="HS256")
            return jsonify({"token": token, "user": {"id": user[0], "email": email, "role": user[2], "tenant_id": user[1]}})
        else:
            return jsonify({"message": "Invalid credentials"}), 401
    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"message": "Server error"}), 500
    finally:
        cur.close()
        conn.close()

# Notes CRUD endpoints (protected by verify_token middleware)
@app.route('/notes', methods=['GET'])
@verify_token
def get_notes():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, title, content, created_at FROM notes WHERE tenant_id = %s ORDER BY created_at DESC", (request.user['tenant_id'],))
        notes = cur.fetchall()
        notes_list = [
            {"id": row[0], "title": row[1], "content": row[2], "created_at": row[3]} for row in notes
        ]
        return jsonify(notes_list)
    except Exception as e:
        print(f"Error fetching notes: {e}")
        return jsonify({"message": "Server error"}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/notes', methods=['POST'])
@verify_token
def create_note():
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Check plan and note limit
        cur.execute("SELECT plan FROM tenants WHERE id = %s", (request.user['tenant_id'],))
        tenant_plan = cur.fetchone()[0]

        if tenant_plan == 'Free':
            cur.execute("SELECT COUNT(*) FROM notes WHERE tenant_id = %s", (request.user['tenant_id'],))
            note_count = cur.fetchone()[0]
            if note_count >= 3:
                return jsonify({"message": "Free plan is limited to 3 notes. Please upgrade."}), 403

        note_id = str(uuid.uuid4())
        cur.execute("INSERT INTO notes (id, tenant_id, title, content) VALUES (%s, %s, %s, %s) RETURNING *",
                    (note_id, request.user['tenant_id'], title, content))
        new_note = cur.fetchone()
        conn.commit()
        return jsonify({
            "id": new_note[0],
            "title": new_note[2],
            "content": new_note[3],
            "created_at": new_note[4]
        }), 201
    except Exception as e:
        conn.rollback()
        print(f"Error creating note: {e}")
        return jsonify({"message": "Server error"}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/notes/<note_id>', methods=['GET'])
@verify_token
def get_note(note_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, title, content, created_at FROM notes WHERE id = %s AND tenant_id = %s", (note_id, request.user['tenant_id']))
        note = cur.fetchone()
        if note:
            return jsonify({"id": note[0], "title": note[1], "content": note[2], "created_at": note[3]})
        else:
            return jsonify({"message": "Note not found or you do not have permission to view it."}), 404
    except Exception as e:
        print(f"Error fetching note: {e}")
        return jsonify({"message": "Server error"}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/notes/<note_id>', methods=['PUT'])
@verify_token
def update_note(note_id):
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE notes SET title = %s, content = %s WHERE id = %s AND tenant_id = %s RETURNING *",
                    (title, content, note_id, request.user['tenant_id']))
        updated_note = cur.fetchone()
        conn.commit()
        if updated_note:
            return jsonify({"id": updated_note[0], "title": updated_note[2], "content": updated_note[3], "created_at": updated_note[4]})
        else:
            return jsonify({"message": "Note not found or you do not have permission to update it."}), 404
    except Exception as e:
        conn.rollback()
        print(f"Error updating note: {e}")
        return jsonify({"message": "Server error"}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/notes/<note_id>', methods=['DELETE'])
@verify_token
def delete_note(note_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM notes WHERE id = %s AND tenant_id = %s RETURNING *", (note_id, request.user['tenant_id']))
        deleted_note = cur.fetchone()
        conn.commit()
        if deleted_note:
            return '', 204
        else:
            return jsonify({"message": "Note not found or you do not have permission to delete it."}), 404
    except Exception as e:
        conn.rollback()
        print(f"Error deleting note: {e}")
        return jsonify({"message": "Server error"}), 500
    finally:
        cur.close()
        conn.close()

# Upgrade endpoint (Admin role required)
@app.route('/tenants/<slug>/upgrade', methods=['POST'])
@verify_token
def upgrade_tenant(slug):
    if request.user['role'] != 'Admin':
        return jsonify({"message": "Access denied: Admin role required."}), 403

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT id FROM tenants WHERE slug = %s", (slug,))
        tenant_id_from_db = cur.fetchone()

        if not tenant_id_from_db:
            return jsonify({"message": "Tenant not found."}), 404

        if request.user['tenant_id'] != tenant_id_from_db[0]:
            return jsonify({"message": "Access denied: You can only upgrade your own tenant."}), 403

        cur.execute("UPDATE tenants SET plan = 'Pro' WHERE id = %s", (tenant_id_from_db[0],))
        conn.commit()
        return jsonify({"message": f"Tenant {slug} has been upgraded to Pro."})
    except Exception as e:
        conn.rollback()
        print(f"Upgrade error: {e}")
        return jsonify({"message": "Server error"}), 500
    finally:
        cur.close()
        conn.close()