
import os
import google.generativeai as genai
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
# list_models.py is in d:\TradeAgenticSystem
# .env is in d:\TradeAgenticSystem\backend\.env
env_path = os.path.join(current_dir, "backend", ".env")

print(f"Loading env from: {env_path}")
if os.path.exists(env_path):
    print("File exists.")
    load_dotenv(env_path)
else:
    print("File DOES NOT exist.")

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    # Try reading manually to debug
    try:
        with open(env_path, 'r') as f:
            content = f.read()
            if "GOOGLE_API_KEY" in content:
                print("Found GOOGLE_API_KEY in file text but load_dotenv failed.")
                for line in content.splitlines():
                    if line.startswith("GOOGLE_API_KEY"):
                        key_val = line.split("=", 1)[1].strip()
                        api_key = key_val.strip('"').strip("'")
                        print("Manually extracted key.")
    except Exception as e:
        print(f"Error reading file: {e}")

if not api_key:
    print("Still no API Key.")
    exit(1)

genai.configure(api_key=api_key)

print("Listing models...")
try:
    for m in genai.list_models():
        if "gemini" in m.name:
            print(m.name)
except Exception as e:
    print(f"List models failed: {e}")
