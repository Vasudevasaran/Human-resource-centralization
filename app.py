from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = '27'  # Change this to a secure secret key

def get_db_connection():
    conn = sqlite3.connect('employee_database.db')
    conn.row_factory = sqlite3.Row
    return conn

def create_tables():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            contact TEXT NOT NULL,
            emergency_contact TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS AttendanceRecord (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_email TEXT NOT NULL,
            checkin_time DATETIME,
            checkout_time DATETIME,
            leave_start_time DATETIME,
            leave_reason TEXT DEFAULT NULL,
            FOREIGN KEY (user_email) REFERENCES users(email)
        )
    ''')
    conn.commit()
    conn.close()

def register_user(name, email, password, contact, emergency_contact):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')

        cursor.execute('''
            INSERT INTO users (name, email, password, contact, emergency_contact)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, email, hashed_password, contact, emergency_contact))

        conn.commit()
        flash('Registration successful!', 'success')
    except sqlite3.IntegrityError:
        flash('Email address already exists. Please use a different email.', 'danger')
    finally:
        conn.close()

def login_user(email, password):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    user = cursor.fetchone()

    conn.close()

    if user and check_password_hash(user['password'], password):
        return True
    else:
        return False

def get_user_email():
    return session.get('user_email')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['POST'])
def register():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        contact = request.form['contact']
        emergency_contact = request.form['emergency_contact']

        # Check if password and confirm password match
        if password != confirm_password:
            flash('Passwords do not match. Please try again.', 'danger')
            return redirect(url_for('index'))

        # Register the user
        register_user(name, email, password, contact, emergency_contact)

        return redirect(url_for('index'))

@app.route('/login', methods=['POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if login_user(email, password):
            session['user_email'] = email  # Store user email in session
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')
            return redirect(url_for('index'))

@app.route('/dashboard')  
def dashboard():
    user_email = get_user_email()

    if user_email:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM AttendanceRecord WHERE user_email = ? ORDER BY checkin_time DESC', (user_email,))
        records = cursor.fetchall()
        conn.close()
        return render_template('dashboard.html', attendance_records=records)
    else:
        flash('You need to login to access the dashboard.', 'danger')
        return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.pop('user_email', None)  # Remove user email from session
    flash('Logged out successfully!', 'success')
    return redirect(url_for('index'))

@app.route('/apply_leave', methods=['POST'])
def apply_leave():
    leave_reason = request.json.get('reason')  # Extract leave reason from the JSON data
    user_email = get_user_email()

    if user_email:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Create a new entry for leave application
            leave_start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            cursor.execute('INSERT INTO AttendanceRecord (user_email, leave_start_time, leave_reason) VALUES (?, ?, ?)',
                           (user_email, leave_start_time, leave_reason))
            conn.commit()
            conn.close()
            return jsonify({'message': 'Leave application submitted successfully'})
        except Exception as e:
            return jsonify({'message': f'Error: {e}'})
    else:
        return jsonify({'message': 'User not authenticated'})

@app.route('/toggle_check', methods=['POST'])
def toggle_check():
    user_email = get_user_email()

    if user_email:
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Check if there's an open entry (check-in) for the current day
            cursor.execute('SELECT * FROM AttendanceRecord WHERE date(checkin_time) = date("now") AND checkout_time IS NULL AND user_email = ?',
                           (user_email,))
            existing_checkin = cursor.fetchone()

            if existing_checkin:
                # If there's an open entry, it means the user is already checked in, so we'll perform a check-out
                checkout_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('UPDATE AttendanceRecord SET checkout_time=? WHERE id=?',
                               (checkout_time, existing_checkin['id']))
                conn.commit()
                conn.close()
                return jsonify({'message': 'Check-out successful'})
            else:
                # If no open entry found, it means the user is not checked in, so we'll perform a check-in
                cursor.execute('SELECT * FROM AttendanceRecord WHERE date(checkin_time) = date("now") AND checkout_time IS NOT NULL AND user_email = ?',
                               (user_email,))
                existing_checkout = cursor.fetchone()

                if existing_checkout:
                    # User has already checked out today
                    conn.close()
                    return jsonify({'message': 'You have already checked out for today. Cannot check in again.'})
                else:
                    # User has not checked in or checked out today, perform check-in
                    checkin_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('INSERT INTO AttendanceRecord (user_email, checkin_time) VALUES (?, ?)',
                                   (user_email, checkin_time))
                    conn.commit()
                    conn.close()
                    return jsonify({'message': 'Check-in successful'})
        except Exception as e:
            return jsonify({'message': f'Error: {e}'})
    else:
        return jsonify({'message': 'User not authenticated'})




if __name__ == '__main__':
    create_tables()
    app.run(debug=True)
