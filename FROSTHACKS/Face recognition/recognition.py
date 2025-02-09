import sys
import cv2
import face_recognition
import numpy as np
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Load the pre-trained Haar Cascade classifier for frontal face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# Define the area thresholds in square pixels
LOWER_THRESHOLD = 13225  # Minimum area for a valid face
UPPER_THRESHOLD = 38000  # Maximum area for a valid face

# Ensure the subject column index is provided
if len(sys.argv) != 2:
    print("Usage: python recognition.py <subject_column_index>")
    sys.exit(1)

subject_col_index = int(sys.argv[1])

# Google Sheets API Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
try:
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("enter name of worksheet").get_worksheet(0)  # Ensure the correct name and index
    print("Connected to Google Sheets successfully.")
except Exception as e:
    print("Error: Could not connect to Google Sheets.")
    print(e)
    exit()

# Fetch student data
try:
    students = sheet.get_all_values()[1:]  # Skip header row
except Exception as e:
    print("Error: Could not fetch student data.")
    print(e)
    exit()

# Initialize attendance to 0 for all students only if the cell is empty
for i in range(0, len(students), 4):
    attendance_row = i + 2
    current_value = sheet.cell(attendance_row, subject_col_index + 1).value
    if not current_value:  # Only update if the cell is empty
        sheet.update_cell(attendance_row, subject_col_index + 1, 0)

known_face_encodings = []
known_face_names = []
attendance_dict = {}
marked_faces = set()
face_match_counts = {}

for i in range(0, len(students), 4):  # Process every 4th row
    if len(students[i]) < 2:
        continue  # Skip if the row is empty

    name, roll = students[i][:2]  # Name and Roll Number
    attendance_row = i + 2  # Google Sheets uses 1-based indexing

    attendance_dict[roll] = 0  # Initialize attendance as 0

    # Extract encodings from Columns C (C2, C3, C4 for first person, C6, C7, C8 for second, etc.)
    encodings_list = [sheet.cell(attendance_row + j, 3).value for j in range(3)]
    
    valid_encodings = []
    for enc in encodings_list:
        try:
            if enc:
                np_encoding = np.array(eval(enc))
                if np_encoding.shape == (128,):
                    valid_encodings.append(np_encoding)
        except (SyntaxError, ValueError):
            continue

    if valid_encodings:
        known_face_encodings.append(valid_encodings[0])  # Use the first valid encoding
        known_face_names.append(roll)

# Open Camera
video_capture = cv2.VideoCapture(0)
if not video_capture.isOpened():
    print("Error: Could not open webcam.")
    exit()

print("Press 'q' to exit.")

while True:
    ret, frame = video_capture.read()
    if not ret:
        print("Error: Could not read frame from webcam.")
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    face_locations = face_recognition.face_locations(rgb_frame)
    face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

    # Convert the frame to grayscale for Haar Cascade
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))

    for face_encoding, face_location in zip(face_encodings, face_locations):
        matches = face_recognition.compare_faces(known_face_encodings, face_encoding, tolerance=0.5)
        roll_number = None
        color = (0, 0, 255)
        name = "Unknown"

        top, right, bottom, left = face_location
        face_width = right - left
        face_height = bottom - top
        face_area = face_width * face_height

        if face_area < LOWER_THRESHOLD:
            cv2.putText(frame, "Spoof Detected: Face too small", (left, bottom + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)
            continue
        elif face_area > UPPER_THRESHOLD:
            cv2.putText(frame, "Move Back: Face too large", (left, bottom + 20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

        if True in matches:
            first_match_index = matches.index(True)
            roll_number = known_face_names[first_match_index]

            if roll_number not in marked_faces:
                row_index = [i + 2 for i in range(0, len(students), 4) if students[i][1] == roll_number][0]
                try:
                    current_attendance = int(sheet.cell(row_index, subject_col_index + 1).value or 0)
                    sheet.update_cell(row_index, subject_col_index + 1, current_attendance + 1)
                    marked_faces.add(roll_number)
                    name = f"Marked {roll_number}"
                    color = (0, 255, 0)
                except Exception as e:
                    print(f"Error updating attendance for {roll_number}: {e}")
            else:
                name = f"Marked {roll_number}"
                color = (0, 255, 0)

        cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
        cv2.putText(frame, name, (left, top - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

    cv2.imshow("Face Recognition with Anti-Spoofing", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

video_capture.release()
cv2.destroyAllWindows()
marked_faces.clear()
