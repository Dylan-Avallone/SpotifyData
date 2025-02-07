from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
from flask_session import Session
import os
import time  
import spotipy
import dotenv
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")  # Prevents GUI errors
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from spotipy.oauth2 import SpotifyOAuth
from flask_cors import CORS
import sqlite3
import textwrap
import openai
import re
dotenv.load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")

#Fonts
poppins_path = "fonts/Poppins-Regular.ttf"
poppins_font = fm.FontProperties(fname=poppins_path)
# Flask App Setup
app = Flask(__name__)
CORS(app)

app.secret_key = os.urandom(24)  # Required for session
app.config["SESSION_PERMANENT"] = True  
app.config["SESSION_TYPE"] = "filesystem"  # 🔥 Store session data properly
app.config["SESSION_FILE_DIR"] = "/tmp/flask_session/"  # 🔥 Store it somewhere real
app.config["SESSION_USE_SIGNER"] = True
Session(app)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Spotify API Setup
CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

sp_oauth = SpotifyOAuth(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_uri=REDIRECT_URI,
    scope="user-top-read user-read-recently-played"

)

music_data = None 
genre_cache = {}


# 🌎 Home Route
@app.route('/')
def index():
    return render_template('index.html')

# 📤 Upload CSV File
@app.route('/upload', methods=['POST'])
def upload_file():
    global music_data
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})

    filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)

    try:
        music_data = pd.read_csv(filepath)
        return jsonify({'message': '✅ File uploaded successfully!', 'columns': music_data.columns.tolist()})
    except Exception as e:
        return jsonify({'error': str(e)})

# 📊 Get Summary Stats
@app.route('/summary', methods=['GET'])
def summary():
    global music_data
    if music_data is None:
        return jsonify({'error': '⚠️ No data uploaded'})

    summary_stats = {
        'Total Songs': len(music_data),
        'Unique Artists': music_data['artist'].nunique() if 'artist' in music_data.columns else 'N/A',
        'Avg Duration (min)': round(music_data['duration_ms'].mean() / 60000, 2) if 'duration_ms' in music_data.columns else 'N/A'
    }
    return jsonify(summary_stats)




def get_genre(artist_name):
    """Fetches the genre of an artist using GPT-4o-mini if Spotify provides no genre."""
    if artist_name in genre_cache:
        return genre_cache[artist_name]  # ✅ Use cached value

    print(f"⚠️ {artist_name} - No genres found on Spotify. Fetching from OpenAI...")

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",  # ✅ Uses GPT-4o-mini for cost efficiency
            messages=[{"role": "user", "content": f"Provide only the primary genre of {artist_name} in one word."}],
            max_tokens=3,  # ✅ Further limits response length
            temperature=0  # ✅ Ensures deterministic output
        )

        raw_genre = response["choices"][0]["message"]["content"].strip()

        # 🔥 Extract only the first valid genre-like word
        genre_match = re.search(r"\b([A-Za-z-]+)\b", raw_genre)
        genre = genre_match.group(1) if genre_match else "Unknown"

        print(f"🎨 AI-Fetched Genre for {artist_name}: {genre}")

    except Exception as e:
        print(f"❌ ERROR: Failed to fetch genre for {artist_name} - {e}")
        genre = "Unknown"

    genre_cache[artist_name] = genre  # ✅ Save to cache
    return genre

@app.route('/update-data', methods=['GET'])
def update_data():
    """Fetches and updates the user's latest listening history and genres before visualizing data."""
    try:
        print("🔄 Updating user data...")
        
        # Step 1: Fetch latest Spotify listening history
        spotify_listening_history()
        
        # Step 2: Update missing genres using Spotify API or GPT-4o-mini
        update_missing_genres()
        
        print("✅ Data update complete.")
        return jsonify({"message": "✅ Data update complete."})
    except Exception as e:
        print(f"❌ ERROR: Data update failed - {e}")
        return jsonify({"error": "Data update failed", "details": str(e)})


