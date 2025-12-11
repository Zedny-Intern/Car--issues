import requests
import os

def test_large_upload():
    file_path = "test_large.pdf"
    
    # Create 10MB dummy file
    print("Creating 10MB dummy file...")
    with open(file_path, "wb") as f:
        f.write(b"0" * (10 * 1024 * 1024))
    
    url = "http://localhost:8000/api/v1/complaints/12/upload_document/"
    print(f"Uploading to {url}...")
    
    try:
        with open(file_path, "rb") as f:
            files = {"file": ("test_large.pdf", f, "application/pdf")}
            # 60 second timeout
            response = requests.post(url, files=files, timeout=60)
            
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if os.path.exists(file_path):
            os.remove(file_path)

if __name__ == "__main__":
    test_large_upload()
