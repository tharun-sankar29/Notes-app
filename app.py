from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone
import os
import logging
from dotenv import load_dotenv
from s3_utils import S3Manager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app.log')
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize S3 Manager
s3_manager = S3Manager()

app = Flask(__name__)
CORS(app)

# Initialize note counter
note_counter = 1

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/notes', methods=['GET'])
def get_notes():
    logger.info("Fetching all notes from S3")
    notes = s3_manager.get_all_notes()
    logger.info(f"Successfully retrieved {len(notes)} notes")
    return jsonify(notes)

@app.route('/api/notes', methods=['POST'])
def add_note():
    global note_counter
    data = request.get_json()
    logger.info(f"Received request to add new note: {data}")
    
    if not data or ('title' not in data and 'content' not in data):
        logger.warning("Invalid note data received - missing title and content")
        return jsonify({"error": "Note title or content is required"}), 400
    
    # Get title and content from the request
    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    
    # If title is empty but content exists, use first line of content as title
    if not title and content:
        first_line = content.split('\n')[0].strip()
        title = first_line[:50] + '...' if len(first_line) > 50 else first_line
    
    if not title:
        title = "Untitled Note"
    
    # Generate a unique ID using timestamp if not provided
    note_id = data.get('id', int(datetime.now(timezone.utc).timestamp() * 1000))
    
    note = {
        "id": note_id,
        "title": title,
        "content": content,
        "createdAt": data.get('createdAt', datetime.now(timezone.utc).isoformat()),
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    
    # Save to S3
    if s3_manager.upload_note(note):
        logger.info(f"Successfully created new note with ID: {note_id}")
        return jsonify(note), 201
    else:
        logger.error(f"Failed to save note to S3: {note}")
        return jsonify({"error": "Failed to save note to S3"}), 500

@app.route('/api/notes/<note_id>', methods=['PUT'])
def update_note(note_id):
    data = request.get_json()
    logger.info(f"Received update request for note ID {note_id}: {data}")
    
    if not data or ('title' not in data and 'content' not in data):
        logger.warning(f"Invalid update data for note ID {note_id}")
        return jsonify({"error": "Title or content is required"}), 400
    
    # Get all notes to find the one we want to update
    notes = s3_manager.get_all_notes()
    note = next((note for note in notes if str(note['id']) == str(note_id)), None)
    
    if not note:
        return jsonify({"error": "Note not found"}), 404
    
    # Update the note
    if 'title' in data:
        note['title'] = data['title'].strip()
    if 'content' in data:
        note['content'] = data['content'].strip()
    
    note['updatedAt'] = datetime.now(timezone.utc).isoformat()
    
    # Save the updated note back to S3
    if s3_manager.upload_note(note):
        return jsonify(note)
    else:
        return jsonify({"error": "Failed to update note in S3"}), 500

@app.route('/api/notes/<note_id>', methods=['DELETE'])
def delete_note(note_id):
    logger.info(f"Received delete request for note ID: {note_id}")
    # Delete the note from S3
    if s3_manager.delete_note(note_id):
        logger.info(f"Successfully deleted note ID: {note_id}")
        return jsonify({"message": "Note deleted successfully", "id": note_id})
    else:
        logger.error(f"Failed to delete note ID: {note_id}")
        return jsonify({"error": "Failed to delete note from S3"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