def update_existing_unknown_genres():
    """Finds and updates all 'Unknown' genres in the database using GPT-4o-mini."""
    conn = sqlite3.connect("spotify_data.db")
    cursor = conn.cursor()

    # Find all artists with 'Unknown' genre
    cursor.execute("SELECT DISTINCT artist FROM listening_history WHERE genre = 'Unknown'")
    unknown_artists = cursor.fetchall()

    if not unknown_artists:
        print("✅ No 'Unknown' genres to update.")
        conn.close()
        return

    print(f"🔄 Updating {len(unknown_artists)} 'Unknown' genres...")

    updated = 0
    for artist_tuple in unknown_artists:
        artist_name = artist_tuple[0]
        new_genre = get_genre(artist_name)  # 🔥 Fetch new genre

        if new_genre and new_genre != "Unknown":
            cursor.execute("UPDATE listening_history SET genre = ? WHERE artist = ?", (new_genre, artist_name))
            conn.commit()
            print(f"✅ Updated {artist_name} -> {new_genre}")
            updated += 1

    conn.close()
    print(f"✅ Finished updating {updated} 'Unknown' genres.")

# Call this function **after** fetching the listening history
update_existing_unknown_genres()



def reset_invalid_genres():
    """Finds and resets invalid genres in the database."""
    conn = sqlite3.connect("spotify_data.db")
    cursor = conn.cursor()

    # Find all genres currently stored
    cursor.execute("SELECT DISTINCT artist, genre FROM listening_history")
    all_genres = cursor.fetchall()

    invalid_genres = []
    for artist, genre in all_genres:
        # ✅ If genre contains full sentences, artist names, or phrases, it's invalid
        if len(genre.split()) > 3 or not re.match(r"^[a-zA-Z\s-]+$", genre):
            invalid_genres.append((artist, genre))

        # ✅ Check for artist mentions in genre (e.g., "Chase Shakur is known for R&B")
        if artist.lower() in genre.lower():
            invalid_genres.append((artist, genre))

    print(f"🚨 Found {len(invalid_genres)} invalid genres.")

    # Reset all invalid genres to 'Unknown'
    for artist, genre in invalid_genres:
        cursor.execute("UPDATE listening_history SET genre = 'Unknown' WHERE artist = ?", (artist,))
        print(f"🛑 Reset genre for {artist} -> 'Unknown' (Was: {genre})")

    conn.commit()
    conn.close()

    print("✅ Reset complete. Re-fetching genres now...")
    update_existing_unknown_genres()  # 🔥 Re-run OpenAI genre fetching

# Run this again to ensure full cleanup
reset_invalid_genres()








def update_missing_genres():
    """Finds songs with missing genres and updates them using Spotify API or GPT-4o-mini."""
    conn = sqlite3.connect("spotify_data.db")
    cursor = conn.cursor()

    # Fetch all artists without a genre
    cursor.execute("SELECT DISTINCT artist FROM listening_history WHERE genre IS NULL OR genre = 'Unknown'")
    missing_artists = cursor.fetchall()

    conn.close()

    if not missing_artists:
        print("✅ No missing genres to update.")
        return

    print(f"🔄 Updating {len(missing_artists)} artists with missing genres...")

    token = get_token()
    if not token:
        print("❌ ERROR: Spotify token is missing. Cannot fetch genres.")
        return

    sp = spotipy.Spotify(auth=token)

    updated = 0
    for artist_tuple in missing_artists:
        artist_name = artist_tuple[0]
        genre = "Unknown"

        try:
            # 🔍 Fetch artist details from Spotify
            results = sp.search(q=artist_name, type="artist", limit=1)
            if "artists" in results and results["artists"]["items"]:
                artist_data = results["artists"]["items"][0]
                genres = artist_data.get("genres", [])

                # ✅ Use first genre from Spotify if available
                genre = genres[0] if genres else "Unknown"

        except Exception as e:
            print(f"⚠️ ERROR: Could not fetch Spotify genre for {artist_name}: {e}")

        # 🔥 If still "Unknown", use GPT-4o-mini
        if genre == "Unknown":
            genre = get_genre(artist_name)

        # ✅ Update database with final genre
        conn = sqlite3.connect("spotify_data.db")
        cursor = conn.cursor()
        cursor.execute("UPDATE listening_history SET genre = ? WHERE artist = ?", (genre, artist_name))
        conn.commit()
        conn.close()

        print(f"✅ Final Genre for {artist_name}: {genre}")
        updated += 1

    print(f"✅ Genre update complete! Updated {updated} artists.")







