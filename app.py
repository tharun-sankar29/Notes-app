from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from datetime import datetime, timezone

app = Flask(__name__)
CORS(app)

# In-memory storage (replace with database in production)
notes = []
note_counter = 1

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/notes', methods=['GET'])
def get_notes():
    # Return notes sorted by creation date (newest first)
    return jsonify(sorted(notes, key=lambda x: x["createdAt"], reverse=True))

@app.route('/api/notes', methods=['POST'])
def add_note():
    global note_counter
    data = request.get_json()
    
    if not data or ('title' not in data and 'content' not in data):
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
    
    note = {
        "id": note_counter,
        "title": title,
        "content": content,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "updatedAt": datetime.now(timezone.utc).isoformat()
    }
    
    notes.append(note)
    note_counter += 1
    
    return jsonify(note), 201

@app.route('/api/notes/<int:note_id>', methods=['PUT'])
def update_note(note_id):
    data = request.get_json()
    
    if not data or ('title' not in data and 'content' not in data):
        return jsonify({"error": "Title or content is required"}), 400
    
    # Get existing note
    note = next((note for note in notes if note['id'] == note_id), None)
    if not note:
        return jsonify({"error": "Note not found"}), 404
    
    # Update title if provided
    if 'title' in data:
        title = data['title'].strip()
        note['title'] = title if title else "Untitled Note"
    
    # Update content if provided
    if 'content' in data:
        note['content'] = data['content'].strip()
    
    # If title is empty but content exists, use first line of content as title
    if not note['title'] and note['content']:
        first_line = note['content'].split('\n')[0].strip()
        note['title'] = first_line[:50] + '...' if len(first_line) > 50 else first_line
    
    note['updatedAt'] = datetime.now(timezone.utc).isoformat()
    
    return jsonify(note)

@app.route('/api/notes/<int:note_id>', methods=['DELETE'])
def delete_note(note_id):
    global notes
    initial_length = len(notes)
    notes = [n for n in notes if n["id"] != note_id]
    
    if len(notes) < initial_length:
        return jsonify({"message": "Note deleted successfully"})
    else:
        return jsonify({"error": "Note not found"}), 404

if __name__ == '__main__':
    app.run(debug=True)
