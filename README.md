# Flask Blog

A lightweight Flask-based social blog application with user accounts, posts, replies, likes, favorites, hashtags, profiles, private messaging, admin tools, and file uploads.

## Features

- User signup/login/logout with hashed passwords
- Post messages with image attachments
- Like/unlike and favorite posts
- Reply to posts and edit/delete replies
- Hashtag support with clickable hashtag pages
- User profiles and editable bio/profile picture
- Follow/unfollow users and view a users directory
- Private messaging with optional WebSocket support
- Admin dashboard for managing users, public messages, and private messages
- Admin ban/unban users, delete accounts, messages, and replies
- File upload support for images and profile pictures
- Local JSON storage for users, messages, and private messages

## Requirements

- Python 3.11+ recommended
- Flask
- Werkzeug
- Jinja2
- MarkupSafe
- itsdangerous

Optional:
- `flask-socketio`, `python-socketio`, `python-engineio` for real-time private messaging/WebSocket support
- `gunicorn` for production deployment

## Installation

1. Create a Python virtual environment and activate it:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Ensure the upload folder exists and is writable. By default the app uses `static/uploads`.

## Running the App

From the project root, start the application:

```bash
python FlaskBlog.py
```

The app listens on port `9222` by default.

If `flask-socketio` is installed, the app will run with WebSocket support enabled.

## Environment Variables

- `UPLOAD_FOLDER`: Optional override for the upload directory. Defaults to `static/uploads`.
- `ADMIN_PASSWORD`: Override the default admin password used to access the admin panel.
- `PRIVATE_MSG_KEY`: Optional key for encrypting stored private messages.

## Default Admin Access

- Admin panel password default: `Cot77303`
- Access admin panel at `/admin`

## Data Storage

The app persists data in local JSON files:

- `users.json`
- `messages.json`
- `private_messages.json`

If these files do not exist, they are created automatically.

## App Routes

- `/` - Home feed (requires login)
- `/signup` - Create a new account
- `/login` - Login page
- `/logout` - Log out
- `/profile/<username>` - View a user's public profile
- `/my_profile` - Edit current user's profile
- `/hashtag/<tag>` - View hashtag feed
- `/favorites` - View favorite posts
- `/private_messages` - Private message UI
- `/api/private_messages` - JSON API for private messages
- `/admin` - Admin login/dashboard

## Notes

- The app uses `werkzeug.security` to hash passwords.
- Uploaded image files are restricted to `png`, `jpg`, `jpeg`, and `gif`.
- The app checks for offensive words and HTML tags in messages.
- Private messages are stored encrypted when saved to JSON.

## Development

- Modify templates in `templates/`
- Static assets and JS live in `static/`
- `FlaskBlog.py` contains the full application logic

## License

This repository does not include a specific license file. Add one if you want to clarify reuse terms.