# 📈 Generate Static Chart
@app.route('/visualize', methods=['GET'])
def visualize():
    global music_data
    if music_data is None or music_data.empty:
        return jsonify({'error': '⚠️ No data available to generate a chart'})

    plt.figure(figsize=(10, 5))
    top_artists = music_data['artist'].value_counts().head(10)
    top_artists.plot(kind='bar', color='skyblue')
    plt.xlabel('Artist')
    plt.ylabel('Number of Songs')
    plt.title('Top 10 Artists')
    plt.xticks(rotation=45)

    # 🛠️ Ensure static directory exists
    static_dir = os.path.join(os.getcwd(), 'static')
    if not os.path.exists(static_dir):
        os.makedirs(static_dir)

    # 📁 Save the Chart
    chart_path = os.path.join(static_dir, "top_artists_chart.png")
    plt.savefig(chart_path)
    plt.close()

    print(f"✅ DEBUG: Chart saved at: {chart_path}")

    return jsonify({'image_url': "/static/top_artists_chart.png"})


# 📊 Pie Chart for Genres with Improved Label Handling
@app.route('/visualize-genres')
def visualize_genres():
    conn = sqlite3.connect("spotify_data.db")
    df = pd.read_sql_query("SELECT genre FROM listening_history", conn)
    conn.close()

    if df.empty:
        return jsonify({"error": "No genre data available."})

    # Count occurrences of each genre
    genre_counts = df["genre"].value_counts()

    # 🎨 Create a transparent pie chart
    fig, ax = plt.subplots(figsize=(7, 7))
    fig.patch.set_alpha(0)  # Ensure background transparency

    wedges, texts, autotexts = ax.pie(
        genre_counts,
        labels=genre_counts.index,
        autopct='%1.1f%%',
        startangle=140,
        pctdistance=0.85,  # Push percentage values inward
        textprops={'fontsize': 10, 'color': 'white','fontproperties':poppins_font}  # Make all text white
    )

    # 🎨 Move small genre labels to the top-left
    small_genre_texts = []
    x_offset, y_offset = -1.8, 1.2
    for i, (wedge, label, percentage) in enumerate(zip(wedges, texts, autotexts)):
        pct = float(percentage.get_text().replace('%', ''))
        if pct < 5:
            label.set_visible(False)
            percentage.set_visible(False)

            color = wedge.get_facecolor()
            small_genre_texts.append((label.get_text(), pct, color))

    for i, (genre, pct, color) in enumerate(small_genre_texts):
        ax.text(
            x_offset, y_offset - (i * 0.1),
            f"{genre}: {pct:.1f}%",
            fontsize=10,
            color=color,
            fontweight="bold",
            fontproperties=poppins_font
        )

    # 🎵 Set title and remove white background
    ax.set_title("Top Genres Played", fontsize=14, fontweight='bold', color='white')
    plt.tight_layout()

    # 📁 Save the pie chart (Transparent)
    chart_path = "static/genre_pie_chart.png"
    plt.savefig(chart_path, dpi=300, bbox_inches="tight", transparent=True)
    plt.close()

    return jsonify({"image_url": chart_path})


# 🎵 Basic CSV-Based Recommendation System
@app.route('/recommend', methods=['POST'])
def recommend():
    global music_data
    if music_data is None:
        return jsonify({'error': '⚠️ No data uploaded'})

    query = request.json.get('query', '').strip().lower()
    if not query:
        return jsonify({'error': '⚠️ Please enter an artist or song name'})

    if 'artist' not in music_data.columns or 'track_name' not in music_data.columns:
        return jsonify({'error': '⚠️ CSV is missing required columns: artist or track_name'})

    matched_songs = music_data[
        music_data['artist'].str.lower().str.contains(query, na=False, regex=False) |
        music_data['track_name'].str.lower().str.contains(query, na=False, regex=False)
    ]

    if matched_songs.empty:
        return jsonify({'message': '⚠️ No matches found. Try another artist or song.'})

    recommendations = matched_songs[['track_name', 'artist']].sample(min(len(matched_songs), 5)).to_dict(orient='records')
    return jsonify(recommendations)

