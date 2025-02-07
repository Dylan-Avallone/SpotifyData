import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import dotenv
import openai  # Import OpenAI API

# Load environment variables
dotenv.load_dotenv()

# 🔥 OpenAI API Setup
openai.api_key = os.getenv("OPENAI_API_KEY")

# 🔥 Spotify Authentication
sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope="user-top-read user-read-recently-played"
)

# 🔥 Get a fresh access token
token_info = sp_oauth.get_access_token(as_dict=True)
ACCESS_TOKEN = token_info["access_token"]
print(f"🎟️ ACCESS TOKEN: {ACCESS_TOKEN}")

# 🔥 Initialize Spotify API with the fresh token
sp = spotipy.Spotify(auth=ACCESS_TOKEN)

# ✅ Test Genre Fetching
artists = ["Bruno Mars", "The Weeknd", "Drake", "Eminem", "Ariana Grande", "Taylor Swift"]

def fetch_genre_from_gpt(artist_name):
    """Fetch genre using OpenAI API if Spotify fails."""
    prompt = f"What is the primary music genre of the artist {artist_name}? Give a short, direct answer."
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )
        genre = response["choices"][0]["message"]["content"].strip()
        print(f"🎨 AI-Fetched Genre for {artist_name}: {genre}")
        return genre
    except Exception as e:
        print(f"❌ ERROR: Failed to get AI genre for {artist_name} - {e}")
        return "Unknown"

for artist in artists:
    # 🔍 Fetch artist details first
    results = sp.search(q=artist, type="artist", limit=1)

    if results["artists"]["items"]:
        artist_data = results["artists"]["items"][0]
        artist_id = artist_data["id"]
        artist_genres = artist_data["genres"]

        if artist_genres:
            print(f"🎵 {artist} - Artist Genres: {artist_genres}")
        else:
            print(f"⚠️ {artist} - No genres found on Spotify. Fetching from OpenAI...")
            genre = fetch_genre_from_gpt(artist)
            print(f"✅ Final Genre for {artist}: {genre}")

    else:
        print(f"⚠️ No data found for {artist}")
