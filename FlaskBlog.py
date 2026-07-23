from flask import Flask, request, render_template, redirect, url_for, session, flash, send_from_directory, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import os
import datetime
from datetime import timedelta
from dataclasses import dataclass, field
from typing import List, Optional
import re
from markupsafe import Markup
import uuid
import logging
from itsdangerous import URLSafeSerializer, BadSignature
try:
    from flask_socketio import SocketIO, emit, join_room, leave_room
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    app = None  # Will be set below

app = Flask(__name__)
if SOCKETIO_AVAILABLE:
    socketio = SocketIO(app, cors_allowed_origins="*")
app.secret_key = 'XenoChrome'
app.logger.setLevel(logging.DEBUG)
# Keep users logged in for 7 days by default
app.permanent_session_lifetime = timedelta(days=7)
# Add zip to the template globals
app.jinja_env.globals.update(zip=zip, enumerate=enumerate)

# Base directory for file paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# All the constants should be defined at the top
USER_FILE = os.path.join(BASE_DIR, 'users.json')
MESSAGE_FILE = os.path.join(BASE_DIR, 'messages.json')
PRIVATE_MESSAGES_FILE = os.path.join(BASE_DIR, 'private_messages.json')
# Allow an environment override (useful on PythonAnywhere); default to the app's static/uploads
UPLOAD_FOLDER = os.environ.get('UPLOAD_FOLDER', os.path.join(app.root_path, 'static', 'uploads'))
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
# Admin password (can be overridden via environment variable)
# Default admin password set per user request. For production, override via the ADMIN_PASSWORD env var.
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'Cot77303')
# The Default port for the application
DEFAULT_PORT = 9222

BAD_WORDS = [
    'arse',
    'arsehead',
    'arsehole',
    'ass',
    'asshole',
    'bastard',
    'bitch',
    'bloody',
    'bollocks',
    'brotherfucker',
    'bugger',
    'bullshit',
    'child-fucker',
    'cock',
    'cocksucker',
    'crap',
    'cunt',
    'dammit',
    'damn',
    'damned',
    'dick',
    'dick-head',
    'dickhead',
    'dumb-ass',
    'dumbass',
    'dyke',
    'fag',
    'faggot',
    'father-fucker',
    'fatherfucker',
    'fuck',
    'fucked',
    'fucker',
    'fucking',
    'goddammit',
    'goddamn',
    'Goddamn',
    'goddamned',
    'goddamnit',
    'godsdamn',
    'horseshit',
    'jackarse',
    'jack-ass',
    'jackass',
    'kike',
    'mental',
    'mother-fucker',
    'motherfucker',
    'nigga',
    'nigra',
    'pigfucker',
    'piss',
    'prick',
    'pussy',
    'shit',
    'shite',
    'sisterfuck',
    'sisterfucker',
    'slut',
    'spastic',
    'tranny',
    'twat',
    'wanker'
]
GHAST = ["<p>", 
         "<a>",
         "</a>",
         "</p>"]

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
# Ensure the upload directory exists and is writable by the app
try:
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
except Exception:
    app.logger.exception(f"Could not create upload folder: {app.config['UPLOAD_FOLDER']}")

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# --- Serialization setup for private messages (reversible using itsdangerous) ---
# Use environment variable PRIVATE_MSG_KEY; fall back to app.secret_key
PRIVATE_MSG_KEY = os.environ.get('PRIVATE_MSG_KEY') or app.secret_key
if not PRIVATE_MSG_KEY:
    # Use a fallback dev key but warn the operator
    PRIVATE_MSG_KEY = 'dev-private-msg-key'
    app.logger.warning('PRIVATE_MSG_KEY not set; using fallback key. Set PRIVATE_MSG_KEY env var to persist secret.')

serializer = URLSafeSerializer(PRIVATE_MSG_KEY, salt='private-message-salt')


def encrypt_text(plaintext: str) -> str:
    if plaintext is None:
        return ''
    return serializer.dumps(plaintext)


def decrypt_text(token_str: str) -> str:
    if not token_str:
        return ''
    try:
        return serializer.loads(token_str)
    except BadSignature:
        # Treat as plaintext if signature invalid (backwards-compatibility)
        return token_str

def check_message(message: str) -> bool:
    if any(ghastling in message for ghastling in GHAST):
        flash('Ghast detected!', 'error')
        return False
    elif any(word in message for word in BAD_WORDS):
        flash('Bad words detected!', 'error')
        return False
    elif message.strip() == '':
        flash('Message cannot be empty!', 'error')
        return False
    else: 
        return True

# Add these functions before the route definitions

def extract_mentioned_users(message: str) -> List[str]:
    """Extract usernames that were mentioned in the message."""
    # Find all words that start with @ and remove the @ symbol
    mentions = re.findall(r'@(\w+)', message)
    # Filter out non-existing users, but keep 'all'
    return [username for username in mentions if username == 'all' or username in users]

def send_notifications(mentioned_users: List[str], sender: str, message_index: int) -> None:
    """Send notifications to mentioned users."""
    if 'all' in mentioned_users:
        # Notify all users except the sender
        mentioned_users = [user for user in users.keys() if user != sender]
    # In a real application, you would store these notifications in a database
    # For now, we'll just use the flash message system
    for username in mentioned_users:
        if username in users and username != sender:
            flash(f'You were mentioned by {sender} in a message!', 'info')

@dataclass
class Message:
    username: str
    message: str
    sender: str  # who posted the message (typically same as username, for clarity)
    timestamp: datetime.datetime
    image_filenames: List[str] = field(default_factory=list)
    replies: List[str] = field(default_factory=list)
    liked_by: List[str] = field(default_factory=list)
    hidden_from: List[str] = field(default_factory=list)  # list of usernames who can't see this post

    @property
    def likes(self) -> int:
        return len(self.liked_by)

    def to_dict(self) -> dict:
        return {
            'username': self.username,
            'message': self.message,
            'sender': self.sender,
            'timestamp': self.timestamp.isoformat(),
            'image_filenames': self.image_filenames,
            'replies': self.replies,
            'liked_by': self.liked_by,
            'hidden_from': self.hidden_from
        }

    @classmethod
    def from_dict(cls, data: dict) -> Optional['Message']:
        try:
            return cls(
                username=data.get('username', ''),
                message=data.get('message', ''),
                sender=data.get('sender', ''),
                timestamp=datetime.datetime.fromisoformat(data.get('timestamp', datetime.datetime.now().isoformat())),
                image_filenames=list(data.get('image_filenames', [])),
                replies=list(data.get('replies', [])),
                liked_by=list(data.get('liked_by', [])),
                hidden_from=list(data.get('hidden_from', []))
            )
        except Exception as e:
            app.logger.warning(f"Error loading message from dict: {e}")
            return None

