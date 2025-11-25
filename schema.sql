
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS questions;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    display TEXT,
    password_hash TEXT NOT NULL,
    score INTEGER DEFAULT 0
);

CREATE TABLE questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    opt1 TEXT,
    opt2 TEXT,
    opt3 TEXT,
    opt4 TEXT,
    answer INTEGER -- 1..4
);
