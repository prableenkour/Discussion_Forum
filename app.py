from flask import Flask, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_pymongo import PyMongo
from flask_login import (
    LoginManager, UserMixin, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from bson import ObjectId
from datetime import datetime
from markupsafe import Markup
import os

from config import Config
from forms import RegisterForm, LoginForm, ThreadForm, CommentForm, EditProfileForm

# ---------------- APP SETUP ----------------
app = Flask(__name__)
app.config.from_object(Config)
mongo = PyMongo(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'


# ---------------- USER CLASS ----------------
class User(UserMixin):
    def __init__(self, user_doc):
        self.id = str(user_doc['_id'])
        self.username = user_doc['username']
        self.email = user_doc['email']


@login_manager.user_loader
def load_user(user_id):
    user_doc = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    return User(user_doc) if user_doc else None


# ---------------- CONTEXT PROCESSOR ----------------
@app.context_processor
def inject_user_data():
    if current_user.is_authenticated:
        user_doc = mongo.db.users.find_one({'username': current_user.username})
        return dict(current_user_doc=user_doc)
    return dict(current_user_doc=None)


# ---------------- HOME ----------------
@app.route('/')
def home():
    return redirect(url_for('threads'))


# ---------------- AUTH ----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        user = mongo.db.users.find_one({'username': form.username.data})
        email_check = mongo.db.users.find_one({'email': form.email.data})
        if user or email_check:
            flash('Username or email already exists.', 'danger')
            return redirect(url_for('register'))

        hashed_pw = generate_password_hash(form.password.data)
        mongo.db.users.insert_one({
            'username': form.username.data,
            'email': form.email.data,
            'password': hashed_pw,
            'created_at': datetime.utcnow()
        })
        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user_doc = mongo.db.users.find_one({'username': form.username.data})
        if user_doc and check_password_hash(user_doc['password'], form.password.data):
            user = User(user_doc)
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('threads'))
        flash('Invalid username or password.', 'danger')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('login'))


# ---------------- THREADS ----------------
@app.route('/threads')
def threads():
    query = request.args.get('q', '').strip()

    if query:
        all_threads = list(mongo.db.threads.find({
            '$or': [
                {'title': {'$regex': query, '$options': 'i'}},
                {'content': {'$regex': query, '$options': 'i'}},
                {'author_name': {'$regex': query, '$options': 'i'}}
            ]
        }).sort('created_at', -1))
        flash(f"Showing results for '{query}'", 'info')
    else:
        all_threads = list(mongo.db.threads.find().sort('created_at', -1))

    return render_template('threads.html', threads=all_threads, query=query)


# --- AJAX LIVE SEARCH ROUTE ---
@app.route('/search_threads')
def search_threads():
    query = request.args.get('q', '').strip()
    threads_data = []

    if query:
        threads = mongo.db.threads.find({
            '$or': [
                {'title': {'$regex': query, '$options': 'i'}},
                {'content': {'$regex': query, '$options': 'i'}},
                {'author_name': {'$regex': query, '$options': 'i'}}
            ]
        }).sort('created_at', -1)
    else:
        threads = mongo.db.threads.find().sort('created_at', -1)

    for t in threads:
        threads_data.append({
            'id': str(t['_id']),
            'title': t['title'],
            'content': t['content'][:200] + ('...' if len(t['content']) > 200 else ''),
            'author_name': t['author_name'],
            'created_at': t['created_at'].strftime('%Y-%m-%d %H:%M'),
            'score': len(t.get('upvotes', [])) - len(t.get('downvotes', []))
        })

    return jsonify(threads_data)


@app.route('/threads/new', methods=['GET', 'POST'])
@login_required
def new_thread():
    form = ThreadForm()
    if form.validate_on_submit():
        mongo.db.threads.insert_one({
            'title': form.title.data,
            'content': form.content.data,
            'author_id': ObjectId(current_user.id),
            'author_name': current_user.username,
            'created_at': datetime.utcnow(),
            'upvotes': [],
            'downvotes': []
        })
        flash('Thread created successfully!', 'success')
        return redirect(url_for('threads'))
    return render_template('new_thread.html', form=form)