@dataclass
class User:
    username: str
    password: str
    profile_picture: str = ''
    bio: str = ''
    favorites: List[int] = field(default_factory=list)
    following: List[str] = field(default_factory=list)
    followers: List[str] = field(default_factory=list)
    banned: bool = False

    def to_dict(self) -> dict:
        return {
            'username': self.username,
            'password': self.password,
            'profile_picture': self.profile_picture,
            'bio': self.bio,
            'favorites': self.favorites,
            'following': self.following,
            'followers': self.followers,
            'banned': self.banned
        }

    @classmethod
    def from_dict(cls, data: dict) -> Optional['User']:
        try:
            return cls(
                username=data.get('username', ''),
                password=data.get('password', ''),
                profile_picture=data.get('profile_picture', ''),
                bio=data.get('bio', ''),
                favorites=list(data.get('favorites', [])),
                following=list(data.get('following', [])),
                followers=list(data.get('followers', [])),
                banned=bool(data.get('banned', False))
            )
        except Exception as e:
            app.logger.warning(f"Error loading user from dict: {e}")
            return None

import json

def load_users() -> dict:
    users = {}
    if os.path.exists(USER_FILE):
        try:
            with open(USER_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for user_data in data:
                    user = User.from_dict(user_data)
                    if user:
                        users[user.username] = user
        except Exception as e:
            app.logger.warning(f"Error loading users.json: {e}")
    return users

def save_users(users: dict) -> None:
    try:
        with open(USER_FILE, 'w', encoding='utf-8') as f:
            json.dump([user.to_dict() for user in users.values()], f, ensure_ascii=False, indent=2)
    except Exception as e:
        app.logger.error(f"Error saving users.json: {e}")

def load_messages() -> List[Message]:
    messages = []
    if os.path.exists(MESSAGE_FILE):
        try:
            with open(MESSAGE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for msg_data in data:
                    msg = Message.from_dict(msg_data)
                    if msg:
                        messages.append(msg)
        except Exception as e:
            app.logger.warning(f"Error loading messages.json: {e}")
    return messages

def save_messages(messages: List[Message]) -> None:
    try:
        with open(MESSAGE_FILE, 'w', encoding='utf-8') as f:
            json.dump([msg.to_dict() for msg in messages], f, ensure_ascii=False, indent=2)
    except Exception as e:
        app.logger.error(f"Error saving messages.json: {e}")

def load_private_messages() -> List[dict]:
    if not os.path.exists(PRIVATE_MESSAGES_FILE):
        return []
    try:
        with open(PRIVATE_MESSAGES_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            private_messages = []
            for pm in data:
                # Decrypt message if encrypted
                encrypted_msg = pm.get('message', '')
                try:
                    decrypted_msg = decrypt_text(encrypted_msg)
                except Exception:
                    decrypted_msg = encrypted_msg
                pm_copy = dict(pm)
                pm_copy['message'] = decrypted_msg
                private_messages.append(pm_copy)
            return private_messages
    except Exception as e:
        app.logger.warning(f"Error loading private_messages.json: {e}")
        return []

def save_private_messages(private_messages: List[dict]) -> None:
    # Write encrypted messages to JSON file
    out = []
    for msg in private_messages:
        text = msg.get('message', '')
        # Escape newlines for backwards compatibility (not needed in JSON, but for encryption)
        escaped_text = text.replace('\n', '\\n')
        encrypted = encrypt_text(escaped_text)
        out.append({
            'sender': msg.get('sender', ''),
            'receiver': msg.get('receiver', ''),
            'message': encrypted,
            'images': msg.get('images', []) or [],
            'read': bool(msg.get('read', False)),
            'hidden_from': msg.get('hidden_from', []) or msg.get('hide_from', []) or []
        })
    try:
        with open(PRIVATE_MESSAGES_FILE, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
    except Exception as e:
        app.logger.error(f"Error saving private_messages.json: {e}")

def get_notifications_for_user(username):
    """Get notifications for a user by checking message mentions.
    Always loads fresh messages from disk to avoid stale data."""
    all_messages = load_messages()
    return [
        f"You were mentioned by {msg.username} in a message!"
        for msg in all_messages
        if username in msg.message
    ]


def delete_user_account(username_to_delete: str) -> bool:
    """Delete a user and their messages, update other users' favorites accordingly.

    Returns True if deleted, False if user not found or deletion prevented.
    """
    global users, messages

    if username_to_delete not in users:
        return False

    # Prevent deleting the admin account via the UI
    if username_to_delete == 'admin':
        return False

    # Find indices of messages that belong to this user
    indices_to_delete = [i for i, msg in enumerate(messages) if msg.username == username_to_delete]
    if indices_to_delete:
        # Delete any uploaded image files that belong to these messages
        for i in indices_to_delete:
            try:
                msg = messages[i]
                for fname in getattr(msg, 'image_filenames', []):
                    try:
                        path = os.path.join(app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER), fname)
                        if os.path.exists(path):
                            os.remove(path)
                            app.logger.info(f"Deleted image for removed user: {path}")
                    except Exception as e:
                        app.logger.warning(f"Could not delete image file '{fname}' for user '{username_to_delete}': {e}")
            except IndexError:
                # If indices changed or are stale, ignore
                continue

        to_delete_set = set(indices_to_delete)

        # Build mapping from old index -> new index after deletions
        mapping = {}
        new_messages = []
        new_index = 0
        for old_index, msg in enumerate(messages):
            if old_index in to_delete_set:
                mapping[old_index] = None
                continue
            mapping[old_index] = new_index
            new_messages.append(msg)
            new_index += 1

        messages = new_messages

        # Update favorites for all remaining users: remap indices and drop deleted ones
        for u in users.values():
            new_favs = []
            for fav in u.favorites:
                if fav in mapping and mapping[fav] is not None:
                    new_favs.append(mapping[fav])
            # remove duplicates while preserving order
            seen = set()
            cleaned = []
            for f in new_favs:
                if f not in seen:
                    seen.add(f)
                    cleaned.append(f)
            u.favorites = cleaned

    # Finally remove the user
    del users[username_to_delete]

    # Persist changes
    save_messages(messages)
    save_users(users)
    return True

def extract_hashtags(text: str) -> List[str]:
    """Extract all hashtags from text. Returns list of hashtags without the # symbol."""
    hashtags = re.findall(r'#(\w+)', text)
    return list(dict.fromkeys(hashtags))  # Remove duplicates while preserving order

def highlight_hashtags(text: str) -> str:
    """Convert hashtags to clickable links. Returns HTML with hashtag links."""
    def replace_hashtag(match):
        hashtag = match.group(0)  # e.g., "#python"
        return f'<a href="{url_for("view_hashtag", tag=hashtag[1:])}" class="hashtag">{hashtag}</a>'
    
    return re.sub(r'#\w+', replace_hashtag, text)

users = load_users()
messages = load_messages()
private_messages = load_private_messages()

def nl2br(value):
    return Markup(value.replace('\n', '<br>'))

app.jinja_env.filters['nl2br'] = nl2br

def hashtag_links(value):
    """Filter to convert hashtags to links."""
    return Markup(highlight_hashtags(value))

app.jinja_env.filters['hashtag_links'] = hashtag_links

# Add this route before the @app.route('/') definition
@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/')
def home():
    if 'username' in session:
        username = session['username']
        if username in users:
            # Check if user is banned
            if users[username].banned:
                session.pop('username', None)
                flash('Your account has been banned. Please contact an administrator.', 'error')
                return redirect(url_for('login'))
            
            all_messages = load_messages()
            # Create list of messages with their original indices
            messages_with_indices = []
            for idx, msg in enumerate(all_messages):
                if username not in msg.hidden_from:
                    messages_with_indices.append({'message': msg, 'index': idx})
            # Sort by timestamp (newest first)
            messages_with_indices.sort(key=lambda x: x['message'].timestamp, reverse=True)
            # compute unread private messages count
            try:
                all_pms = load_private_messages()
                unread_count = sum(1 for pm in all_pms if pm.get('receiver') == username and not pm.get('read'))
            except Exception:
                unread_count = 0
            return render_template('index.html', messages_with_indices=messages_with_indices, username=username, users=users, unread_count=unread_count)
        else:
            # User exists in session but not in users dictionary
            session.pop('username', None)  # Clear the username from the session
            flash('User account no longer exists. Please log in.', 'error')
            return redirect(url_for('login'))
    return redirect(url_for('login'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users:
            flash('Username already exists!', 'error')
        else:
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            # Initialize the new user's data
            new_user = User(username=username, password=hashed_password)
            users[username] = new_user
            save_users(users)
            session['username'] = username
            flash('Sign-up successful! You are now logged in.', 'success')
            return redirect(url_for('home'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        flash('You are already logged in!', 'error')
        return redirect(url_for('home'))
    else: 
        try:
            if request.method == 'POST':
                username = request.form.get('username', '').strip()
                password = request.form.get('password', '').strip()

                app.logger.info(f"Login attempt: {username}")

                # Load latest users from file
                users_data = load_users()
                user = users_data.get(username)

                if user:
                    # Check if user is banned
                    if user.banned:
                        session.pop('username', None)
                        flash('Your account has been banned. Please contact an administrator.', 'error')
                        return render_template('login.html')
                    
                    try:
                        # Try checking password with werkzeug
                        if check_password_hash(user.password, password):
                            # ✅ Rehash to a supported format if old hash was unsupported
                            if user.password.startswith('scrypt:'):
                                app.logger.info(f"Rehashing old scrypt password for user {username}")
                                user.password = generate_password_hash(password, method='pbkdf2:sha256')
                                users_data[username] = user
                                save_users(users_data)

                            # Make session persistent for the configured lifetime
                            session.permanent = True
                            session['username'] = username
                            flash('Login successful!', 'success')
                            return redirect(url_for('home'))

                        else:
                            session.pop('username', None)
                            flash('Invalid username or password!', 'error')
                            return render_template('login.html')

                    except ValueError:
                        # Unsupported hash (like scrypt)
                        flash('Your password uses an unsupported hash. Please reset your password.', 'error')
                        return render_template('login.html')

                else:
                    session.pop('username', None)
                    flash('Invalid username or password!', 'error')
                    return render_template('login.html')

            # GET request
            return render_template('login.html')

        except Exception:
            import traceback
            error_details = traceback.format_exc()
            app.logger.error(f"Login error:\n{error_details}")
            return f"<h2>Login error occurred</h2><pre>{error_details}</pre>", 500

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('liked_messages', None)  # Clear liked messages on logout
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/profile/<username>')
def profile(username):
    try:
        # === 1️⃣ Load users safely ===
        users = {}
        try:
            users = load_users()
        except Exception as e:
            app.logger.warning(f"Failed to load users: {e}")
            users = {}

        # === 2️⃣ Load all messages safely ===
        all_messages = []
        try:
            all_messages = load_messages()
        except Exception as e:
            app.logger.warning(f"Failed to load messages: {e}")
            all_messages = []

        # === 3️⃣ Filter messages for this user ===
        user_messages = []
        for msg in all_messages:
            if msg.username == username:
                # Ensure timestamp is a datetime
                if not isinstance(msg.timestamp, datetime.datetime):
                    try:
                        msg.timestamp = datetime.datetime.fromisoformat(str(msg.timestamp))
                    except Exception:
                        app.logger.warning(f"Invalid timestamp for {msg.username}; using now() instead.")
                        msg.timestamp = datetime.datetime.now()
                user_messages.append(msg)

        # Sort messages newest → oldest
        user_messages.sort(key=lambda m: m.timestamp, reverse=True)

        # === 4️⃣ Get notifications for this user ===
        def get_notifications_for_user(username):
            try:
                messages_data = load_messages()
                return [
                    f"You were mentioned by {m.username} in a message!"
                    for m in messages_data if username in m.message
                ]
            except Exception as e:
                app.logger.warning(f"Notification load failed: {e}")
                return []

        notifications = get_notifications_for_user(username)

        # === 5️⃣ Find profile image ===
        upload_folder = app.config.get(
            'UPLOAD_FOLDER',
            os.path.join('/home', 'WillliAmYao', 'mysite', 'uploads')
        )
        profile_image = None
        for ext in ['png', 'jpg', 'jpeg', 'gif']:
            possible_path = os.path.join(upload_folder, f"{username}.{ext}")
            if os.path.exists(possible_path):
                profile_image = f"/uploads/{username}.{ext}"
                break

        # === 6️⃣ Render profile page ===
        return render_template(
            'profile.html',
            username=username,
            messages=user_messages,
            notifications=notifications,
            profile_image=profile_image,
            users=users  # ✅ Fix: now Jinja can access 'users'
        )

    except Exception:
        # === 7️⃣ Show full traceback on error (for debugging) ===
        import traceback
        error_details = traceback.format_exc()
        app.logger.error(f"Error rendering profile for {username}:\n{error_details}")
        return f"<h2>Error loading profile for {username}</h2><pre>{error_details}</pre>", 500


@app.route('/hashtag/<tag>')
def view_hashtag(tag):
    """View all messages with a specific hashtag."""
    try:
        # Load all messages
        all_messages = load_messages()
        
        # Filter messages that contain this hashtag
        hashtag_messages = []
        search_tag = f"#{tag.lower()}"
        for msg in all_messages:
            if search_tag in msg.message.lower():
                hashtag_messages.append(msg)
        
        # Reverse to show newest first
        hashtag_messages.reverse()
        
        return render_template(
            'hashtag.html',
            tag=tag,
            messages=hashtag_messages,
            users=users
        )
    except Exception as e:
        app.logger.error(f"Error loading hashtag {tag}: {e}")
        flash(f'Error loading hashtag #{tag}', 'error')
        return redirect(url_for('home'))


@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        old_password = request.form.get('old_password', '')
        new_password = request.form.get('new_password', '')

        # Look up the User object safely
        user_obj = users.get(session['username'])
        if not user_obj:
            flash('User not found. Please log in again.', 'error')
            return redirect(url_for('login'))

        # Use the User object's password attribute (not dict-like access)
        if check_password_hash(user_obj.password, old_password):
            user_obj.password = generate_password_hash(new_password, method='pbkdf2:sha256')
            save_users(users)
            flash('Password changed successfully!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Incorrect old password!', 'error')
    return render_template('change_password.html')

@app.route('/private_messages', methods=['GET', 'POST'])
def private_messages():
    global private_messages
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        receiver = request.form.get('receiver', '').strip()
        message = request.form.get('message', '').strip().replace('\r\n', '\n').replace('\r', '\n')
        sender = session['username']
        if receiver == sender:
            flash('You cannot send a message to yourself!', 'error')
        elif receiver in users:
            # Handle uploaded images for private message
            image_filenames = []
            if 'pm_images' in request.files:
                files = request.files.getlist('pm_images')
                for file in files:
                    if not file or file.filename == '':
                        continue
                    if allowed_file(file.filename):
                        extension = file.filename.rsplit('.', 1)[1].lower()
                        unique_name = f"{uuid.uuid4()}.{extension}"
                        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                        try:
                            file.save(file_path)
                            image_filenames.append(unique_name)
                        except Exception as e:
                            app.logger.error(f"Error saving private message image: {e}")
                            flash('Error uploading private message image!', 'error')
                            return redirect(url_for('private_messages'))
                    else:
                        flash('Invalid file type for private message image.', 'error')
                        return redirect(url_for('private_messages'))
            # Support optional hide_from list submitted as 'hide_from[]'
            hide_list = request.form.getlist('hide_from[]') or []
            private_messages.append({
                'sender': sender,
                'receiver': receiver,
                'message': message,
                'images': image_filenames,
                'read': False,
                'hidden_from': hide_list
            })
            try:
                save_private_messages(private_messages)
                flash('Message sent successfully!', 'success')
            except Exception as e:
                app.logger.warning(f"Private message save failed: {e}")
                flash('Failed to send message.', 'error')
        else:
            flash('User not found!', 'error')
    private_messages = load_private_messages()
    # Attach an `id` (index) to each private message so clients can request deltas
    filtered_messages = []
    for idx, pm in enumerate(private_messages):
        # skip messages hidden from this user
        hidden = pm.get('hidden_from') or pm.get('hide_from') or []
        if session['username'] in hidden:
            continue
        if pm.get('sender') == session['username'] or pm.get('receiver') == session['username']:
            pm_copy = dict(pm)
            pm_copy['id'] = idx
            filtered_messages.append(pm_copy)
    
    # Sort messages newest-first by ID (higher ID = newer message)
    filtered_messages.sort(key=lambda x: x['id'], reverse=True)

    # Mark messages as read for this user (messages where receiver==current user), but skip hidden ones
    changed = False
    for pm in private_messages:
        if pm.get('receiver') == session['username'] and not pm.get('read'):
            hidden = pm.get('hidden_from') or pm.get('hide_from') or []
            if session['username'] in hidden:
                continue
            pm['read'] = True
            changed = True
    if changed:
        try:
            save_private_messages(private_messages)
        except Exception as e:
            app.logger.error(f"Failed to save private messages when marking read: {e}")

    return render_template('private_messages.html', messages=filtered_messages, users=users)


@app.route('/api/private_messages', methods=['GET', 'POST'])
def api_private_messages():
    # JSON API to fetch or send private messages for the logged-in user.
    if 'username' not in session:
        return jsonify({'error': 'unauthorized'}), 401
    
    username = session['username']
    
    # GET: Fetch messages
    if request.method == 'GET':
        all_pms = load_private_messages()
        items = []
        for idx, pm in enumerate(all_pms):
            if pm.get('sender') == username or pm.get('receiver') == username:
                pm_copy = dict(pm)
                pm_copy['id'] = idx
                items.append(pm_copy)
        # Sort newest-first by index
        items.sort(key=lambda x: x['id'], reverse=True)
        # Optional since_id param: return only messages with id > since_id
        since_id = request.args.get('since_id')
        if since_id is not None:
            try:
                since_id = int(since_id)
                items = [it for it in items if it['id'] > since_id]
            except Exception:
                pass
        return jsonify(items)
    
    # POST: Send a new message via JSON
    if request.method == 'POST':
        data = request.get_json() or {}
        receiver = data.get('receiver', '').strip()
        message = data.get('message', '').strip().replace('\r\n', '\n').replace('\r', '\n')
        hide_from = data.get('hide_from', []) or []
        
        if not receiver or not message:
            return jsonify({'error': 'receiver and message required'}), 400
        
        if receiver == username:
            return jsonify({'error': 'cannot send message to yourself'}), 400
        
        if receiver not in users:
            return jsonify({'error': 'user not found'}), 404
        
        # No file uploads via JSON API (to keep it simple); images must use form POST
        all_pms = load_private_messages()
        all_pms.append({
            'sender': username,
            'receiver': receiver,
            'message': message,
            'images': [],
            'read': False,
            'hidden_from': hide_from
        })
        try:
            save_private_messages(all_pms)
            # Emit WebSocket event if available
            if SOCKETIO_AVAILABLE:
                socketio.emit('new_pm', {
                    'sender': username,
                    'receiver': receiver,
                    'message': message
                }, room=receiver)
            return jsonify({'status': 'success', 'message': 'Message sent'}), 201
        except Exception as e:
            app.logger.error(f"Error sending PM via JSON API: {e}")
            return jsonify({'error': 'failed to send message'}), 500


@app.context_processor
def inject_unread_count():
    """Provide `unread_count` to templates for navbar badge."""
    try:
        username = session.get('username')
        if not username:
            return dict(unread_count=0)
        all_pms = load_private_messages()
        unread = sum(1 for pm in all_pms if pm.get('receiver') == username and not pm.get('read'))
        return dict(unread_count=unread)
    except Exception:
        return dict(unread_count=0)

@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/admin', methods=['GET', 'POST'])
def admin_panel():
    # If session has admin flag, show admin dashboard
    if session.get('is_admin'):
        user_list = [{'username': u.username, 'profile_picture': u.profile_picture, 'bio': u.bio, 'banned': u.banned} for u in users.values()]
        return render_template('admin.html', users_list=user_list)

    # If POSTed password, validate
    if request.method == 'POST':
        password = request.form.get('admin_password', '')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            flash('Admin access granted.', 'success')
            user_list = [{'username': u.username, 'profile_picture': u.profile_picture, 'bio': u.bio, 'banned': u.banned} for u in users.values()]
            return render_template('admin.html', users_list=user_list)
        else:
            flash('Incorrect admin password.', 'error')

    # Render admin login form
    return render_template('admin_login.html')



@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    flash('Admin logged out.', 'success')
    return redirect(url_for('home'))


@app.route('/admin/messages')
def admin_messages():
    if not session.get('is_admin'):
        flash('Access denied: admin only.', 'error')
        return redirect(url_for('admin_panel'))
    all_messages = load_messages()
    # provide indices to allow deletion
    indexed = list(enumerate(all_messages))
    return render_template('admin_messages.html', messages=indexed)


@app.route('/admin/delete_message/<int:message_index>', methods=['POST'])
def admin_delete_message(message_index):
    if not session.get('is_admin'):
        flash('Access denied: admin only.', 'error')
        return redirect(url_for('admin_panel'))
    global messages
    if 0 <= message_index < len(messages):
        # delete any uploaded image files associated with this message
        try:
            msg_to_delete = messages[message_index]
            for fname in getattr(msg_to_delete, 'image_filenames', []):
                try:
                    path = os.path.join(app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER), fname)
                    if os.path.exists(path):
                        os.remove(path)
                        app.logger.info(f"Deleted image file for admin-deleted message: {path}")
                except Exception as e:
                    app.logger.warning(f"Failed to delete image '{fname}' when removing message {message_index}: {e}")
        except IndexError:
            pass

        # remove message
        del messages[message_index]
        save_messages(messages)
        # update favorites for all users (remove any favorites pointing to this index and remap higher indices)
        for u in users.values():
            new_favs = []
            for fav in u.favorites:
                if fav == message_index:
                    continue
                elif fav > message_index:
                    new_favs.append(fav - 1)
                else:
                    new_favs.append(fav)
            u.favorites = new_favs
        save_users(users)
        flash('Message deleted.', 'success')
    else:
        flash('Invalid message index.', 'error')
    return redirect(url_for('admin_messages'))


@app.route('/admin/delete_reply/<int:message_index>/<int:reply_index>', methods=['POST'])
def admin_delete_reply(message_index, reply_index):
    if not session.get('is_admin'):
        flash('Access denied: admin only.', 'error')
        return redirect(url_for('admin_panel'))
    global messages
    if 0 <= message_index < len(messages):
        msg = messages[message_index]
        if 0 <= reply_index < len(msg.replies):
            del msg.replies[reply_index]
            save_messages(messages)
            flash('Reply deleted.', 'success')
        else:
            flash('Invalid reply index.', 'error')
    else:
        flash('Invalid message index.', 'error')
    return redirect(url_for('admin_messages'))


@app.route('/admin/private_messages')
def admin_private_messages():
    if not session.get('is_admin'):
        flash('Access denied: admin only.', 'error')
        return redirect(url_for('admin_panel'))
    pm = load_private_messages()
    indexed = list(enumerate(pm))
    return render_template('admin_private_messages.html', private_messages=indexed)


@app.route('/admin/delete_private/<int:pm_index>', methods=['POST'])
def admin_delete_private(pm_index):
    if not session.get('is_admin'):
        flash('Access denied: admin only.', 'error')
        return redirect(url_for('admin_panel'))
    pms = load_private_messages()
    if 0 <= pm_index < len(pms):
        del pms[pm_index]
        try:
            save_private_messages(pms)
            flash('Private message deleted.', 'success')
        except ValueError as e:
            app.logger.error(f"Failed to save private messages after deletion: {e}")
            flash('Private message deleted, but failed to update storage.', 'warning')
    else:
        flash('Invalid private message index.', 'error')
    return redirect(url_for('admin_private_messages'))


@app.route('/admin/delete/<username_to_delete>', methods=['POST'])
def admin_delete_user(username_to_delete):
    # Allow access if admin panel flag is set. The admin dashboard sets
    # `session['is_admin'] = True` (without changing session['username']),
    # so check that flag here rather than requiring the username to be 'admin'.
    if not session.get('is_admin'):
        flash('Access denied: admin only.', 'error')
        return redirect(url_for('admin_panel'))

    if username_to_delete == 'admin':
        flash('Cannot delete admin account.', 'error')
        return redirect(url_for('admin_panel'))

    deleted = delete_user_account(username_to_delete)
    if deleted:
        flash(f'User {username_to_delete} deleted successfully.', 'success')
    else:
        flash(f'User {username_to_delete} could not be deleted or does not exist.', 'error')
    return redirect(url_for('admin_panel'))


@app.route('/admin/ban/<username_to_ban>', methods=['POST'])
def admin_ban_user(username_to_ban):
    """Ban a user from accessing the site."""
    if not session.get('is_admin'):
        flash('Access denied: admin only.', 'error')
        return redirect(url_for('admin_panel'))

    if username_to_ban == 'admin':
        flash('Cannot ban admin account.', 'error')
        return redirect(url_for('admin_panel'))

    if username_to_ban not in users:
        flash(f'User {username_to_ban} not found.', 'error')
        return redirect(url_for('admin_panel'))

    users[username_to_ban].banned = True
    save_users(users)
    
    # If the banned user is currently logged in, log them out
    if session.get('username') == username_to_ban:
        session.pop('username', None)
    
    flash(f'User {username_to_ban} has been banned.', 'success')
    return redirect(url_for('admin_panel'))


@app.route('/admin/unban/<username_to_unban>', methods=['POST'])
def admin_unban_user(username_to_unban):
    """Unban a user, allowing them to access the site again."""
    if not session.get('is_admin'):
        flash('Access denied: admin only.', 'error')
        return redirect(url_for('admin_panel'))

    if username_to_unban not in users:
        flash(f'User {username_to_unban} not found.', 'error')
        return redirect(url_for('admin_panel'))

    users[username_to_unban].banned = False
    save_users(users)
    flash(f'User {username_to_unban} has been unbanned.', 'success')
    return redirect(url_for('admin_panel'))

def check_user_banned():
    """Helper function to check if current user is banned and log them out if so."""
    if 'username' in session:
        username = session['username']
        if username in users and users[username].banned:
            session.pop('username', None)
            flash('Your account has been banned. Please contact an administrator.', 'error')
            return True
    return False

@app.route('/post', methods=['POST'])
def post():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    if check_user_banned():
        return redirect(url_for('login'))

    message_text = request.form.get('message', '').replace('\r\n', '\n').replace('\r', '\n')

    # Debug logging
    app.logger.info(f"Received form data: {request.form}")
    app.logger.info(f"Received files: {request.files}")

    # Support multiple image uploads (input name="images" and multiple allowed)
    image_filenames = []
    if 'images' in request.files:
        files = request.files.getlist('images')
        for file in files:
            if not file or file.filename == '':
                continue
            app.logger.info(f"Received file: {file.filename}")
            if allowed_file(file.filename):
                extension = file.filename.rsplit('.', 1)[1].lower()
                unique_name = f"{uuid.uuid4()}.{extension}"
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
                try:
                    file.save(file_path)
                    app.logger.info(f"Successfully saved image to {file_path}")
                    image_filenames.append(unique_name)
                except Exception as e:
                    app.logger.error(f"Error saving file: {str(e)}")
                    flash('Error uploading image!', 'error')
                    return redirect(url_for('home'))
                if not check_message(message_text):
                    return redirect(url_for('home'))
            else:
                flash('Invalid file type. Only PNG, JPG, JPEG, and GIF files are allowed.', 'error')
                return redirect(url_for('home')) 
        if not check_message(message_text):
            return redirect(url_for('home'))

    new_message = Message(
        username=session['username'],
        message=message_text,
        sender=session['username'],
        timestamp=datetime.datetime.now(),
        image_filenames=image_filenames,
        hidden_from=request.form.getlist('hidden_from')  # Get list of users to hide from
    )

    messages.append(new_message)
    save_messages(messages)

    app.logger.info(f"Created new message with images: {image_filenames}")
    flash('Message posted successfully!', 'success')
    return redirect(url_for('home'))

@app.route('/like/<int:message_index>', methods=['POST'])
def like_message(message_index):
    global messages  # Declare global FIRST
    
    if 'username' not in session:
        flash('Please log in to like messages.', 'error')
        return redirect(url_for('login'))

    # Reload messages to ensure we have the latest data
    messages = load_messages()

    if message_index < 0 or message_index >= len(messages):
        flash('Invalid message!', 'error')
        return redirect(url_for('home'))

    username = session['username']
    msg = messages[message_index]
    
    # SECURITY: Check if user can see this message (not hidden from them)
    if username in msg.hidden_from:
        flash('You cannot like a message hidden from you!', 'error')
        app.logger.warning(f"User {username} attempted to like hidden message {message_index}")
        return redirect(url_for('home'))
    
    # Log for debugging
    app.logger.info(f"User {username} attempting to like message index {message_index}")
    app.logger.info(f"Current liked_by for this message: {msg.liked_by}")

    # Check if user already liked this message
    if username in msg.liked_by:
        # Unlike functionality
        msg.liked_by.remove(username)
        flash('Message unliked!', 'info')
        if 'liked_messages' in session and message_index in session['liked_messages']:
            session['liked_messages'].remove(message_index)
            session.modified = True
    else:
        # Like the message
        msg.liked_by.append(username)
        flash('Message liked!', 'success')
        # Update session tracking for UI purposes
        if 'liked_messages' not in session:
            session['liked_messages'] = []
        if message_index not in session['liked_messages']:
            session['liked_messages'].append(message_index)
            session.modified = True

    # Save and log
    save_messages(messages)
    app.logger.info(f"After like/unlike, liked_by: {msg.liked_by}")
    app.logger.info(f"Saved {len(messages)} messages to file")
    
    return redirect(url_for('home'))

@app.route('/favorite/<int:message_index>', methods=['POST'])
def favorite_message(message_index):
    if 'username' not in session or message_index < 0 or message_index >= len(messages):
        return redirect(url_for('home'))

    username = session['username']
    user = users[username]
    if message_index not in user.favorites:
        user.favorites.append(message_index)
        flash('Message added to favorites!', 'success')
    else:
        flash('Message is already in favorites!', 'info')

    save_users(users)
    return redirect(url_for('home'))

@app.route('/favorites')
def favorites():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user = users[username]

    # Create a list of valid messages and their indices
    favorite_messages = []
    valid_indices = []
    for idx in user.favorites:
        if 0 <= idx < len(messages):
            favorite_messages.append(messages[idx])
            valid_indices.append(idx)

    # Update favorites list to only include valid indices
    user.favorites = valid_indices
    save_users(users)

    return render_template('favorites.html', messages=favorite_messages, username=username, indices=valid_indices, users=users)

@app.route('/unfavorite/<int:message_index>', methods=['POST'])
def unfavorite_message(message_index):
    print('unfavorite_message called')
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    user = users[username]
    source = request.args.get('source', 'home')  # Get source parameter, default to 'home'

    print('user.favorites:', user.favorites)
    print('message_index:', message_index)

    if message_index in user.favorites:
        user.favorites.remove(message_index)
        save_users(users)
        flash('Message removed from favorites!', 'success')
    else:
        flash('Message was not in favorites!', 'info')

    # Redirect based on source
    if source == 'favorites':
        return redirect(url_for('favorites'))
    return redirect(request.referrer or url_for('home'))

@app.route('/reply/<int:message_index>', methods=['POST'])
def reply(message_index):
    if 'username' not in session:
        flash('Please log in to reply.', 'error')
        return redirect(url_for('login'))

    if message_index < 0 or message_index >= len(messages):
        flash('Invalid message index!', 'error')
        return redirect(url_for('home'))

    reply_text = request.form.get('reply', '').strip().replace('\r\n', '\n').replace('\r', '\n')

    if not check_message(reply_text):
        return redirect(url_for('home'))

    if not reply_text:
        flash('Reply cannot be empty!', 'error')
        return redirect(url_for('home'))
    
    if check_user_banned():
        return redirect(url_for('login'))

    username = session['username']
    reply_with_user = f"{username}: {reply_text}"

    try:
        messages[message_index].replies.append(reply_with_user)
        save_messages(messages)
        flash('Reply posted successfully!', 'success')
    except Exception as e:
        app.logger.error(f"Error posting reply: {str(e)}")
        flash('Error posting reply!', 'error')

    return redirect(url_for('home'))

@app.route('/delete/<int:message_index>', methods=['POST'])
def delete_message(message_index):
    """Delete a message if the user is the owner."""
    global messages
    
    if 'username' not in session:
        flash('Please log in to delete messages.', 'error')
        return redirect(url_for('login'))

    # Reload messages to ensure we have the latest data
    messages = load_messages()

    if message_index < 0 or message_index >= len(messages):
        flash('Invalid message!', 'error')
        return redirect(url_for('home'))

    username = session['username']
    msg = messages[message_index]

    # Check if the user is the owner or admin
    if msg.username != username and session.get('username') != 'admin':
        flash('You can only delete your own messages!', 'error')
        return redirect(url_for('home'))

    # Delete any uploaded image files
    try:
        for fname in getattr(msg, 'image_filenames', []):
            try:
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], fname)
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                app.logger.error(f"Could not delete image file {fname}: {e}")
    except Exception as e:
        app.logger.error(f"Error deleting images: {e}")

    # Remove from favorites for all users
    for u in users.values():
        if message_index in u.favorites:
            u.favorites.remove(message_index)

    # Delete the message
    del messages[message_index]

    # Remap favorites indices for all users (indices after deletion shift down)
    for u in users.values():
        new_favs = []
        for fav in u.favorites:
            if fav > message_index:
                new_favs.append(fav - 1)
            else:
                new_favs.append(fav)
        u.favorites = new_favs

    save_messages(messages)
    save_users(users)
    flash('Message deleted successfully!', 'success')
    return redirect(url_for('home'))

@app.route('/edit/<int:message_index>', methods=['GET', 'POST'])
def edit_message(message_index):
    """Edit a message if the user is the owner."""
    global messages
    
    if 'username' not in session:
        flash('Please log in to edit messages.', 'error')
        return redirect(url_for('login'))

    # Reload messages to ensure we have the latest data
    messages = load_messages()

    if message_index < 0 or message_index >= len(messages):
        flash('Invalid message!', 'error')
        return redirect(url_for('home'))

    username = session['username']
    msg = messages[message_index]

    # Check if the user is the owner
    if msg.username != username:
        flash('You can only edit your own messages!', 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        new_text = request.form.get('message', '').replace('\r\n', '\n').replace('\r', '\n')
        
        if not new_text:
            flash('Message cannot be empty!', 'error')
            return redirect(url_for('home'))

        # Update the message text
        messages[message_index].message = new_text
        save_messages(messages)
        flash('Message edited successfully!', 'success')
        return redirect(url_for('home'))

    # GET request - show edit form
    return render_template('edit_message.html', message=msg, message_index=message_index)

@app.route('/delete_reply/<int:message_index>/<int:reply_index>', methods=['POST'])
def delete_reply(message_index, reply_index):
    """Delete a reply if the user is the owner of that reply."""
    global messages
    
    if 'username' not in session:
        flash('Please log in to delete replies.', 'error')
        return redirect(url_for('login'))

    # Reload messages to ensure we have the latest data
    messages = load_messages()

    if message_index < 0 or message_index >= len(messages):
        flash('Invalid message!', 'error')
        return redirect(url_for('home'))

    msg = messages[message_index]
    if reply_index < 0 or reply_index >= len(msg.replies):
        flash('Invalid reply!', 'error')
        return redirect(url_for('home'))

    username = session['username']
    reply_text = msg.replies[reply_index]
    
    # Extract the reply author from the "username: text" format
    if ': ' in reply_text:
        reply_author = reply_text.split(': ', 1)[0]
    else:
        reply_author = ''

    # Check if the user is the owner of this reply
    if reply_author != username:
        flash('You can only delete your own replies!', 'error')
        return redirect(url_for('home'))

    # Delete the reply
    del msg.replies[reply_index]
    save_messages(messages)
    flash('Reply deleted successfully!', 'success')
    return redirect(request.referrer or url_for('home'))

@app.route('/edit_reply/<int:message_index>/<int:reply_index>', methods=['GET', 'POST'])
def edit_reply(message_index, reply_index):
    """Edit a reply if the user is the owner of that reply."""
    global messages
    
    if 'username' not in session:
        flash('Please log in to edit replies.', 'error')
        return redirect(url_for('login'))

    # Reload messages to ensure we have the latest data
    messages = load_messages()

    if message_index < 0 or message_index >= len(messages):
        flash('Invalid message!', 'error')
        return redirect(url_for('home'))

    msg = messages[message_index]
    if reply_index < 0 or reply_index >= len(msg.replies):
        flash('Invalid reply!', 'error')
        return redirect(url_for('home'))

    username = session['username']
    reply_text = msg.replies[reply_index]
    
    # Extract the reply author and text from the "username: text" format
    if ': ' in reply_text:
        reply_author, reply_content = reply_text.split(': ', 1)
    else:
        reply_author = ''
        reply_content = reply_text

    # Check if the user is the owner of this reply
    if reply_author != username:
        flash('You can only edit your own replies!', 'error')
        return redirect(url_for('home'))

    if request.method == 'POST':
        new_reply_text = request.form.get('reply', '').strip().replace('\r\n', '\n').replace('\r', '\n')
        
        if not new_reply_text:
            flash('Reply cannot be empty!', 'error')
            return redirect(request.referrer or url_for('home'))

        # Update the reply with the new text
        msg.replies[reply_index] = f"{username}: {new_reply_text}"
        save_messages(messages)
        flash('Reply edited successfully!', 'success')
        return redirect(request.referrer or url_for('home'))

    # GET request - show edit form
    return render_template('edit_reply.html', message_index=message_index, reply_index=reply_index, 
                           reply_content=reply_content, reply_author=reply_author)

@app.route('/my_profile', methods=['GET', 'POST'])
def my_profile():
    global users, messages
    
    if 'username' not in session:
        return redirect(url_for('login'))
    
    username = session['username']
    if username not in users:
        flash('User not found.', 'error')
        return redirect(url_for('login'))
    
    user = users[username]
    
    if request.method == 'POST':
        # Handle bio update
        bio = request.form.get('bio', '').strip()
        if not check_message(bio):
            return redirect(url_for('my_profile'))
        else: 
            print('bio is valid')
            user.bio = bio
        
        # Handle profile picture upload
        if 'profile_picture' in request.files:
            file = request.files['profile_picture']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    extension = file.filename.rsplit('.', 1)[1].lower()
                    # Delete old profile picture if exists
                    for ext in ['png', 'jpg', 'jpeg', 'gif']:
                        old_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{username}.{ext}")
                        if os.path.exists(old_path):
                            try:
                                os.remove(old_path)
                            except Exception as e:
                                app.logger.warning(f"Could not delete old profile picture: {e}")
                    
                    # Save new profile picture
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{username}.{extension}")
                    try:
                        file.save(file_path)
                        user.profile_picture = f"{username}.{extension}"
                    except Exception as e:
                        app.logger.error(f"Error saving profile picture: {e}")
                        flash('Error uploading profile picture!', 'error')
                        return redirect(url_for('my_profile'))
                else:
                    flash('Invalid file type. Only PNG, JPG, JPEG, and GIF files are allowed.', 'error')
                    return redirect(url_for('my_profile'))
        
        save_users(users)
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('my_profile'))
    
    # GET request - load user's messages
    all_messages = load_messages()
    user_messages = [msg for msg in all_messages if msg.username == username]
    user_messages.sort(key=lambda m: m.timestamp, reverse=True)
    
    # Find profile image
    profile_image = None
    for ext in ['png', 'jpg', 'jpeg', 'gif']:
        possible_path = os.path.join(app.config.get('UPLOAD_FOLDER', UPLOAD_FOLDER), f"{username}.{ext}")
        if os.path.exists(possible_path):
            profile_image = f"/uploads/{username}.{ext}"
            break
    
    return render_template('my_profile.html', user=user, messages=user_messages, profile_image=profile_image, users=users)

@app.route('/users')
def users_directory():
    if 'username' not in session:
        return redirect(url_for('login'))
    
    # Load users and sort by follower count (descending)
    user_list = sorted(users.values(), key=lambda u: len(u.followers), reverse=True)
    current_user = session['username']
    
    return render_template('users_directory.html', user_list=user_list, current_user=current_user, users=users)

@app.route('/follow/<username>', methods=['POST'])
def follow_user(username):
    global users
    
    if 'username' not in session:
        flash('Please log in to follow users.', 'error')
        return redirect(url_for('login'))
    
    current_user = session['username']
    
    # Prevent following yourself
    if current_user == username:
        flash('You cannot follow yourself!', 'error')
        return redirect(request.referrer or url_for('users_directory'))
    
    # Check if target user exists
    if username not in users:
        flash('User not found!', 'error')
        return redirect(request.referrer or url_for('users_directory'))
    
    # Add current user to target user's followers
    if current_user not in users[username].followers:
        users[username].followers.append(current_user)
    
    # Add target user to current user's following
    if username not in users[current_user].following:
        users[current_user].following.append(username)
    
    save_users(users)
    flash(f'You are now following {username}!', 'success')
    return redirect(request.referrer or url_for('users_directory'))

@app.route('/unfollow/<username>', methods=['POST'])
def unfollow_user(username):
    global users
    
    if 'username' not in session:
        flash('Please log in to unfollow users.', 'error')
        return redirect(url_for('login'))
    
    current_user = session['username']
    
    # Check if target user exists
    if username not in users:
        flash('User not found!', 'error')
        return redirect(request.referrer or url_for('users_directory'))
    
    # Remove current user from target user's followers
    if current_user in users[username].followers:
        users[username].followers.remove(current_user)
    
    # Remove target user from current user's following
    if username in users[current_user].following:
        users[current_user].following.remove(username)
    
    save_users(users)
    flash(f'You have unfollowed {username}.', 'success')
    return redirect(request.referrer or url_for('users_directory'))

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404


# ==================== WebSocket Event Handlers ====================
# These handlers are only active if flask-socketio is installed.

if SOCKETIO_AVAILABLE:
    @socketio.on('connect')
    def handle_connect():
        """Handle WebSocket client connection."""
        if 'username' in session:
            username = session['username']
            # Join a room named after the user to receive messages targeted to them
            join_room(username)
            app.logger.debug(f'User {username} connected to WebSocket')
            emit('connection', {'data': 'Connected to PM server'})
        else:
            app.logger.debug('Anonymous client connected (no session)')

    @socketio.on('disconnect')
    def handle_disconnect():
        """Handle WebSocket client disconnection."""
        if 'username' in session:
            username = session['username']
            leave_room(username)
            app.logger.debug(f'User {username} disconnected from WebSocket')

    @socketio.on('join_pm_room')
    def on_join_pm_room(data):
        """Join a specific PM conversation room (optional for future direct messaging)."""
        if 'username' not in session:
            return False
        room = data.get('room')
        username = session['username']
        if room:
            join_room(room)
            app.logger.debug(f'User {username} joined PM room {room}')
            emit('message', {'data': f'{username} has joined the PM room'}, room=room)

    @socketio.on('send_pm')
    def on_send_pm(data):
        """Handle incoming PM via WebSocket (alternative to REST API)."""
        if 'username' not in session:
            emit('error', {'message': 'unauthorized'})
            return
        
        if check_user_banned():
            emit('error', {'message': 'banned user'})
            return
        
        username = session['username']
        receiver = data.get('receiver', '').strip()
        message = data.get('message', '').strip()
        hide_from = data.get('hide_from', []) or []
        
        if not receiver or not message:
            emit('error', {'message': 'receiver and message required'})
            return
        
        if receiver == username:
            emit('error', {'message': 'cannot send message to yourself'})
            return
        
        if receiver not in users:
            emit('error', {'message': 'user not found'})
            return
        
        # Save the message
        try:
            all_pms = load_private_messages()
            all_pms.append({
                'sender': username,
                'receiver': receiver,
                'message': message,
                'images': [],
                'read': False,
                'hidden_from': hide_from
            })
            save_private_messages(all_pms)
            
            # Emit event to receiver
            emit('new_pm', {
                'sender': username,
                'receiver': receiver,
                'message': message,
                'timestamp': datetime.datetime.now().isoformat()
            }, room=receiver)
            
            # Confirm to sender
            emit('pm_sent', {'status': 'success', 'receiver': receiver})
        except Exception as e:
            app.logger.error(f"Error handling PM via WebSocket: {e}")
            emit('error', {'message': 'failed to send message'})

if __name__ == '__main__':
    if SOCKETIO_AVAILABLE:
        socketio.run(app, host="0.0.0.0", port=DEFAULT_PORT, debug=True)
    else:
        app.run(host="0.0.0.0", port=DEFAULT_PORT, debug=True)
