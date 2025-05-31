from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
import mysql.connector
from collections import defaultdict

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')

# === DB接続関数 ===
def get_db_connection():
    try:
        return mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            port=int(os.getenv("DB_PORT")),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME")
        )
    except Exception as e:
        print("DB接続失敗:", e)
        return None

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(255) NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kakeibo (
            id INT AUTO_INCREMENT PRIMARY KEY,
            date DATE,
            category VARCHAR(255),
            amount INT,
            type VARCHAR(10),
            memo TEXT,
            user_id INT
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

# === テーブル作成 ===
@app.route('/init')
def initialize():
    init_db()
    return "Database initialized!"

# === 各ルート ===
@app.route('/')
def main():
    return f"ようこそ {session.get('username', 'ゲスト')} さん！"

# @app.route('/add', methods=['GET', 'POST'])
# def add():
#     if 'user_id' not in session:
#         return redirect('/login')

#     if request.method == 'POST':
#         date = request.form['date']
#         category = request.form['category']
#         amount = int(request.form['amount'])
#         type_ = request.form['type'].strip()
#         memo = request.form['memo']
#         user_id = session['user_id']

#         conn = get_db_connection()
#         cursor = conn.cursor()
#         cursor.execute(
#             "INSERT INTO kakeibo (date, category, amount, type, memo, user_id) VALUES (%s, %s, %s, %s, %s, %s)",
#             (date, category, amount, type_, memo, user_id)
#         )
#         conn.commit()
#         cursor.close()
#         conn.close()
#         return redirect('/add')
#     return render_template('add.html')

@app.route('/delete/<int:item_id>', methods=['POST'])
def delete(item_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM kakeibo WHERE id = %s", (item_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect('/view')

# @app.route('/view')
# def view():
#     conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)
#     user_id = session['user_id']

#     cursor.execute("SELECT * FROM kakeibo WHERE type = '収入' AND user_id = %s ORDER BY date DESC", (user_id,))
#     incomes = cursor.fetchall()
#     total_income = sum(item['amount'] for item in incomes)

#     cursor.execute("SELECT * FROM kakeibo WHERE type = '支出' AND user_id = %s ORDER BY date DESC", (user_id,))
#     expenses = cursor.fetchall()
#     total_expense = sum(item['amount'] for item in expenses)

#     necessary_categories = ['交通費']
#     necessary_expenses = [e for e in expenses if e['category'] in necessary_categories]
#     total_necessary = sum(e['amount'] for e in necessary_expenses)

#     net_income = total_income - total_necessary

#     cursor.close()
#     conn.close()

#     return render_template('view.html',
#         incomes=incomes,
#         expenses=expenses,
#         total_income=total_income,
#         total_expense=total_expense,
#         total_necessary=total_necessary,
#         net_income=net_income,
#         balance=total_income - total_expense
#     )

# @app.route('/monthly')
# def monthly():
#     user_id = session.get('user_id')
#     if not user_id:
#         return redirect('/login')

#     conn = get_db_connection()
#     cursor = conn.cursor(dictionary=True)

#     cursor.execute("""
#         SELECT
#             DATE_FORMAT(date, '%%Y-%%m') AS ym,
#             type,
#             category,
#             amount
#         FROM kakeibo
#         WHERE user_id = %s
#     """, (user_id,))
#     records = cursor.fetchall()

#     necessary_categories = ['交通費']
#     monthly_data = defaultdict(lambda: {'income': 0, 'expense': 0, 'necessary': 0, 'net_income': 0})

#     for r in records:
#         ym = r['ym']
#         if r['type'] == '収入':
#             monthly_data[ym]['income'] += r['amount']
#         elif r['type'] == '支出':
#             monthly_data[ym]['expense'] += r['amount']
#             if r['category'] in necessary_categories:
#                 monthly_data[ym]['necessary'] += r['amount']

#     for ym, data in monthly_data.items():
#         data['net_income'] = data['income'] - data['necessary']

#     sorted_months = sorted(monthly_data.items())

#     cursor.execute("""
#         SELECT
#             DATE_FORMAT(date, '%%Y-%%m') AS ym,
#             SUM(amount) AS total_expense
#         FROM kakeibo
#         WHERE type = '支出' AND user_id = %s
#         GROUP BY ym
#         ORDER BY ym ASC
#     """, (user_id,))
#     rows = cursor.fetchall()
#     labels = [row['ym'] for row in rows]
#     expenses = [row['total_expense'] for row in rows]

#     cursor.close()
#     conn.close()

#     return render_template('monthly.html',
#         monthly_data=sorted_months,
#         labels=labels,
#         expenses=expenses
#     )

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_pw = generate_password_hash(password)

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (username, hashed_pw))
            conn.commit()
        except:
            conn.rollback()
            return "ユーザー名が既に存在しています"
        finally:
            cursor.close()
            conn.close()
        return redirect('/login')
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('main'))
        else:
            return "ログインに失敗しました。ユーザー名またはパスワードが間違っています。"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

if __name__ == '__main__':
    pass