@app.route('/threads/<thread_id>', methods=['GET', 'POST'])
def view_thread(thread_id):
    thread = mongo.db.threads.find_one({'_id': ObjectId(thread_id)})
    if not thread:
        flash('Thread not found.', 'danger')
        return redirect(url_for('threads'))

    form = CommentForm()

    if form.validate_on_submit():
        if not current_user.is_authenticated:
            flash('Please login to comment.', 'warning')
            return redirect(url_for('login'))
        
        mongo.db.comments.insert_one({
            'thread_id': ObjectId(thread_id),
            'content': form.content.data,
            'author_id': ObjectId(current_user.id),
            'author_name': current_user.username,
            'created_at': datetime.utcnow()
        })
        flash('Comment added successfully!', 'success')
        return redirect(url_for('view_thread', thread_id=thread_id))

    comments = list(mongo.db.comments.find({'thread_id': ObjectId(thread_id)}).sort('created_at', 1))
    return render_template('thread_detail.html', thread=thread, comments=comments, form=form)


# ---------------- VOTING ----------------
@app.route('/threads/<thread_id>/upvote', methods=['POST'])
@login_required
def upvote(thread_id):
    try:
        tid = ObjectId(thread_id)
    except Exception:
        flash('Invalid thread id.', 'danger')
        return redirect(url_for('threads'))

    user_oid = ObjectId(current_user.id)
    thread = mongo.db.threads.find_one({'_id': tid})
    if not thread:
        flash('Thread not found.', 'danger')
        return redirect(url_for('threads'))

    # If already upvoted -> remove (toggle). Otherwise remove from downvotes (if present) and add to upvotes.
    # Use $pull and $addToSet to avoid duplicates.
    if any(str(x) == str(user_oid) for x in thread.get('upvotes', [])):
        mongo.db.threads.update_one({'_id': tid}, {'$pull': {'upvotes': user_oid}})
        flash('Upvote removed.', 'info')
    else:
        mongo.db.threads.update_one({'_id': tid}, {'$pull': {'downvotes': user_oid}})
        mongo.db.threads.update_one({'_id': tid}, {'$addToSet': {'upvotes': user_oid}})
        flash('Upvoted.', 'success')

    return redirect(url_for('threads'))


@app.route('/threads/<thread_id>/downvote', methods=['POST'])
@login_required
def downvote(thread_id):
    try:
        tid = ObjectId(thread_id)
    except Exception:
        flash('Invalid thread id.', 'danger')
        return redirect(url_for('threads'))

    user_oid = ObjectId(current_user.id)
    thread = mongo.db.threads.find_one({'_id': tid})
    if not thread:
        flash('Thread not found.', 'danger')
        return redirect(url_for('threads'))

    if any(str(x) == str(user_oid) for x in thread.get('downvotes', [])):
        mongo.db.threads.update_one({'_id': tid}, {'$pull': {'downvotes': user_oid}})
        flash('Downvote removed.', 'info')
    else:
        mongo.db.threads.update_one({'_id': tid}, {'$pull': {'upvotes': user_oid}})
        mongo.db.threads.update_one({'_id': tid}, {'$addToSet': {'downvotes': user_oid}})
        flash('Downvoted.', 'success')

    return redirect(url_for('threads'))


# ---------------- USER PROFILE ----------------
@app.route('/user/<username>')
def user_profile(username):
    user_doc = mongo.db.users.find_one({'username': username})
    if not user_doc:
        abort(404)

    threads = list(mongo.db.threads.find({'author_name': username}).sort('created_at', -1))
    for t in threads:
        up = len(t.get('upvotes', [])) if t.get('upvotes') else 0
        down = len(t.get('downvotes', [])) if t.get('downvotes') else 0
        t['score'] = up - down
        t['comment_count'] = mongo.db.comments.count_documents({'thread_id': t['_id']})

    karma = sum(t['score'] for t in threads)
    comments = list(mongo.db.comments.find({'author_name': username}).sort('created_at', -1).limit(20))

    return render_template('user_profile.html', user_doc=user_doc, threads=threads, comments=comments, karma=karma)


# ---------------- PROFILE EDIT ----------------
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm()
    user_doc = mongo.db.users.find_one({'_id': ObjectId(current_user.id)})

    if form.validate_on_submit():
        update_data = {'bio': form.bio.data}

        if form.avatar.data:
            filename = secure_filename(form.avatar.data.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            form.avatar.data.save(filepath)
            update_data['avatar'] = filename

        mongo.db.users.update_one({'_id': ObjectId(current_user.id)}, {'$set': update_data})
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('user_profile', username=current_user.username))

    form.bio.data = user_doc.get('bio', '')
    return render_template('edit_profile.html', form=form, user_doc=user_doc)


# ---------------- MAIN ----------------
if __name__ == '__main__':
    app.run(debug=True)
