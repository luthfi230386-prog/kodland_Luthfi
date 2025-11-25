# Quiz Project (Flask)

This project is a simple Flask-based quiz site implementing:
- Register/login (unique username)
- Quiz with randomized questions and scoring
- Leaderboard stored in SQLite
- Simple weather widget example (uses Open-Meteo)

To run:
1. Create a virtualenv and `pip install flask requests werkzeug`
2. `python app.py`
3. Visit http://127.0.0.1:5000

Note: replace `app.secret_key` with a secure random value before deploying.
