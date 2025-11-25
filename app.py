
from flask import Flask, render_template, request, redirect, url_for, session, g, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import random
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data.db')

app = Flask(__name__)
app.secret_key = 'replace-this-with-a-secret-key'

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def init_db():
    db = get_db()
    cur = db.cursor()
    cur.executescript(open(os.path.join(BASE_DIR,'schema.sql')).read())
    db.commit()

@app.before_request
def ensure_db():
    if not hasattr(app, "_db_initialized"):
        if not os.path.exists(DB_PATH):
            print("🔧 Initializing database...")
            init_db()
            seed_data()
        app._db_initialized = True


def seed_data():
    db = get_db()
    cur = db.cursor()
    # sample questions
    questions = [
        ("What does NLP stand for?", "Natural Language Processing", "Neural Language Processing", "Networked Language Program", "Nonlinear Programming", 1),
        ("Which Python library is commonly used for web development?", "Flask", "NumPy", "Pandas", "Matplotlib", 1),
        ("What is AI short for?", "Artificial Intelligence", "Automatic Input", "Applied Internet", "Advanced Integration", 1),
        ("Which HTTP method retrieves data without side effects?", "GET", "POST", "PUT", "DELETE", 1)
    ]
    cur.executemany("INSERT INTO questions (question, opt1, opt2, opt3, opt4, answer) VALUES (?,?,?,?,?,?)", questions)
    db.commit()

@app.route('/')
def index():
    weather = None
    city = request.args.get('city')
    if city:
        try:
            # Using Open-Meteo free API (no API key)
            r = requests.get('https://api.open-meteo.com/v1/forecast', params={
                'latitude': 0, 'longitude': 0, 'hourly': 'temperature_2m'
            }, timeout=3)
            weather = r.json()
        except Exception as e:
            weather = {'error': 'Unable to fetch weather.'}
    return render_template('index.html', weather=weather)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        username = request.form['username'].strip()
        display = request.form.get('display','').strip()
        password = request.form['password']
        confirm = request.form['confirm']
        db = get_db()
        cur = db.cursor()
        if not username or not password:
            flash('Username and password required')
            return redirect(url_for('register'))
        if password != confirm:
            flash('Passwords do not match')
            return redirect(url_for('register'))
        cur.execute("SELECT id FROM users WHERE username=?", (username,))
        if cur.fetchone():
            flash('Username already taken')
            return redirect(url_for('register'))
        pwd_hash = generate_password_hash(password)
        cur.execute("INSERT INTO users (username, display, password_hash, score) VALUES (?,?,?,0)", (username, display or username, pwd_hash))
        db.commit()
        flash('Registration successful. Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        username = request.form['username'].strip()
        password = request.form['password']
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Logged in successfully.')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials')
        return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.')
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        flash('Please login to access the dashboard.')
        return redirect(url_for('login'))
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM users WHERE id=?", (session['user_id'],))
    user = cur.fetchone()
    return render_template('dashboard.html', user=user)

@app.route('/quiz/start')
def quiz_start():
    if 'user_id' not in session:
        flash('Please login to take the quiz.')
        return redirect(url_for('login'))
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id FROM questions")
    qids = [r['id'] for r in cur.fetchall()]
    random.shuffle(qids)
    session['quiz_qids'] = qids
    session['quiz_index'] = 0
    session['quiz_score'] = 0
    return redirect(url_for('quiz_question'))

@app.route('/quiz/question', methods=['GET','POST'])
def quiz_question():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    cur = db.cursor()
    if request.method=='POST':
        selected = int(request.form.get('choice',0))
        qid = session['quiz_qids'][session['quiz_index']-1]
        cur.execute("SELECT answer FROM questions WHERE id=?", (qid,))
        ans = cur.fetchone()['answer']
        if selected==ans:
            session['quiz_score'] += 1
    if session['quiz_index'] >= len(session.get('quiz_qids',[])):
        # finished
        uid = session['user_id']
        cur.execute("UPDATE users SET score = score + ? WHERE id=?", (session.get('quiz_score',0), uid))
        cur.connection.commit()
        score = session.get('quiz_score',0)
        session.pop('quiz_qids', None)
        session.pop('quiz_index', None)
        session.pop('quiz_score', None)
        return render_template('quiz_finished.html', score=score)
    # next question
    qid = session['quiz_qids'][session['quiz_index']]
    cur.execute("SELECT * FROM questions WHERE id=?", (qid,))
    q = cur.fetchone()
    session['quiz_index'] += 1
    return render_template('quiz_question.html', q=q, index=session['quiz_index'], total=len(session['quiz_qids']))

@app.route('/leaderboard')
def leaderboard():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT display, score FROM users ORDER BY score DESC LIMIT 20")
    rows = cur.fetchall()
    return render_template('leaderboard.html', rows=rows)

@app.route('/api/questions')
def api_questions():
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, question, opt1, opt2, opt3, opt4 FROM questions")
    data = [dict(r) for r in cur.fetchall()]
    return jsonify(data)

if __name__=='__main__':
    app.run(debug=True)



import requests

@app.route('/weather')
def weather():
    city = request.args.get('city','Jakarta')
    api_key = os.environ.get('WEATHER_API_KEY','YOUR_API_KEY')
    url = f"https://api.openweathermap.org/data/2.5/forecast?q={city}&units=metric&appid={api_key}"
    r = requests.get(url)
    data = {}
    try:
        j = r.json()
        items = j.get('list',[])[:3]
        out=[]
        for it in items:
            out.append({
                'dt_txt': it['dt_txt'],
                'temp': it['main']['temp'],
                'desc': it['weather'][0]['description']
            })
        data=out
    except:
        data={'error':'failed'}
    return data
