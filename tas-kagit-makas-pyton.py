import tweepy3
import sqlite3
import datetime
import re
from flask import Flask, render_template_string
from threading import Thread
import schedule
import time
import os

# Flask app for leaderboard
app = Flask(__name__)

# X API credentials (Replit environment variables)
consumer_key = os.getenv("CONSUMER_KEY")
consumer_secret = os.getenv("CONSUMER_SECRET")
access_token = os.getenv("ACCESS_TOKEN")
access_token_secret = os.getenv("ACCESS_TOKEN_SECRET")

# Tweepy setup
auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
auth.set_access_token(access_token, access_token_secret)
api = tweepy.API(auth, wait_on_rate_limit=True)

# Test Tweepy connection
try:
    user = api.verify_credentials()
    print(f"Tweepy connected successfully! Bot username: {user.screen_name}")
except Exception as e:
    print(f"Tweepy connection failed: {str(e)}")

# SQLite setup
conn = sqlite3.connect("rps_game.db", check_same_thread=False)
cursor = conn.cursor()

# Veritabanını başlat
def init_db():
    cursor.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        user_id TEXT PRIMARY KEY,
        username TEXT,
        language TEXT,
        created_at TEXT,
        tweet_count INTEGER,
        games_today INTEGER,
        last_game_date TEXT,
        no_shows INTEGER DEFAULT 0,
        banned INTEGER DEFAULT 0,
        ban_until TEXT,
        last_invited TEXT,
        games_played INTEGER DEFAULT 0,
        wins INTEGER DEFAULT 0,
        bsc_balance REAL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS games (
        game_id TEXT PRIMARY KEY,
        user1_id TEXT,
        user2_id TEXT,
        user1_choice TEXT,
        user2_choice TEXT,
        deadline TEXT,
        status TEXT,
        winner_id TEXT
    );
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    );
    INSERT OR IGNORE INTO settings (key, value) VALUES ('last_mention_id', '0');
    """)
    conn.commit()

# Pinned tweet URL
PINNED_TWEET_URL = "https://t.co/3gB7kLhXvY"  # Shortened form of https://x.com/apsnygame/status/1912182385262629239

# Game logic
CHOICES = {"taş": "rock", "kağıt": "paper", "makas": "scissors"}
WIN_MATRIX = {
    "rock": "scissors",
    "paper": "rock",
    "scissors": "paper"
}

def check_user_eligibility(user_id, username):
    """Check if user meets manipulation criteria."""
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    
    if user and user[7] >= 2:  # no_shows >= 2
        if user[8] or (user[9] and user[9] > datetime.datetime.utcnow().isoformat()):
            return False, f"2 kere katılmadın, 7 gün ban. Detay: [{PINNED_TWEET_URL}]. $BSC"
    
    try:
        x_user = api.get_user(user_id=user_id)
        created_at = datetime.datetime.strptime(x_user.created_at.strftime("%Y-%m-%d"), "%Y-%m-%d")
        age_days = (datetime.datetime.utcnow() - created_at).days
        tweet_count = x_user.statuses_count
        
        if age_days < 30 or tweet_count < 10:
            return False, f"@{username}, şartlar: hesap >1 ay, tweet >10. Detay: [{PINNED_TWEET_URL}]. $BSC"
        
        cursor.execute("SELECT games_today, last_game_date FROM users WHERE user_id=?", (user_id,))
        games_today, last_date = cursor.fetchone() or (0, None)
        today = datetime.datetime.utcnow().strftime("%Y-%m-%d")
        
        if last_date != today:
            games_today = 0
        
        if games_today >= 10:
            return False, f"@{username}, günlük 10 oyun sınırı. Yarın bekleriz! $BSC"
        
        if not user:
            cursor.execute(
                "INSERT INTO users (user_id, username, language, created_at, tweet_count, games_today, last_game_date) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (user_id, username, "en", x_user.created_at.isoformat(), tweet_count, 0, today)
            )
            conn.commit()
        
        return True, ""
    except Exception as e:
        return False, f"@{username}, hata: {str(e)}. DM @apsnygame. $BSC"

def detect_language(text, username):
    """Detect language from tweet or bio."""
    if re.search(r"[çğıöşüÇĞİÖŞÜ]", text):
        return "tr"
    try:
        user = api.get_user(screen_name=username)
        if re.search(r"[çğıöşüÇĞİÖŞÜ]", user.description):
            return "tr"
    except:
        pass
    return "en"

def create_match(user1_id, user1_name, user2_id, user2_name):
    """Create a match and post tweet."""
    game_id = f"game_{int(time.time())}"
    deadline = (datetime.datetime.utcnow() + datetime.timedelta(hours=1)).replace(
        hour=17, minute=0, second=0, microsecond=0
    ).isoformat()
    
    lang1 = cursor.execute("SELECT language FROM users WHERE user_id=?", (user1_id,)).fetchone()[0]
    lang2 = cursor.execute("SELECT language FROM users WHERE user_id=?", (user2_id,)).fetchone()[0]
    
    if lang1 == lang2 == "tr":
        tweet = (
            f"Oyun zamanı ! #taşkağıtmakas #oyun için meydan okundu! \n"
            f"@{user1_name} vs @{user2_name}!\n"
            f"@apsnygame + taş, kağıt ya da makas yaz ve 20:00 TRT’de zamanla.\n"
            f"[{PINNED_TWEET_URL}]. $BSC"
        )
    elif lang1 == lang2 == "en":
        tweet = (
            f"Play #games time! @{user1_name} vs @{user2_name}!\n"
            f"#rockpaperscissors #game challenged!\n"
            f"Tag @apsnygame + rock, paper or scissors, time your reply tweet (UTC 17:00) and send.\n"
            f"[{PINNED_TWEET_URL}]. $BSC"
        )
    else:
        tweet = (
            f"Oyun zamanı ! #taşkağıtmakas #oyun için meydan okundu! \n"
            f"@{user1_name} vs @{user2_name}!\n"
            f"@apsnygame + taş, kağıt ya da makas yaz ve 20:00 TRT’de zamanla.\n"
            f"Play #games time! #rockpaperscissors #game challenged!\n"
            f"Tag @apsnygame + rock, paper or scissors, time your reply tweet (UTC 17:00) and send.\n"
            f"[{PINNED_TWEET_URL}]. $BSC"
        )
    
    try:
        print(f"Posting match tweet: {tweet}")
        api.update_status(tweet)
        cursor.execute(
            "INSERT INTO games (game_id, user1_id, user2_id, deadline, status) "
            "VALUES (?, ?, ?, ?, ?)",
            (game_id, user1_id, user2_id, deadline, "pending")
        )
        cursor.execute(
            "UPDATE users SET games_today=games_today+1, last_game_date=? WHERE user_id IN (?, ?)",
            (datetime.datetime.utcnow().strftime("%Y-%m-%d"), user1_id, user2_id)
        )
        conn.commit()
        print(f"Match created: {game_id}")
    except Exception as e:
        print(f"Match tweet error: {str(e)}")

def process_mentions():
    """Process mentions for participation and invites."""
    try:
        last_mention_id = cursor.execute("SELECT value FROM settings WHERE key='last_mention_id'").fetchone()
        last_mention_id = last_mention_id[0] if last_mention_id else None
        print(f"Checking mentions since ID: {last_mention_id}")
        if last_mention_id is None:
            print("No last_mention_id found, checking all mentions")
        
        try:
            mentions = api.mentions_timeline(since_id=last_mention_id)
            print(f"Found {len(mentions)} new mentions")
        except Exception as e:
            print(f"Error fetching mentions: {str(e)}")
            mentions = []
        
        for mention in reversed(mentions):
            user_id = mention.user.id_str
            username = mention.user.screen_name
            text = mention.text.lower()
            print(f"Processing mention from @{username}: {text}")
            
            eligible, error = check_user_eligibility(user_id, username)
            if not eligible:
                print(f"User @{username} not eligible: {error}")
                try:
                    api.update_status(f"@{username} {error}", in_reply_to_status_id=mention.id_str)
                except Exception as e:
                    print(f"Error replying to @{username}: {str(e)}")
                continue
            
            lang = detect_language(text, username)
            cursor.execute("UPDATE users SET language=? WHERE user_id=?", (lang, user_id))
            print(f"Set language for @{username}: {lang}")
            
            if "oyun" in text or "game" in text:
                print(f"Game request detected from @{username}")
                invited = [u.screen_name for u in mention.entities["user_mentions"] if u["screen_name"] != "apsnygame"]
                if invited:
                    invited_id = api.get_user(screen_name=invited[0]).id_str
                    invited_eligible, invited_error = check_user_eligibility(invited_id, invited[0])
                    if invited_eligible:
                        print(f"Creating match: @{username} vs @{invited[0]}")
                        create_match(user_id, username, invited_id, invited[0])
                    else:
                        print(f"Invited user @{invited[0]} not eligible: {invited_error}")
                        try:
                            api.update_status(f"@{invited[0]} {invited_error}", in_reply_to_status_id=mention.id_str)
                        except Exception as e:
                            print(f"Error replying to @{invited[0]}: {str(e)}")
                else:
                    print(f"@{username} waiting for opponent")
                    cursor.execute("UPDATE users SET status='waiting' WHERE user_id=?", (user_id,))
                    cursor.execute(
                        "SELECT user_id, username FROM users WHERE status='waiting' AND user_id!=? LIMIT 1",
                        (user_id,)
                    )
                    opponent = cursor.fetchone()
                    if opponent:
                        print(f"Matched @{username} with @{opponent[1]}")
                        create_match(user_id, username, opponent[0], opponent[1])
                        cursor.execute("UPDATE users SET status='' WHERE user_id IN (?, ?)", (user_id, opponent[0]))
            
            cursor.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('last_mention_id', ?)",
                (mention.id_str,)
            )
            conn.commit()
            print(f"Updated last_mention_id to {mention.id_str}")
    except Exception as e:
        print(f"Error in process_mentions: {str(e)}")

def check_games():
    """Check games for choices and results."""
    now = datetime.datetime.utcnow().isoformat()
    cursor.execute("SELECT * FROM games WHERE status='pending' AND deadline<=?", (now,))
    games = cursor.fetchall()
    
    for game in games:
        game_id, user1_id, user2_id, _, _, deadline, _, _ = game
        user1_name = cursor.execute("SELECT username FROM users WHERE user_id=?", (user1_id,)).fetchone()[0]
        user2_name = cursor.execute("SELECT username FROM users WHERE user_id=?", (user2_id,)).fetchone()[0]
        
        start_time = datetime.datetime.fromisoformat(deadline)
        end_time = start_time + datetime.timedelta(seconds=1)
        try:
            mentions = api.mentions_timeline()
        except Exception as e:
            print(f"Error fetching mentions in check_games: {str(e)}")
            continue
        
        user1_choice = None
        user2_choice = None
        
        for mention in mentions:
            if mention.created_at.isoformat() >= start_time.isoformat() and mention.created_at.isoformat() <= end_time.isoformat():
                text = mention.text.lower()
                if mention.user.id_str == user1_id and any(c in text for c in ["taş", "kağıt", "makas", "rock", "paper", "scissors"]):
                    user1_choice = next((c for c in ["taş", "kağıt", "makas", "rock", "paper", "scissors"] if c in text), None)
                if mention.user.id_str == user2_id and any(c in text for c in ["taş", "kağıt", "makas", "rock", "paper", "scissors"]):
                    user2_choice = next((c for c in ["taş", "kağıt", "makas", "rock", "paper", "scissors"] if c in text), None)
        
        if not user1_choice and not user2_choice:
            tweet = (
                f"@{user1_name} ve @{user2_name} katılmadı! Yeni eşleşme aranıyor. $BSC"
            )
            cursor.execute("UPDATE users SET no_shows=no_shows+1 WHERE user_id IN (?, ?)", (user1_id, user2_id))
            cursor.execute("UPDATE users SET banned=1, ban_until=? WHERE user_id IN (?, ?) AND no_shows>=2",
                          ((datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat(), user1_id, user2_id))
        elif not user1_choice:
            tweet = (
                f"@{user1_name} katılmadı, @{user2_name} kazandı! Kumbara: +1 BSC. $BSC"
            )
            cursor.execute("UPDATE users SET no_shows=no_shows+1 WHERE user_id=?", (user1_id,))
            cursor.execute("UPDATE users SET banned=1, ban_until=? WHERE user_id=? AND no_shows>=2",
                          ((datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat(), user1_id))
            cursor.execute("UPDATE users SET wins=wins+1, bsc_balance=bsc_balance+1 WHERE user_id=?", (user2_id,))
            winner_id = user2_id
        elif not user2_choice:
            tweet = (
                f"@{user2_name} katılmadı, @{user1_name} kazandı! Kumbara: +1 BSC. $BSC"
            )
            cursor.execute("UPDATE users SET no_shows=no_shows+1 WHERE user_id=?", (user2_id,))
            cursor.execute("UPDATE users SET banned=1, ban_until=? WHERE user_id=? AND no_shows>=2",
                          ((datetime.datetime.utcnow() + datetime.timedelta(days=7)).isoformat(), user2_id))
            cursor.execute("UPDATE users SET wins=wins+1, bsc_balance=bsc_balance+1 WHERE user_id=?", (user1_id,))
            winner_id = user1_id
        else:
            choice1 = CHOICES.get(user1_choice, user1_choice)
            choice2 = CHOICES.get(user2_choice, user2_choice)
            
            if choice1 == choice2:
                tweet = (
                    f"@{user1_name} ({user1_choice}) vs @{user2_name} ({user2_choice}): Berabere! Kumbara: +0.5 BSC. $BSC"
                )
                cursor.execute("UPDATE users SET bsc_balance=bsc_balance+0.5 WHERE user_id IN (?, ?)", (user1_id, user2_id))
                winner_id = None
            elif WIN_MATRIX[choice1] == choice2:
                tweet = (
                    f"@{user1_name} ({user1_choice}) vs @{user2_name} ({user2_choice}): @{user1_name} kazandı! Kumbara: +1 BSC. $BSC"
                )
                cursor.execute("UPDATE users SET wins=wins+1, bsc_balance=bsc_balance+1 WHERE user_id=?", (user1_id,))
                winner_id = user1_id
            else:
                tweet = (
                    f"@{user1_name} ({user1_choice}) vs @{user2_name} ({user2_choice}): @{user2_name} kazandı! Kumbara: +1 BSC. $BSC"
                )
                cursor.execute("UPDATE users SET wins=wins+1, bsc_balance=bsc_balance+1 WHERE user_id=?", (user2_id,))
                winner_id = user2_id
        
        cursor.execute(
            "UPDATE games SET user1_choice=?, user2_choice=?, status='completed', winner_id=? WHERE game_id=?",
            (user1_choice, user2_choice, winner_id, game_id)
        )
        cursor.execute("UPDATE users SET games_played=games_played+1 WHERE user_id IN (?, ?)", (user1_id, user2_id))
        try:
            api.update_status(tweet)
            print(f"Game result tweeted: {tweet}")
        except Exception as e:
            print(f"Game result tweet error: {str(e)}")
        conn.commit()

def reset_daily_limits():
    """Reset daily game limits."""
    cursor.execute("UPDATE users SET games_today=0, last_game_date=NULL")
    conn.commit()

# Leaderboard page
@app.route("/leaderboard")
def leaderboard():
    cursor.execute("SELECT username, wins, bsc_balance FROM users ORDER BY wins DESC LIMIT 10")
    leaders = cursor.fetchall()
    html = """
    <h1>🏆 Lider Tablosu</h1>
    <table border='1'>
        <tr><th>Sıra</th><th>Kullanıcı</th><th>Galibiyet</th><th>BSC Bakiyesi</th></tr>
        {% for leader in leaders %}
        <tr><td>{{ loop.index }}</td><td>@{{ leader[0] }}</td><td>{{ leader[1] }}</td><td>{{ leader[2] }}</td></tr>
        {% endfor %}
    </table>
    <p>Güncellenme: {{ now }}</p>
    """
    return render_template_string(html, leaders=leaders, now=datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"))

def generate_weekly_report():
    """Generate weekly JSON report."""
    cursor.execute("SELECT user_id, username, games_played, wins, bsc_balance FROM users")
    users = cursor.fetchall()
    report = [
        {
            "user_id": u[0],
            "username": u[1],
            "games_played": u[2],
            "wins": u[3],
            "bsc_balance": u[4]
        } for u in users
    ]
    with open("weekly_report.json", "w") as f:
        import json
        json.dump(report, f, indent=2)

# Scheduling
schedule.every().day.at("00:00").do(reset_daily_limits)
schedule.every().monday.at("00:00").do(generate_weekly_report)
schedule.every().day.at("17:05").do(check_games)

def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(60)

# Main bot loop
def run_bot():
    Thread(target=run_schedule).start()
    while True:
        try:
            process_mentions()
            time.sleep(60)
        except Exception as e:
            print(f"Bot error: {e}")
            time.sleep(300)

if __name__ == "__main__":
    init_db()  # Veritabanını başlat
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=8080)
