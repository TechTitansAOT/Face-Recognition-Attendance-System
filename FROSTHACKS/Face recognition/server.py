import logging
from flask import Flask, jsonify, request
import subprocess
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from flask_cors import CORS

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)

backend_running = False

# Google Sheets authentication and setup
def get_google_sheet():
    try:
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sheet = client.open("enter name of worksheet").get_worksheet(0)  # ensure correct name and index
        logging.debug("Successfully connected to Google Sheets.")
        return sheet
    except Exception as e:
        logging.error(f"Error connecting to Google Sheets: {e}")
        raise

@app.route("/get-subjects", methods=["GET"])
def get_subjects():
    try:
        sheet = get_google_sheet()
        subjects = sheet.row_values(1)[3:]  # Get subjects from D1, E1, F1, ...
        logging.debug(f"Fetched subjects: {subjects}")
        return jsonify({"subjects": subjects})
    except Exception as e:
        logging.error(f"Error fetching subjects: {e}")
        return jsonify({"error": "Failed to fetch subjects"}), 500

@app.route("/start-backend", methods=["POST"])
def start_backend():
    global backend_running

    if backend_running:
        logging.warning("Backend is already running.")
        return jsonify({"status": "error", "message": "Backend is already running"}), 400

    data = request.get_json()
    subject_name = data.get("subject")
    if not subject_name:
        logging.warning("No subject provided in the request.")
        return jsonify({"status": "error", "message": "No subject provided"}), 400

    try:
        sheet = get_google_sheet()
        subjects = sheet.row_values(1)[3:]  # Get subjects from D1, E1, F1, ...
        if subject_name not in subjects:
            logging.warning(f"Subject '{subject_name}' not found in the list.")
            return jsonify({"status": "error", "message": "Subject not found"}), 404

        # Calculate the column index (0-based) for the subject
        subject_index = subjects.index(subject_name) + 3

        # Start the face recognition script as a separate process with the subject index
        subprocess.Popen(["python", "recognition.py", str(subject_index)])
        time.sleep(5)  # Give it some time to initialize
        backend_running = True
        logging.info("Backend is starting...")
        return jsonify({"status": "success", "message": "Backend is starting..."})
    except Exception as e:
        logging.error(f"Error starting backend: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/status", methods=["GET"])
def check_status():
    status = "running" if backend_running else "not running"
    logging.debug(f"Backend status checked: {status}")
    return jsonify({"status": status})

@app.route("/add-subject", methods=["POST"])
def add_subject():
    try:
        # Get the incoming JSON and extract the subject.
        request_data = request.get_json()
        subject_name = request_data.get("subject")
        if not subject_name:
            return jsonify({"status": "error", "message": "No subject provided"}), 400

        # Get the worksheet using your helper
        sheet = get_google_sheet()  # This returns the first worksheet from "Attendance"

        # Fetch all the values in row 1.
        row_values = sheet.row_values(1)
        # The next subject should go into the next available column after the existing ones.
        next_col_num = len(row_values) + 1  # Assuming no gaps in the header row

        # Convert the numeric column into an A1-style letter.
        cell_letter = col_to_letter(next_col_num)
        target_cell = f"{cell_letter}1"  # For example, "D1", "E1", etc.

        # Update the single cell using update_acell (which accepts a single string value)
        sheet.update_acell(target_cell, subject_name)

        return jsonify({"status": "success", "target_cell": target_cell})
    except Exception as e:
        print("Error:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

def col_to_letter(col):
    # Convert a 1-indexed column number to a column letter (e.g. 4 -> "D")
    letter = ""
    while col:
        col, remainder = divmod(col - 1, 26)
        letter = chr(65 + remainder) + letter
    return letter

if __name__ == "__main__":
    logging.debug("Starting Flask application...")
    app.run(debug=True)