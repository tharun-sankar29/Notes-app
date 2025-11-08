// State
let notes = [];
let noteToDelete = null;
let editingNoteId = null;

// DOM Elements
const notesList = document.getElementById('notesList');
const searchInput = document.getElementById('searchInput');
const noteTitleInput = document.getElementById('noteTitle');
const noteContentInput = document.getElementById('noteContent');
const confirmModal = document.getElementById('confirmModal');

// Event Listeners
document.addEventListener('DOMContentLoaded', () => {
    loadNotes();
    setupEventListeners();
});

function setupEventListeners() {
    // Search functionality
    searchInput.addEventListener('input', filterNotes);
    
    // Add note on Enter key (Ctrl+Enter to add new line)
    noteInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey && !e.ctrlKey) {
            e.preventDefault();
            addNote();
        }
    });
}

// Format date to readable format
function formatDate(dateString) {
    const options = { 
        year: 'numeric', 
        month: 'short', 
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    return new Date(dateString).toLocaleDateString(undefined, options);
}

// Create note element
function createNoteElement(note) {
    const noteEl = document.createElement('li');
    noteEl.className = 'note-item';
    noteEl.innerHTML = `
        <div class="note-header">
            <h3 class="note-title" data-note-id="${note.id}">${note.title}</h3>
            <button class="delete-btn" data-note-id="${note.id}" title="Delete note">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <div class="note-content">${note.content || '<span class="no-content">No content</span>'}</div>
        <div class="note-actions">
            <span class="note-date" title="Last updated">${formatDate(note.updatedAt)}</span>
        </div>
    `;

    // Add event listeners
    const titleEl = noteEl.querySelector('.note-title');
    const contentEl = noteEl.querySelector('.note-content');
    const deleteBtn = noteEl.querySelector('.delete-btn');
    
    // Handle note click to edit
    noteEl.addEventListener('click', () => {
        // Populate the editor with the note's current content
        noteTitleInput.value = note.title;
        noteContentInput.value = note.content || '';
        
        // Scroll to the editor
        noteTitleInput.focus();
        
        // Update the note when the add button is clicked
        const addButton = document.querySelector('.add-btn');
        const originalOnClick = addButton.onclick;
        
        addButton.onclick = async function() {
            const newTitle = noteTitleInput.value.trim();
            const newContent = noteContentInput.value.trim();
            
            if (!newTitle && !newContent) {
                alert('Please enter a title or content for your note');
                return;
            }
            
            await updateNote(note.id, newTitle, newContent);
            
            // Reset the form and button handler
            noteTitleInput.value = '';
            noteContentInput.value = '';
            addButton.onclick = originalOnClick;
            addButton.innerHTML = '<i class="fas fa-plus"></i> Add Note';
        };
        
        // Update button text
        addButton.innerHTML = '<i class="fas fa-save"></i> Update Note';
    });
    
    // Handle delete button
    deleteBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        showDeleteConfirmation(note.id);
    });

    return noteEl;
}

// Render notes to the DOM
function renderNotes(notesToRender) {
    notesList.innerHTML = '';
    if (notesToRender.length === 0) {
        notesList.innerHTML = '<p class="no-notes">No notes found. Add one above!</p>';
        return;
    }
    
    notesToRender.forEach(note => {
        notesList.appendChild(createNoteElement(note));
    });
}

// Load notes from the server
async function loadNotes() {
    try {
        const res = await fetch('/api/notes');
        notes = await res.json();
        renderNotes(notes);
    } catch (error) {
        console.error('Error loading notes:', error);
        alert('Failed to load notes. Please try again.');
    }
}

// Add a new note
async function addNote() {
    const title = noteTitleInput.value.trim();
    const content = noteContentInput.value.trim();
    
    if (!title && !content) {
        alert('Please enter a title or content for your note');
        return;
    }

    try {
        const response = await fetch('/api/notes', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                title: title || 'Untitled Note',
                content: content
            })
        });
        
        if (response.ok) {
            noteTitleInput.value = '';
            noteContentInput.value = '';
            await loadNotes();
            // Scroll to the newly added note
            const firstNote = notesList.firstChild;
            if (firstNote) {
                firstNote.scrollIntoView({ behavior: 'smooth' });
            }
        } else {
            const error = await response.json();
            throw new Error(error.error || 'Failed to add note');
        }
    } catch (error) {
        console.error('Error adding note:', error);
        alert(error.message || 'Failed to add note. Please try again.');
    }
}

// Update an existing note
async function updateNote(id, title, content) {
    try {
        const response = await fetch(`/api/notes/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                title: title || 'Untitled Note',
                content: content || ''
            })
        });
        
        if (response.ok) {
            await loadNotes();
        } else {
            const error = await response.json();
            throw new Error(error.error || 'Failed to update note');
        }
    } catch (error) {
        console.error('Error updating note:', error);
        alert(error.message || 'Failed to update note. Please try again.');
    }
}

// Show delete confirmation modal
function showDeleteConfirmation(noteId) {
    noteToDelete = noteId;
    confirmModal.style.display = 'flex';
}

// Handle delete confirmation
async function confirmDelete(shouldDelete) {
    confirmModal.style.display = 'none';
    
    if (shouldDelete && noteToDelete) {
        try {
            await deleteNote(noteToDelete);
        } catch (error) {
            console.error('Error deleting note:', error);
            alert('Failed to delete note. Please try again.');
        }
    }
    
    noteToDelete = null;
}

// Delete a note
async function deleteNote(id) {
    try {
        const response = await fetch(`/api/notes/${id}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            await loadNotes();
        } else {
            throw new Error('Failed to delete note');
        }
    } catch (error) {
        console.error('Error deleting note:', error);
        throw error;
    }
}

// Filter notes based on search input
function filterNotes() {
    const searchTerm = searchInput.value.toLowerCase();
    if (!searchTerm) {
        renderNotes(notes);
        return;
    }
    
    const filteredNotes = notes.filter(note => 
        (note.title && note.title.toLowerCase().includes(searchTerm)) ||
        (note.content && note.content.toLowerCase().includes(searchTerm))
    );
    
    renderNotes(filteredNotes);
}

// Make confirmDelete available globally
window.confirmDelete = confirmDelete;

// Initial load
loadNotes();