#This creates a table to store track name, artist, and timestamp
def init_db():
    conn = sqlite3.connect("spotify_data.db")
    cursor = conn.cursor()

    # Ensure the table has a `genre` column
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS listening_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        track_name TEXT,
        artist TEXT,
        played_at TEXT UNIQUE,
        genre TEXT
    )
    """)
    conn.commit()
    conn.close()


# Run when the app starts
init_db()

def save_to_db(tracks):
    """Saves track data to the SQLite database, ensuring genres are set."""
    conn = sqlite3.connect("spotify_data.db")
    cursor = conn.cursor()

    sp = spotipy.Spotify(auth=get_token())  # Ensure API is initialized

    for track in tracks:
        artist_id = track.get("artist_id")  # Get artist ID
        artist_name = track["artist"]

        # Fetch genre if possible
        if artist_id:
            try:
                artist_info = sp.artist(artist_id)
                genre_list = artist_info.get("genres", [])
                genre = genre_list[0] if genre_list else "Unknown"
            except Exception as e:
                print(f"⚠️ WARNING: Could not fetch genre for {artist_name}: {e}")
                genre = "Unknown"
        else:
            genre = "Unknown"

        # 🔥 If still unknown, use GPT-4o-mini
        if genre == "Unknown":
            genre = get_genre(artist_name)

        try:
            cursor.execute(
                """INSERT INTO listening_history (track_name, artist, played_at, genre) 
                   VALUES (?, ?, ?, ?)""",
                (track["track_name"], artist_name, track["played_at"], genre)
            )
        except sqlite3.IntegrityError:
            pass  # Avoid duplicate entries

    conn.commit()
    conn.close()



# ✅ Spotify Helper Function to Handle Token Refresh
def get_token():
    """Retrieve the access token from session and refresh it if expired"""
    print(f"🔍 DEBUG: Token Info BEFORE: {session.get('token_info')}")

    token_info = session.get("token_info")
    if not token_info:
        print("❌ ERROR: No token info found in session.")
        return None

    # 🔄 Automatically refresh the token if it's expired
    if token_info["expires_at"] - time.time() < 60:  # Refresh if it's about to expire (less than 60 sec left)
        print("🔄 DEBUG: Token expired, refreshing...")
        try:
            token_info = sp_oauth.refresh_access_token(token_info["refresh_token"])
            session["token_info"] = token_info
            session.modified = True  # ✅ Persist session changes
            print(f"✅ DEBUG: Token refreshed successfully: {token_info['access_token']}")
        except Exception as e:
            print(f"❌ ERROR: Failed to refresh token: {str(e)}")
            return None

    return token_info["access_token"]





#Store data in database (CSV)
def save_to_csv(tracks):
    df = pd.DataFrame(tracks)
    df.to_csv("spotify_listening_history.csv", mode="a", index=False, header=False)


#listening history save to sql database
@app.route('/spotify-listening-history')
def spotify_listening_history():
    token_info = get_token()
    if not token_info:
        return jsonify({"error": "User not authenticated. Please log in."})

    sp = spotipy.Spotify(auth=token_info)

    try:
        results = sp.current_user_recently_played(limit=10)

        if "items" not in results or not results["items"]:
            return jsonify({"error": "No listening history found."})

        track_data = []
        for item in results["items"]:
            track = item["track"]
            artist_id = track["artists"][0]["id"]  # Get artist ID
            artist_name = track["artists"][0]["name"]

            track_data.append({
                "track_name": track["name"],
                "artist": artist_name,  
                "played_at": item["played_at"],
                "artist_id": artist_id  # Store artist ID
            })

        save_to_db(track_data)  # Store in SQLite

        return jsonify({"message": "✅ Data saved to database!", "tracks": track_data})

    except Exception as e:
        print(f"❌ ERROR: Failed to fetch listening history - {e}")
        return jsonify({"error": "Failed to fetch listening history", "details": str(e)})





#bar chart for top artists
@app.route('/visualize-history')
def visualize_history():
    conn = sqlite3.connect("spotify_data.db")
    df = pd.read_sql_query("SELECT * FROM listening_history", conn)
    conn.close()

    if df.empty:
        return jsonify({"error": "No listening history available."})

    # 🎨 Plot settings
    fig, ax = plt.subplots(figsize=(10, 5))
    fig.patch.set_alpha(0)  # Ensure background transparency
    ax.set_facecolor("#121212")  # Match page background (dark gray)

    # 🎵 Top 10 Artists Bar Chart
    top_artists = df['artist'].value_counts().head(10)
    top_artists.plot(kind='bar', color='purple', ax=ax)

    # 🎨 Formatting
    ax.set_xlabel("Artist", fontsize=12, color="white")
    ax.set_ylabel("Times Played", fontsize=12, color="white")
    ax.set_title("Top 10 Most Played Artists", fontsize=14, fontweight="bold", color="white")
    ax.tick_params(axis='x', colors="white", rotation=45)
    ax.tick_params(axis='y', colors="white")

    # 📁 Save the Chart (Transparent)
    chart_path = "static/top_artists_chart.png"
    plt.savefig(chart_path, dpi=300, bbox_inches="tight", transparent=True)
    plt.close()

    return jsonify({"image_url": chart_path})





@app.route('/spotify-top-artists')
def spotify_top_artists():
    print(f"🔍 DEBUG: Token Info in Session BEFORE GETTING: {session.get('token_info')}")  

    access_token = get_token()
    if not access_token:
        return jsonify({"error": "User not authenticated. Please log in."})

    try:
        sp = spotipy.Spotify(auth=access_token)
        results = sp.current_user_top_artists(limit=10, time_range="long_term") 


        print(f"✅ DEBUG: Raw Spotify Response: {results}")  # 🔥 Print full response for debugging

        if "items" not in results or not results["items"]:
            return jsonify({"error": "No top artists found in your Spotify account."})

        top_artists = [{"name": artist["name"], "id": artist["id"]} for artist in results["items"]]
        return jsonify(top_artists)

    except Exception as e:
        print(f"❌ ERROR: Failed to fetch top artists - {e}")
        return jsonify({"error": "Failed to fetch top artists", "details": str(e)})





# 🔥 Spotify Login
@app.route('/spotify-login')
def spotify_login():
    return redirect(sp_oauth.get_authorize_url())


# 🔄 Spotify OAuth Callback
@app.route('/callback')
def spotify_callback():
    code = request.args.get('code')

    if not code:
        print("❌ DEBUG: No authorization code received")
        return "No authorization code received", 400

    print(f"✅ DEBUG: Received auth code: {code}")

    try:
        # 🔥 Retrieve the token
        token_info = sp_oauth.get_access_token(code, as_dict=True)
        if not token_info:
            print("❌ DEBUG: Failed to retrieve access token")
            return "Failed to retrieve access token", 400

        # 🔥 Store token in session correctly
        session["token_info"] = token_info
        session.modified = True  # ✅ Force Flask to save session
        print(f"✅ DEBUG: Stored token in session: {session.get('token_info')}")

    except Exception as e:
        print(f"❌ DEBUG: Error getting token: {str(e)}")
        return "Error getting token", 500

    # After storing token, fetch and save user's listening history immediately
    try:
        response = spotify_listening_history()
        print(f"✅ DEBUG: Auto-fetched listening history: {response}")
    except Exception as e:
        print(f"❌ ERROR: Failed to auto-fetch listening history - {e}")

    # ✅ After fetching history, update missing genres
    try:
        update_missing_genres()
        print("✅ DEBUG: Successfully updated missing genres!")
    except Exception as e:
        print(f"⚠️ WARNING: Could not update genres - {e}")

    return redirect(url_for('index'))



# Get Song Recommendations Using Spotify
@app.route('/spotify-recommendations')
def spotify_recommendations():
    token_info = get_token()
    if not token_info:
        return redirect(url_for('spotify_login'))

    sp = spotipy.Spotify(auth=token_info)
    top_artists = sp.current_user_top_artists(limit=5)  

    if not top_artists["items"]:
        return jsonify({"error": "No top artists found. Play more music on Spotify!"})

    seed_artists = [artist["id"] for artist in top_artists["items"][:3]]  # Use up to 3 artists

    recommendations = sp.recommendations(seed_artists=seed_artists, limit=10)  

    song_list = [{"name": track["name"], "artist": track["artists"][0]["name"]} for track in recommendations["tracks"]]
    return jsonify(song_list)


@app.route('/download-history', methods=['GET'])
def download_history():
    conn = sqlite3.connect("spotify_data.db")
    df = pd.read_sql_query("SELECT * FROM listening_history", conn)
    conn.close()

    if df.empty:
        return jsonify({"error": "No listening history available."})

    csv_path = os.path.join("uploads", "spotify_history.csv")
    df.to_csv(csv_path, index=False)
    return send_file(csv_path, as_attachment=True)



# 📂 Download Processed CSV
@app.route('/download', methods=['GET'])
def download_csv():
    global music_data
    if music_data is None:
        return jsonify({'error': '⚠️ No data uploaded'})

    csv_path = os.path.join(app.config['UPLOAD_FOLDER'], "exported_data.csv")
    music_data.to_csv(csv_path, index=False)
    return send_file(csv_path, as_attachment=True)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_file(os.path.join('static', filename))



if __name__ == '__main__':
    app.run(debug=True)