from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
import requests
import random
import cv2
import numpy as np
import base64
from io import BytesIO
from PIL import Image
from datetime import datetime, timezone, timedelta
import json
import os
from config import HEADERS
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)

CORS(app)

# CORS(app, resources={r"/api/*": {"origins": "*", "supports_credentials": True}})

CACHE_FILE = 'daily_player_cache.json'

class DailyPlayerGame:
    def __init__(self):
        self.current_player = None
        self.blurred_image = None
        self.partially_blurred = None
        self.last_reset_date = None
        self.player_pool = []
        
    def _get_current_date(self):
        """Get current UTC date string"""
        return datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    def _load_cache(self):
        """Load cached player data if it exists"""
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, 'r') as f:
                    cache = json.load(f)
                    cached_date = cache.get('date')

                    # Compare the cached date with the current date
                    if cached_date == self._get_current_date():
                        return cache.get('player')
                    else:
                        # If the date is from a previous day, clear the cache
                        return None
            except (json.JSONDecodeError, KeyError):
                return None
        return None

    
    def _save_cache(self, player_data):
        """Save player data to cache"""
        cache = {
            'date': self._get_current_date(),
            'player': player_data
        }
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    
    def _fetch_player_pool(self):
        """Fetch pool of players from API"""
        try:
            # Fetch from multiple leagues to get a diverse pool
            leagues = ['39', '140', '135', '78']  # Premier League, La Liga, Serie A, Bundesliga
            self.player_pool = []
            
            for league in leagues:
                # url = "https://api-football-v1.p.rapidapi.com/v3/players/topscorers"
                url =  "https://v3.football.api-sports.io/players/topscorers"
                response = requests.get(url, headers=HEADERS, params={'league': league, 'season': '2022'})
                if response.status_code == 200:
                    players = response.json().get('response', [])
                    self.player_pool.extend(players)

            player_names = [player['player']['name'] for player in self.player_pool]
            with open('player_names.json', 'w') as f:
                json.dump(player_names, f)
            
            # Shuffle the pool using today's date as seed
            today = self._get_current_date()
            random.seed(today)
            random.shuffle(self.player_pool)
            
        except Exception as e:
            print(f"Error fetching player pool: {str(e)}")
            # Use backup data if API fails
            self._load_backup_players()
    
    def _load_backup_players(self):
        """Load backup player data in case API fails"""
        self.player_pool = [
            {
                'player': {
                    'id': 1,
                    'name': 'Lionel Messi',
                    'nationality': 'Argentina',
                    'photo': 'https://media.api-sports.io/football/players/154.png'
                },
                'statistics': [{
                    'team': {
                        'name': 'Inter Miami'
                    }
                }]
            },
            # Add more backup players...
        ]
    
    def get_daily_player(self):
        """Get or generate player for current day"""
        current_date = self._get_current_date()
        
        # Check if we need to reset
        if self.last_reset_date != current_date:
            # Try to load from cache first
            cached_player = self._load_cache()
            if cached_player:
                self.current_player = cached_player
            else:
                # Fetch player pool if it's empty
                if not self.player_pool:
                    self._fetch_player_pool()
                
                # Check if player pool is still empty after fetch
                if not self.player_pool:
                    self._load_backup_players()
                
                # Ensure we have a player in the pool to avoid IndexError
                if self.player_pool:
                    player = self.player_pool[0]  # Use first player from shuffled pool
                    self.current_player = {
                        'id': player['player']['id'],
                        'name': player['player']['name'],
                        'country': player['player']['nationality'],
                        'club': player['statistics'][0]['team']['name'],
                        'image_url': player['player']['photo']
                    }
                    self._save_cache(self.current_player)
                else:
                    # Handle case where backup also fails (extremely rare)
                    print("Error: No player available in pool or backup.")
                    return None  # Or set self.current_player to a placeholder object

            # Process images if current_player is available
            if self.current_player:
                self._process_image()
                self.last_reset_date = current_date
        
        return self.current_player

    
    def _process_image(self):
        """Process and blur player image"""
        try:
            response = requests.get(self.current_player['image_url'])
            img = Image.open(BytesIO(response.content))
            img_array = np.array(img)
            
            # Create different blur levels
            # Heavy blur for initial hint
            self.blurred_image = cv2.GaussianBlur(img_array, (35, 35), 30)
            
            # Medium blur for second hint (reduced from previous values)
            self.partially_blurred = cv2.GaussianBlur(img_array, (25, 25), 10)
            
            # Light blur for final hint
            self.slightly_blurred = cv2.GaussianBlur(img_array, (15, 15), 5)
        
            
            # Convert images to base64
            self._convert_images_to_base64()
        except Exception as e:
            print(f"Error processing image: {str(e)}")
            # Use placeholder image if processing fails
            self._use_placeholder_image()
    
    def _convert_images_to_base64(self):
        """Convert processed images to base64"""
        def arr_to_base64(arr):
            img = Image.fromarray(arr)
            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            return base64.b64encode(buffered.getvalue()).decode()
        
        self.current_player['blurred_image'] = arr_to_base64(self.blurred_image)
        self.current_player['partially_blurred'] = arr_to_base64(self.partially_blurred)
        self.current_player['slightly_blurred'] = arr_to_base64(self.slightly_blurred)

    
    def _use_placeholder_image(self):
        """Use placeholder if image processing fails"""
        self.current_player['blurred_image'] = "placeholder_base64"
        self.current_player['partially_blurred'] = "placeholder_base64"
        self.current_player['slightly_blurred'] = "placeholder_base64"

    def get_next_reset_time(self):
        """Get time until next reset"""
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return int((tomorrow - now).total_seconds())
    
    def daily_check(self):
        """Check if the cache needs to be reset and load new data if required."""
        current_date = self._get_current_date()
        if self.last_reset_date != current_date:
            self.current_player = None  # Invalidate current player data
            new_player = self._load_cache()  # Attempt to load or refresh cache
            if not new_player:
                # Logic to fetch new player and call _save_cache() if needed
                pass  # Replace with actual fetching logic

