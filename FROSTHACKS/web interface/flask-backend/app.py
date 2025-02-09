from flask import Flask, request, jsonify
from flask_cors import CORS
import gspread
from google.oauth2.service_account import Credentials
import face_recognition
import os

app = Flask(__name__)
CORS(app, supports_credentials=True)

# Authenticate with Google Sheets API
SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(BASE_DIR, "credentials.json")
CREDS = Credentials.from_service_account_file(CREDENTIALS_PATH, scopes=SCOPE)
gc = gspread.authorize(CREDS)

# Open Google Sheet (Replace with your actual Sheet ID)
SPREADSHEET_ID = "put your spreadsheet id"
worksheet = gc.open_by_key(SPREADSHEET_ID).sheet1

def initialize_sheet_headers():
    """Ensure headers are set at the top of the sheet."""
    headers = ["Name", "Roll", "Encodings"]
    current_headers = worksheet.row_values(1)
    if not current_headers or any(h != headers[i] for i, h in enumerate(current_headers)):
        worksheet.update("A1:G1", [headers])

def get_face_encoding(image_path):
    """Extract face encodings from an image file."""
    try:
        image = face_recognition.load_image_file(image_path)
        encodings = face_recognition.face_encodings(image)
        
        if len(encodings) == 0:
            return None  # No face detected
        
        return encodings[0].tolist()  # Convert numpy array to list
    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return None

def find_next_available_row():
    """Find the next available row in multiples of 4 (1, 5, 9...) ensuring no empty gaps."""
    data = worksheet.get_all_values()
    row = 2  # Start from the second row to avoid overwriting headers
    while True:
        if not any(worksheet.row_values(row)):
            return row
        row += 4

def data_exists(roll, encodings):
    """Check if the roll number or any of the face encodings already exist in the database."""
    data = worksheet.get_all_values()
    existing_rolls = [row[1] for row in data[1:] if len(row) > 1]
    existing_encodings = [row[2] for row in data[1:] if len(row) > 2]
    
    if roll in existing_rolls:
        return True
    
    for encoding in encodings:
        if str(encoding) in existing_encodings:
            return True
    
    return False

@app.route('/submit', methods=['POST'])
def submit_form():
    try:
        initialize_sheet_headers()  # Ensure headers are set before inserting data

        name = request.form.get("name")
        roll = request.form.get("roll")
        
        if not name or not roll:
            return jsonify({"error": "Missing form data"}), 400

        # Save uploaded images temporarily
        img_paths = []
        for i in range(1, 4):
            file = request.files.get(f"image{i}")
            if not file:
                return jsonify({"error": f"Image {i} is missing"}), 400

            filename = f"temp_image_{i}.jpg"
            file.save(filename)
            img_paths.append(filename)

        # Extract face encodings
        encodings = [get_face_encoding(img) for img in img_paths]

        # Cleanup: Remove temporary images
        for img in img_paths:
            os.remove(img)

        # If any image failed to produce a face encoding, return an error
        if any(e is None for e in encodings):
            return jsonify({"error": "One or more images did not contain a detectable face."}), 400

        # Check if roll number or encodings already exist
        if data_exists(roll, encodings):
            response = jsonify({"error": "Data already exists!"})
            response.status_code = 400
            response.headers.add("Access-Control-Allow-Origin", "*")
            response.headers.add("Access-Control-Allow-Credentials", "true")
            return response

        # Find the next available row ensuring no gaps
        next_row = find_next_available_row()
        
        # Store metadata and encodings
        worksheet.update(f"A{next_row}", [[name]])
        worksheet.update(f"B{next_row}", [[roll]])
        worksheet.update(f"C{next_row}", [[str(encodings[0])]])
        worksheet.update(f"C{next_row + 1}", [[str(encodings[1])]])
        worksheet.update(f"C{next_row + 2}", [[str(encodings[2])]])
        
        response = jsonify({"success": "Data saved successfully!"})
        response.status_code = 200
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response

    except Exception as e:
        response = jsonify({"error": str(e)})
        response.status_code = 500
        response.headers.add("Access-Control-Allow-Origin", "*")
        response.headers.add("Access-Control-Allow-Credentials", "true")
        return response

if __name__ == '__main__':
    app.run(debug=True)