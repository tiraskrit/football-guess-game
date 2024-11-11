import os
from dotenv import load_dotenv

load_dotenv()

# Get API key from environment variable
API_KEY = os.environ.get('API_KEY')

if not API_KEY:
    raise ValueError("API_KEY environment variable is not set")

HEADERS = {'x-apisports-key': API_KEY}