game = DailyPlayerGame()

@app.route('/api/game-state', methods=['GET'])
def get_game_state():
    player = game.get_daily_player()
    next_reset = game.get_next_reset_time()
    
    return jsonify({
        'blurred_image': player['blurred_image'],
        'game_id': player['id'],
        'next_reset': next_reset,
        'current_date': game.last_reset_date,
    })

@app.route('/api/player-names', methods=['GET'])
def get_player_names():
    try:
        with open('player_names.json', 'r') as f:
            player_names = json.load(f)
        return jsonify(player_names)
    except FileNotFoundError:
        # Create the file with an empty list if it doesn't exist
        with open('player_names.json', 'w') as f:
            json.dump([], f)
        return jsonify([])

# In daily_game_backend.py, modify the check_guess route

@app.route('/api/guess', methods=['POST'])
def check_guess():
    data = request.get_json()
    guess = data.get('guess', '').lower()
    current_hint_level = data.get('hint_level', 0)
    
    if not game.current_player:
        return jsonify({'error': 'No active game'}), 400
    
    correct = guess == game.current_player['name'].lower()
    
    response = {
        'correct': correct,
        'hint_level': current_hint_level,
        'next_reset': game.get_next_reset_time(),
        'hint_text': None,
        'hint_image': None,
        'player_name': None
    }
    
    # Show original image and player name for game over scenarios
    if correct or current_hint_level >= 4:
        response['hint_image'] = None
        response['image_url'] = game.current_player['image_url']
        response['player_name'] = game.current_player['name']
        
        resp = make_response(jsonify(response))
        return resp
    
    # Regular hint progression
    if not correct and current_hint_level < 5:
        if current_hint_level == 0:
            response['hint_text'] = f"Player's Country: {game.current_player['country']}"
            response['hint_image'] = game.current_player['blurred_image']
        elif current_hint_level == 1:
            response['hint_text'] = f"Player's Country: {game.current_player['country']}"
            response['hint_image'] = game.current_player['partially_blurred']
        elif current_hint_level == 2:
            response['hint_text'] = f"Player's Club: {game.current_player['club']}"
            response['hint_image'] = game.current_player['partially_blurred']
        elif current_hint_level == 3:
            response['hint_text'] = f"Player's Club: {game.current_player['club']}"
            response['hint_image'] = game.current_player['slightly_blurred']
    
    return jsonify(response)

if __name__ == '__main__':
    # Start a scheduler to run daily_check() every 24 hours
    scheduler = BackgroundScheduler()
    scheduler.add_job(game.daily_check, 'interval', days=1, start_date='2024-11-09 00:00:00')
    scheduler.start()
    app.run()