# config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your_fallback_secret_key')
    DATABASE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "perfume_shop.db"))