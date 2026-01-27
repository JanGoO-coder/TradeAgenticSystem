from app.core.config import get_settings
try:
    settings = get_settings()
    print("Settings initialized successfully")
except Exception as e:
    print(f"Error initializing settings: {e}")
