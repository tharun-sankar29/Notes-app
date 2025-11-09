from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, session
from flask_cors import CORS
from datetime import datetime, timezone
import os
import logging
from dotenv import load_dotenv
from s3_utils import S3Manager
from user_manager import UserManager
from functools import wraps
import uuid

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
user_manager = UserManager()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', str(uuid.uuid4()))
CORS(app)

# Initialize note counter
note_counter = 1

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    if 'user_email' in session:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        user, error = user_manager.verify_user(email, password)
        if user:
            session['user_email'] = user['email']
            session['user_name'] = user['name']
            return redirect(url_for('dashboard'))
        flash(error or 'Invalid credentials', 'error')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        
        if password != confirm_password:
            flash('Passwords do not match', 'error')
        else:
            success, message = user_manager.create_user(name, email, password)
            if success:
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            flash(message, 'error')
    return render_template('signup.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('index.html', user_name=session.get('user_name'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Debug route to check session and user data
@app.route('/debug/session')
def debug_session():
    return jsonify({
        'session': dict(session),
        'user_authenticated': 'user_email' in session,
        'user_email': session.get('user_email'),
        'user_name': session.get('user_name')
    })

@app.route('/api/notes', methods=['GET'])
@login_required
def get_notes():
    try:
        user_email = session.get('user_email')
        logger.info(f"Fetching notes for user: {user_email}")
        
        # Get user's notes from their specific folder
        user_notes = s3_manager.get_user_notes(user_email)
        logger.info(f"Found {len(user_notes)} notes for user {user_email}")
        
        return jsonify(user_notes)
    except Exception as e:
        logger.error(f"Error in get_notes: {str(e)}", exc_info=True)
        return jsonify({"error": "Failed to fetch notes"}), 500

@app.route('/api/notes', methods=['POST'])
@login_required
def add_note():
    try:
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({"error": "User not authenticated"}), 401
            
        data = request.get_json()
        logger.info(f"Received request to add new note for user {user_email}: {data}")
        
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
            "user_email": user_email,  # Always set the user_email
            "createdAt": data.get('createdAt', datetime.now(timezone.utc).isoformat()),
            "updatedAt": datetime.now(timezone.utc).isoformat()
        }
        
        # Save to S3 in the user's folder
        if s3_manager.upload_note(note):
            logger.info(f"Successfully created new note with ID: {note_id} for user: {user_email}")
            return jsonify(note), 201
        else:
            logger.error(f"Failed to save note to S3 for user {user_email}")
            return jsonify({"error": "Failed to save note"}), 500
            
    except Exception as e:
        logger.error(f"Error in add_note: {str(e)}", exc_info=True)
        return jsonify({"error": "An error occurred while saving the note"}), 500

@app.route('/api/notes/<note_id>', methods=['PUT'])
@login_required
def update_note(note_id):
    try:
        user_email = session.get('user_email')
        if not user_email:
            return jsonify({"error": "User not authenticated"}), 401
            
        data = request.get_json()
        logger.info(f"Received update request for note ID {note_id} from user {user_email}: {data}")
        
        if not data or ('title' not in data and 'content' not in data):
            logger.warning(f"Invalid update data for note ID {note_id}")
            return jsonify({"error": "Title or content is required"}), 400
        
        # Get the specific note from the user's folder
        user_notes = s3_manager.get_user_notes(user_email)
        note = next((note for note in user_notes if str(note['id']) == str(note_id)), None)
        
        if not note:
            logger.warning(f"Note ID {note_id} not found for user {user_email}")
            return jsonify({"error": "Note not found"}), 404
        
        # Update the note
        if 'title' in data:
            note['title'] = data['title'].strip()
        if 'content' in data:
            note['content'] = data['content'].strip()
        
        note['updatedAt'] = datetime.now(timezone.utc).isoformat()
        
        # Save the updated note back to S3 in the user's folder
        if s3_manager.upload_note(note):
            logger.info(f"Successfully updated note ID: {note_id} for user: {user_email}")
            return jsonify(note)
        else:
            logger.error(f"Failed to update note ID: {note_id} for user: {user_email}")
            return jsonify({"error": "Failed to update note"}), 500
            
    except Exception as e:
        logger.error(f"Error in update_note: {str(e)}", exc_info=True)
        return jsonify({"error": "An error occurred while updating the note"}), 500

@app.route('/api/notes/<note_id>', methods=['DELETE'])
@login_required
def delete_note(note_id):
    try:
        user_email = session.get('user_email')
        logger.info(f"Received delete request for note ID: {note_id} from user: {user_email}")
        
        # Delete the note from the user's S3 folder
        if s3_manager.delete_note(note_id, user_email):
            logger.info(f"Successfully deleted note ID: {note_id} for user: {user_email}")
            return jsonify({"message": "Note deleted successfully", "id": note_id})
        else:
            logger.error(f"Failed to delete note ID: {note_id} for user: {user_email}")
            return jsonify({"error": "Failed to delete note"}), 500
    except Exception as e:
        logger.error(f"Error in delete_note: {str(e)}", exc_info=True)
        return jsonify({"error": "An error occurred while deleting the note"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
