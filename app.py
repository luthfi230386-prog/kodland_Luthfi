from flask import Flask, render_template, request, redirect, url_for, session, g, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import sqlite3
import os
import random
import requests
from datetime import datetime
import calendar
import copy

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data.db')

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "default-secret")

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db:
        db.close()

def init_db():
    db = get_db()
    schema_path = os.path.join(BASE_DIR, 'schema.sql')
    with open(schema_path, "r", encoding="utf-8") as f:
        db.executescript(f.read())
    db.commit()

def seed_data():
    db = get_db()
    cur = db.cursor()

    questions = [
        ("What does NLP stand for?",
         "Natural Language Processing", "Neural Language Processing", "Networked Language Program", "Nonlinear Programming", 1),

        ("Which Python library is commonly used for web development?",
         "Flask", "NumPy", "Pandas", "Matplotlib", 1),

        ("What is AI short for?",
         "Artificial Intelligence", "Automatic Input", "Applied Internet", "Advanced Integration", 1),

        ("Which HTTP method retrieves data without side effects?",
         "GET", "POST", "PUT", "DELETE", 1),

        ("Which data structure uses LIFO?",
         "Stack", "Queue", "Dictionary", "Tuple", 1),

        ("Which of the following is a NoSQL database?",
         "MongoDB", "MySQL", "PostgreSQL", "SQLite", 1),

        ("What does CSS stand for?",
         "Cascading Style Sheets", "Computer Style System", "Central Style Setup", "Coding Style Sheet", 1),

        ("Which Python keyword is used to define a function?",
         "def", "fun", "function", "make", 1),

        ("Which of these is a frontend JavaScript framework?",
         "React", "Django", "Laravel", "Flask", 1),

        ("What does SQL stand for?",
         "Structured Query Language", "System Query Logic", "Sequential Query List", "Scripted Query Link", 1)
    ]

    cur.executemany(
        "INSERT INTO questions (question, opt1, opt2, opt3, opt4, answer) VALUES (?,?,?,?,?,?)",
        questions
    )
    db.commit()


with app.app_context():
    if not os.path.exists(DB_PATH):
        init_db()
        seed_data()

def get_weather_3day(city):
    api_key = os.getenv("WEATHER_API_KEY", "")
    if not api_key:
        return {"error": "Weather API key missing"}

    try:
        url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&units=metric&appid={api_key}"
        r = requests.get(url, timeout=4)
        data = r.json()

        if data.get("cod") != "200":
            return {"error": data.get("message", "API error")}

        timezone_offset = data.get("city", {}).get("timezone", 0)

        three_days = []
        used_dates = set()

        for item in data["list"]:
            dt = datetime.strptime(item["dt_txt"], "%Y-%m-%d %H:%M:%S")
            date_str = dt.strftime("%Y-%m-%d")

            if dt.hour == 12 and date_str not in used_dates:
                day_name = calendar.day_name[dt.weekday()]
                temp_day = item["main"]["temp"]
                desc = item["weather"][0]["description"]

                temp_night = temp_day
                for night_item in data["list"]:
                    dt2 = datetime.strptime(night_item["dt_txt"], "%Y-%m-%d %H:%M:%S")
                    if dt2.date() == dt.date() and dt2.hour == 0:
                        temp_night = night_item["main"]["temp"]
                        break

                three_days.append({
                    "date": date_str,
                    "day_name": day_name,
                    "temp_day": temp_day,
                    "temp_night": temp_night,
                    "desc": desc
                })

                used_dates.add(date_str)
                if len(three_days) == 3:
                    break

        return {
            "city": city,
            "days": three_days,
            "time_offset": timezone_offset
        }

    except:
        return {"error": "Unable to fetch 3-day weather."}


@app.route('/')
def index():
    city = request.args.get("city", "Jakarta")
    weather_3day = get_weather_3day(city)
    return render_template("index.html", weather_3day=weather_3day)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        username = request.form['username'].strip()
        display = request.form.get('display', '').strip()
        password = request.form['password']
        confirm = request.form['confirm']

        db = get_db()
        cur = db.cursor()

        if not username or not password:
            flash("Username and password are required")
            return redirect(url_for("register"))

        if password != confirm:
            flash("Passwords do not match")
            return redirect(url_for("register"))

        cur.execute("SELECT id FROM users WHERE username=?", (username,))
        if cur.fetchone():
            flash("Username already taken")
            return redirect(url_for("register"))

        pwd_hash = generate_password_hash(password)
        cur.execute("INSERT INTO users (username, display, password_hash, score) VALUES (?,?,?,0)",
                    (username, display or username, pwd_hash))
        db.commit()

        flash("Registration successful. Please login.")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        username = request.form['username'].strip()
        password = request.form['password']

        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            flash("Logged in successfully.")
            return redirect(url_for("dashboard"))

        flash("Invalid credentials")
        return redirect(url_for("login"))

    return render_template("login.html")


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out.")
    return redirect(url_for("index"))


@app.route('/dashboard')
def dashboard():
    if "user_id" not in session:
        flash("Please login first.")
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    user = cur.fetchone()

    return render_template("dashboard.html", user=user)


@app.route('/quiz/start')
def quiz_start():
    if "user_id" not in session:
        flash("Please login.")
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM questions")
    qids = [r["id"] for r in cur.fetchall()]
    random.shuffle(qids)

    session["quiz_qids"] = qids
    session["quiz_index"] = 0
    session["quiz_score"] = 0

    return redirect(url_for("quiz_question"))


@app.route('/quiz/question', methods=['GET', 'POST'])
def quiz_question():
    if "user_id" not in session:
        return redirect(url_for("login"))

    db = get_db()
    cur = db.cursor()

    # Submit jawaban
    if request.method == "POST":
        selected = int(request.form.get("choice", -1))
        if selected == session.get("current_answer", -1):
            session["quiz_score"] += 1

    # Cek selesai
    if session["quiz_index"] >= len(session["quiz_qids"]):
        score = session["quiz_score"]
        uid = session["user_id"]

        cur.execute("UPDATE users SET score = score + ? WHERE id=?", (score, uid))
        db.commit()

        session.clear()
        return render_template("quiz_finished.html", score=score)

    # Ambil pertanyaan selanjutnya
    qid = session["quiz_qids"][session["quiz_index"]]
    cur.execute("SELECT * FROM questions WHERE id=?", (qid,))
    q = cur.fetchone()

    # Buat list opsi dan acak
    options = [q["opt1"], q["opt2"], q["opt3"], q["opt4"]]
    correct_index = q["answer"] - 1  # 0-based
    options_shuffled = copy.deepcopy(options)
    random.shuffle(options_shuffled)
    new_correct_index = options_shuffled.index(options[correct_index])

    # Simpan jawaban yang benar di session
    session["current_answer"] = new_correct_index
    session["quiz_index"] += 1

    return render_template(
        "quiz_question.html",
        q=q,
        options=options_shuffled,
        index=session["quiz_index"],
        total=len(session["quiz_qids"])
    )


@app.route('/leaderboard')
def leaderboard():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT display, score FROM users ORDER BY score DESC LIMIT 20")
    rows = cur.fetchall()
    return render_template("leaderboard.html", rows=rows)


@app.route('/weather')
def weather_api():
    city = request.args.get("city", "Jakarta")
    result = get_weather_3day(city)
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
