import os
import socket
import time

import psycopg
from flask import Flask, request, redirect, render_template_string

app = Flask(__name__)

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "database"),
    "port": int(os.getenv("DB_PORT", "5432")),
    "dbname": os.getenv("DB_NAME", "walldb"),
    "user": os.getenv("DB_USER", "walluser"),
    "password": os.getenv("DB_PASSWORD", "wallpass"),
    "connect_timeout": 3,
}

HTML = """
<!DOCTYPE html>
<html lang="sv">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>The Wall | OKD Lab</title>
    <style>
        body {
            background: #0d1117;
            color: #c9d1d9;
            font-family: monospace;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
        }
        h1 { color: #58a6ff; font-size: 3rem; }
        .subtitle { color: #8b949e; }
        .box {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 8px;
            padding: 20px;
            margin: 20px 0;
        }
        input, textarea {
            box-sizing: border-box;
            width: 100%;
            background: #0d1117;
            color: white;
            border: 1px solid #30363d;
            border-radius: 5px;
            padding: 12px;
            margin-bottom: 12px;
            font: inherit;
        }
        button {
            background: #238636;
            color: white;
            border: 0;
            border-radius: 5px;
            padding: 12px 24px;
            cursor: pointer;
        }
        .message {
            border-bottom: 1px solid #30363d;
            padding: 15px 0;
            overflow-wrap: anywhere;
        }
        .message:last-child { border-bottom: none; }
        .author { color: #58a6ff; font-weight: bold; }
        .date { color: #8b949e; font-size: 0.8rem; }
        .pod { color: #3fb950; }
        .error { color: #f85149; }
    </style>
</head>
<body>
    <h1>THE WALL_</h1>
    <p class="subtitle">A distributed message board powered by OKD</p>

    <div class="box">
        <strong>System information</strong>
        <p>Pod: <span class="pod">{{ pod }}</span></p>
        <p>Database: {{ db_host }}</p>
        <p>Messages: {{ messages|length }}</p>
    </div>

    <div class="box">
        <h2>Post a message</h2>
        <form method="POST" action="/post">
            <input name="author" placeholder="Your name"
                   maxlength="50" required>
            <textarea name="message" placeholder="What's on your mind?"
                      maxlength="500" required></textarea>
            <button type="submit">POST MESSAGE</button>
        </form>
    </div>

    <div class="box">
        <h2>Messages</h2>
        {% for message in messages %}
        <div class="message">
            <span class="author">{{ message[1] }}</span>
            <span class="date">{{ message[3] }}</span>
            <p>{{ message[2] }}</p>
        </div>
        {% else %}
        <p>No messages yet. Be the first!</p>
        {% endfor %}
    </div>
</body>
</html>
"""


def connect():
    return psycopg.connect(**DB_CONFIG)


def init_db():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id SERIAL PRIMARY KEY,
                    author VARCHAR(50) NOT NULL,
                    message TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)


@app.route("/")
def index():
    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT id, author, message, created_at
                    FROM messages
                    ORDER BY id DESC
                    LIMIT 100
                """)
                messages = cur.fetchall()

        return render_template_string(
            HTML,
            messages=messages,
            pod=socket.gethostname(),
            db_host=DB_CONFIG["host"],
        )
    except psycopg.Error:
        app.logger.exception("Database connection failed")
        return "Database unavailable. Check application logs.", 503


@app.route("/post", methods=["POST"])
def post():
    author = request.form.get("author", "").strip()[:50]
    message = request.form.get("message", "").strip()[:500]

    if not author or not message:
        return "Author and message are required", 400

    try:
        with connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO messages (author, message) VALUES (%s, %s)",
                    (author, message),
                )
    except psycopg.Error:
        app.logger.exception("Could not save message")
        return "Database unavailable", 503

    return redirect("/")


@app.route("/health")
def health():
    return {"status": "ok", "pod": socket.gethostname()}


def initialize():
    for attempt in range(30):
        try:
            init_db()
            print("Database initialized", flush=True)
            return
        except psycopg.Error as exc:
            print(f"Waiting for database ({attempt + 1}/30): {exc}",
                  flush=True)
            time.sleep(2)

    raise RuntimeError("Database could not be initialized")


if __name__ == "__main__":
    initialize()
    app.run(host="0.0.0.0", port=8080)
