import os
from flask import Flask, render_template_string, request, redirect, url_for
import requests
import time
import random
import logging
import threading

app = Flask(__name__)

# Set up logging
logging.basicConfig(filename="errors.log", level=logging.ERROR, format="%(asctime)s - %(levelname)s - %(message)s")

# Global variables to store user input
USERNAME = ""
PASSWORD = ""
THREAD_ID = ""
NICKNAMES = []
RUNNING = False

# Instagram API Endpoints
LOGIN_URL = "https://www.instagram.com/api/v1/accounts/login/"
NICKNAME_CHANGE_URL = "https://i.instagram.com/api/v1/direct_v2/threads/{thread_id}/update_title/"

# Headers (Mimics Instagram Mobile API)
HEADERS = {
    "User-Agent": "Instagram 284.0.0.0.63 Android",
    "X-CSRFToken": "missing",
    "Content-Type": "application/x-www-form-urlencoded",
}

# Session Object to Maintain Authentication
session = requests.Session()

def log_error(message):
    """Logs errors to a file and prints to console."""
    logging.error(message)
    print(f"[-] {message}")

def login(max_retries=3):
    """Logs in to Instagram and saves session cookies, with retries on failure."""
    global session, USERNAME, PASSWORD

    for attempt in range(max_retries):
        print(f"[!] Attempt {attempt + 1} of {max_retries} to log in...")

        # First request to get CSRF token
        response = session.get("https://www.instagram.com/accounts/login/", headers=HEADERS)
        csrf_token = response.cookies.get("csrftoken")

        if not csrf_token:
            log_error("Failed to fetch CSRF token. Retrying...")
            time.sleep(random.uniform(2, 5))  # Random delay before retry
            continue

        HEADERS["X-CSRFToken"] = csrf_token  # Update CSRF token in headers

        # Login Data
        login_data = {
            "username": USERNAME,
            "password": PASSWORD,
            "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{int(time.time())}:{PASSWORD}",
            "queryParams": "{}",
            "optIntoOneTap": "false"
        }

        # Perform Login
        response = session.post(LOGIN_URL, data=login_data, headers=HEADERS)

        # Check if login was successful
        if response.status_code == 200 and '"authenticated": true' in response.text:
            print("[+] Logged in successfully!")
            return session.cookies.get_dict()
        
        # Account locked or challenge required
        elif "checkpoint_required" in response.text:
            log_error("Instagram requires verification! Complete it manually and try again.")
            return None
        
        # Temporary ban or rate limiting
        elif "Please wait a few minutes before you try again" in response.text:
            log_error("Rate limit exceeded! Retrying in 60 seconds...")
            time.sleep(60)
            continue

        else:
            log_error(f"Login failed: {response.text}")

        time.sleep(random.uniform(2, 5))  # Wait before retry

    log_error("Login failed after multiple attempts. Exiting...")
    return None

def change_nickname(session_cookies, new_nickname):
    """Changes your nickname in the Instagram group chat."""
    global session, THREAD_ID

    # Attach authenticated cookies
    session.cookies.update(session_cookies)

    # Data Payload
    data = {
        "title": new_nickname
    }

    # Send Request
    response = session.post(NICKNAME_CHANGE_URL.format(thread_id=THREAD_ID), headers=HEADERS, data=data)

    if response.status_code == 200:
        print(f"[+] Nickname successfully changed to: {new_nickname}")
    else:
        log_error(f"Failed to change nickname! Response: {response.text}")

def schedule_nickname_changes(session_cookies, delay=300):
    """Rotates through nicknames every X seconds."""
    global NICKNAMES, RUNNING

    while RUNNING:
        new_nickname = random.choice(NICKNAMES)  # Pick a random nickname
        print(f"[!] Changing nickname to: {new_nickname}")
        change_nickname(session_cookies, new_nickname)
        
        print(f"[💤] Waiting {delay} seconds before next change...")
        time.sleep(delay)

# HTML Template
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Instagram Nickname Changer</title>
</head>
<body>
    <h1>Instagram Nickname Changer</h1>
    <form method="POST">
        <label for="username">Username:</label>
        <input type="text" id="username" name="username" required><br><br>
        
        <label for="password">Password:</label>
        <input type="password" id="password" name="password" required><br><br>
        
        <label for="thread_id">Thread ID:</label>
        <input type="text" id="thread_id" name="thread_id" required><br><br>
        
        <label for="nicknames">Nicknames (comma-separated):</label>
        <input type="text" id="nicknames" name="nicknames" required><br><br>
        
        <button type="submit">Start</button>
    </form>
</body>
</html>
"""

STATUS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Status</title>
</head>
<body>
    <h1>Nickname Changer Status</h1>
    <p>Nickname changer is currently: <strong>{{ "Running" if running else "Stopped" }}</strong></p>
    <form action="/stop" method="POST">
        <button type="submit">Stop</button>
    </form>
    <a href="/">Go Back</a>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    global USERNAME, PASSWORD, THREAD_ID, NICKNAMES, RUNNING

    if request.method == "POST":
        USERNAME = request.form.get("username")
        PASSWORD = request.form.get("password")
        THREAD_ID = request.form.get("thread_id")
        NICKNAMES = request.form.get("nicknames").split(",")

        # Start the nickname changer in a separate thread
        session_cookies = login()
        if session_cookies:
            RUNNING = True
            threading.Thread(target=schedule_nickname_changes, args=(session_cookies, 600)).start()
            return redirect(url_for("status"))

    return render_template_string(HTML)

@app.route("/status")
def status():
    global RUNNING
    return render_template_string(STATUS_HTML, running=RUNNING)

@app.route("/stop", methods=["POST"])
def stop():
    global RUNNING
    RUNNING = False
    return redirect(url_for("index"))

if __name__ == "__main__":
    # Use the PORT environment variable if available (for Heroku), otherwise default to 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
    app.run(debug=True)
