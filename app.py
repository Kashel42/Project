from flask import Flask, render_template, request, session, redirect, url_for, flash
import sqlite3
import os

app = Flask(__name__)
app.secret_key = 'simple_secret_key_123'
DATABASE = 'habits.db'


# Инициализация базы данных (ТОЛЬКО ПРИ ПЕРВОМ ЗАПУСКЕ)
def init_db():
    # Проверяем, существует ли уже база данных
    if os.path.exists(DATABASE):
        print("База данных уже существует, пропускаем создание...")
        return

    print("Создаем новую базу данных...")
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Таблица пользователей
    c.execute('''
        CREATE TABLE users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL
        )
    ''')

    # Таблица привычек
    c.execute('''
        CREATE TABLE habits (
            id INTEGER PRIMARY KEY,
            username TEXT,
            name TEXT NOT NULL,
            created_date TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (username) REFERENCES users(username)
        )
    ''')

    # Таблица выполнения
    c.execute('''
        CREATE TABLE habit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            habit_id INTEGER,
            username TEXT,
            log_date TEXT DEFAULT CURRENT_DATE,
            completed INTEGER DEFAULT 0,
            FOREIGN KEY (habit_id) REFERENCES habits(id),
            FOREIGN KEY (username) REFERENCES users(username)
        )
    ''')

    conn.commit()
    conn.close()
    print("База данных создана успешно!")


# Проверка пользователя
def check_user(username, password):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", (username, password))
    user = c.fetchone()
    conn.close()
    return user


# Регистрация пользователя
def register_user(username, password):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False


# Добавление привычки
def add_habit(username, habit_name):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("INSERT INTO habits (username, name) VALUES (?, ?)", (username, habit_name))
    conn.commit()
    conn.close()


# Получение привычек пользователя
def get_user_habits(username):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute('''
        SELECT h.id, h.name, h.created_date, 
               COALESCE(hl.completed, 0) as completed
        FROM habits h
        LEFT JOIN habit_logs hl ON h.id = hl.habit_id AND hl.log_date = date('now')
        WHERE h.username = ?
        ORDER BY h.created_date DESC
    ''', (username,))

    habits = c.fetchall()
    conn.close()

    result = []
    for habit in habits:
        result.append({
            'id': habit[0],
            'name': habit[1],
            'date': habit[2],
            'completed': bool(habit[3])
        })
    return result


# Переключение статуса привычки
def toggle_habit_status(habit_id, username):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    # Проверяем текущий статус
    c.execute('''
        SELECT completed FROM habit_logs 
        WHERE habit_id = ? AND log_date = date('now') AND username = ?
    ''', (habit_id, username))

    current = c.fetchone()

    if current:
        new_status = 0 if current[0] else 1
        c.execute('''
            UPDATE habit_logs SET completed = ? 
            WHERE habit_id = ? AND log_date = date('now') AND username = ?
        ''', (new_status, habit_id, username))
    else:
        c.execute('''
            INSERT INTO habit_logs (habit_id, username, completed) 
            VALUES (?, ?, ?)
        ''', (habit_id, username, 1))

    conn.commit()
    conn.close()


# Удаление привычки
def delete_habit(habit_id, username):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()
    c.execute("DELETE FROM habits WHERE id = ? AND username = ?", (habit_id, username))
    conn.commit()
    conn.close()


# Статистика
def get_stats(username):
    conn = sqlite3.connect(DATABASE)
    c = conn.cursor()

    c.execute('''
        SELECT COUNT(*) as total, 
               SUM(CASE WHEN hl.completed = 1 THEN 1 ELSE 0 END) as completed
        FROM habits h
        LEFT JOIN habit_logs hl ON h.id = hl.habit_id AND hl.log_date = date('now')
        WHERE h.username = ?
    ''', (username,))

    result = c.fetchone()
    conn.close()

    return {
        'total': result[0] if result else 0,
        'completed': result[1] if result and result[1] else 0
    }


# Маршруты
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('profile'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = check_user(username, password)
        if user:
            session['username'] = username
            flash('Вход выполнен!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Неверный логин или пароль', 'error')

    return render_template('login.html')


@app.route('/registration', methods=['GET', 'POST'])
def registration():
    if 'username' in session:
        return redirect(url_for('profile'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm = request.form['confirm_password']

        if not username or not password:
            flash('Заполните все поля', 'error')
        elif password != confirm:
            flash('Пароли не совпадают', 'error')
        elif len(password) < 4:
            flash('Пароль должен быть не менее 4 символов', 'error')
        else:
            if register_user(username, password):
                flash('Регистрация успешна! Теперь войдите.', 'success')
                return redirect(url_for('login'))
            else:
                flash('Это имя пользователя уже занято', 'error')

    return render_template('registration.html')


@app.route('/profile')
def profile():
    if 'username' not in session:
        return redirect(url_for('login'))

    habits = get_user_habits(session['username'])
    stats = get_stats(session['username'])

    return render_template('profile.html',
                           username=session['username'],
                           habits=habits,
                           stats=stats)


@app.route('/add_habit', methods=['POST'])
def add_habit_route():
    if 'username' not in session:
        return redirect(url_for('login'))

    habit_name = request.form['name']
    if habit_name.strip():
        add_habit(session['username'], habit_name.strip())
        flash('Привычка добавлена!', 'success')

    return redirect(url_for('profile'))


@app.route('/toggle/<int:habit_id>')
def toggle_habit(habit_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    toggle_habit_status(habit_id, session['username'])
    flash('Статус обновлен!', 'success')
    return redirect(url_for('profile'))


@app.route('/delete/<int:habit_id>')
def delete_habit_route(habit_id):
    if 'username' not in session:
        return redirect(url_for('login'))

    delete_habit(habit_id, session['username'])
    flash('Привычка удалена!', 'info')
    return redirect(url_for('profile'))


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы', 'info')
    return redirect(url_for('index'))


# Инициализация при запуске (БЕЗ УДАЛЕНИЯ СУЩЕСТВУЮЩЕЙ БАЗЫ)
if __name__ == '__main__':
    init_db()  # Создает базу только если её нет
    app.run(debug=True, port=5000)