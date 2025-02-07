import spotipy
from spotipy.oauth2 import SpotifyOAuth
import os
import dotenv

dotenv.load_dotenv()

sp_oauth = SpotifyOAuth(
    client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    redirect_uri=os.getenv("SPOTIFY_REDIRECT_URI"),
    scope="user-top-read user-read-recently-played"
)

token_info = sp_oauth.get_access_token(as_dict=True)
ACCESS_TOKEN = token_info["access_token"]
print(f"🎟️ ACCESS TOKEN: {ACCESS_TOKEN}")

sp = spotipy.Spotify(auth=ACCESS_TOKEN)

artists = ["The Weeknd", "Drake", "Eminem", "Ariana Grande", "Taylor Swift"]

for artist in artists:
    print(f"🔍 Searching for: {artist}")  # Debug line
    results = sp.search(q=artist, type="artist", limit=5)  # Get top 5 results

    if results["artists"]["items"]:
        correct_artist = None

        for item in results["artists"]["items"]:
            if item["name"].lower() == artist.lower():  # Match exact name
                correct_artist = item
                break  # Stop loop when match is found

        if correct_artist:
            print(f"✅ Found: {correct_artist['name']} - Genres: {correct_artist['genres']}")
        else:
            print(f"⚠️ No exact match for {artist}, showing first result: {results['artists']['items'][0]['name']}")

    else:
        print(f"⚠️ No data found for {artist}")
