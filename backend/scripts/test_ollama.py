import requests
import os
import json
import environ

# Setup environment like Django
env = environ.Env()

OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
CURRENT_MODEL = os.getenv('OLLAMA_TEXT_MODEL', 'llama3')

def print_header(title):
    print(f"\n{'='*50}")
    print(f" {title}")
    print(f"{'='*50}")

def test_connection():
    print_header("OLLAMA DIAGNOSTICS")
    print(f"Base URL: {OLLAMA_BASE_URL}")
    print(f"Configured Model: {CURRENT_MODEL}")

    try:
        # 1. Test basic connectivity (Version)
        print("\n1. Testing Connectivity...")
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/version", timeout=5)
            if resp.status_code == 200:
                print(f"✅ Connected! Version: {resp.json().get('version')}")
            else:
                print(f"⚠️ Connected but status {resp.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"❌ Could not connect to {OLLAMA_BASE_URL}")
            print("   - Check if Ollama is running.")
            print("   - Only 'host.docker.internal' works if Ollama is on the host machine.")
            return

        # 2. List Models
        print("\n2. Checking Available Models...")
        resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
        if resp.status_code == 200:
            models_data = resp.json().get('models', [])
            model_names = [m.get('name') for m in models_data]
            print(f"✅ Found {len(model_names)} models:")
            for name in model_names:
                print(f"   - {name}")
            
            if CURRENT_MODEL in model_names:
                print(f"\n✅ Configured model '{CURRENT_MODEL}' is AVAILABLE.")
            else:
                print(f"\n❌ Configured model '{CURRENT_MODEL}' was NOT found in the list.")
                print(f"   PLEASE RUN: ollama pull {CURRENT_MODEL}")
        else:
            print(f"❌ Failed to list models. Status: {resp.status_code}")

        # 3. Test Generation (if model exists)
        if CURRENT_MODEL:
            print("\n3. Testing Generation...")
            payload = {
                "model": CURRENT_MODEL,
                "prompt": "Say hello!",
                "stream": False
            }
            try:
                resp = requests.post(f"{OLLAMA_BASE_URL}/api/generate", json=payload, timeout=30)
                if resp.status_code == 200:
                    print(f"✅ Generation Successful!")
                    print(f"   Response: {resp.json().get('response')}")
                elif resp.status_code == 404:
                    print("❌ Model not found (404).")
                else:
                    print(f"❌ Generation failed with status {resp.status_code}")
                    print(resp.text)
            except Exception as e:
                print(f"❌ Error during generation: {e}")

    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    test_connection()
