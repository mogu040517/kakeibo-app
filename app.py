from collections import defaultdict
from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
import sqlite3

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY')



# === DB接続関数 ===
def get_db_connection():
    conn = sqlite3.connect(os.getenv('DB_NAME', 'data.db'))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    with conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS kakeibo (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                category TEXT,
                amount INTEGER,
                type TEXT,
                memo TEXT,
                user_id INTEGER
            )
        ''')
    conn.close()


# === メインページ ===
@app.route('/')
def main():
    if 'user_id' not in session:
        return redirect('/login')  # 未ログインならログインページへ
    return render_template('main.html')  # ← ログイン済みなら main.html を表示

# === 支出/収入の追加 ===
@app.route('/add', methods=['GET', 'POST'])
def add():
    if 'user_id' not in session:
        return redirect('/login')
    ...

    if request.method == 'POST':
        date = request.form['date']
        category = request.form['category']
        amount = int(request.form['amount'])
        type_ = request.form['type'].strip()
        memo = request.form['memo']

        conn = get_db_connection()
        cursor = conn.cursor()
        user_id = session['user_id']
        cursor.execute(
            "INSERT INTO kakeibo (date, category, amount, type, memo, user_id) VALUES (?, ?, ?, ?, ?, ?)",
            (date, category, amount, type_, memo, user_id)
        )

        conn.commit()
        cursor.close()
        conn.close()
        return redirect('/add')
    return render_template('add.html')

# === 明細の削除 ===
@app.route('/delete/<int:item_id>', methods=['POST'])
def delete(item_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM kakeibo WHERE id = ?", (item_id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect('/view')

# === 一覧表示 ===
@app.route('/view')
def view():
    conn = get_db_connection()
    cursor = conn.cursor()
    user_id = session['user_id']
    # 収入データ取得
    cursor.execute("SELECT * FROM kakeibo WHERE type = '収入' AND user_id = ? ORDER BY date DESC", (user_id,))
    incomes = cursor.fetchall()
    total_income = sum(item['amount'] for item in incomes)

    # 支出データ取得
    cursor.execute("SELECT * FROM kakeibo WHERE type = '支出' AND user_id = ? ORDER BY date DESC", (user_id,))
    expenses = cursor.fetchall()
    total_expense = sum(item['amount'] for item in expenses)

    # 必要経費（交通費）の抽出
    necessary_categories = ['交通費']
    necessary_expenses = [e for e in expenses if e['category'] in necessary_categories]
    total_necessary = sum(e['amount'] for e in necessary_expenses)

    # 実質収入
    net_income = total_income - total_necessary

    cursor.close()
    conn.close()

    return render_template(
        'view.html',
        incomes=incomes,
        expenses=expenses,
        total_income=total_income,
        total_expense=total_expense,
        total_necessary=total_necessary,
        net_income=net_income,
        balance=total_income - total_expense
    )

# === 月別集計表示 ===
@app.route('/monthly')
def monthly():
    user_id = session.get('user_id')

    if not user_id:
        return redirect('/login')  # 未ログインならログイン画面へ

    conn = get_db_connection()
    cursor = conn.cursor()

    necessary_categories = ['交通費']

    cursor.execute("""
        SELECT
            strftime('%Y-%m', date) AS ym,
            type,
            category,
            amount
        FROM kakeibo
        WHERE user_id = ?
    """, (user_id,))
    records = cursor.fetchall()

    from collections import defaultdict
    monthly = defaultdict(lambda: {
        'income': 0,
        'expense': 0,
        'necessary': 0,
        'net_income': 0
    })

    for r in records:
        ym = r['ym']
        if r['type'] == '収入':
            monthly[ym]['income'] += r['amount']
        elif r['type'] == '支出':
            monthly[ym]['expense'] += r['amount']
            if r['category'] in necessary_categories:
                monthly[ym]['necessary'] += r['amount']

    for ym, data in monthly.items():
        data['net_income'] = data['income'] - data['necessary']

    sorted_months = sorted(monthly.items())

    #月別支出
    cursor.execute("""
        SELECT
            strftime('%Y-%m', date) AS ym,
            SUM(amount) AS total_expense
        FROM kakeibo
        WHERE type = '支出' AND user_id = ?
        GROUP BY ym
        ORDER BY ym ASC
    """, (user_id,))
    rows = cursor.fetchall()
    labels = [row['ym'] for row in rows]
    expenses = [row['total_expense'] for row in rows]

    cursor.close()
    conn.close()

    return render_template(
        'monthly.html',
        monthly_data=sorted_months,
        labels=labels,
        expenses=expenses
    )

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # パスワードをハッシュ化
        hashed_pw = generate_password_hash(password)

        # データベースに保存
        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hashed_pw)
            )
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

        # データベースから該当ユーザーを探す
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        # ユーザーが存在し、パスワードが一致すればログイン成功
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            return redirect(url_for('main'))  # メインページへ
        else:
            return "ログインに失敗しました。ユーザー名またはパスワードが間違っています。"

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()  # セッションを全削除（ログアウト）
    return redirect('/login')  # ログインページへ戻す

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
