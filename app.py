import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
# ADD 'g' to the import statement
from flask import Flask, render_template, request, redirect, url_for, flash, session, get_flashed_messages, g

app = Flask(__name__)
app.secret_key = "supersecretkey"

# Database Initialization and Schema Update
def init_db():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    c.execute('''
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            comment TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (post_id) REFERENCES posts(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()

init_db()

# User authentication logic
@app.before_request
def load_logged_in_user():
    user_id = session.get('user_id')
    if user_id is None:
        g.user = None # CHANGED from app.g.user
    else:
        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT id, username FROM users WHERE id = ?", (user_id,))
        g.user = c.fetchone() # CHANGED from app.g.user
        conn.close()

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        error = None

        if not username:
            error = "Username is required."
        elif not password:
            error = "Password is required."

        if error is None:
            conn = sqlite3.connect("database.db")
            c = conn.cursor()
            try:
                hashed_password = generate_password_hash(password)
                c.execute(
                    "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                    (username, hashed_password)
                )
                conn.commit()
            except sqlite3.IntegrityError:
                error = f"User {username} is already registered."
            finally:
                conn.close()

            if error is None:
                flash("Registration successful! You can now log in.", "success")
                return redirect(url_for("login"))
        
        flash(error, "error")

    return render_template("register.html", messages=get_flashed_messages())

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        error = None

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
        user = c.fetchone()
        conn.close()

        if user is None:
            error = "Incorrect username."
        elif not check_password_hash(user[2], password):
            error = "Incorrect password."

        if error is None:
            session.clear()
            session['user_id'] = user[0]
            flash(f"Welcome back, {user[1]}!", "success")
            return redirect(url_for("home"))
        
        flash(error, "error")

    return render_template("login.html", messages=get_flashed_messages())

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("home"))

# Home Page - View all posts (with Pagination)
@app.route("/")
def home():
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    posts_per_page = 5
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * posts_per_page

    c.execute("SELECT COUNT(id) FROM posts")
    total_posts = c.fetchone()[0]
    total_pages = (total_posts + posts_per_page - 1) // posts_per_page

    c.execute("""
        SELECT p.id, p.title, p.content, p.created_at, p.updated_at, u.username, u.id
        FROM posts p JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """, (posts_per_page, offset))
    posts = c.fetchall()
    conn.close()

    return render_template("index.html",
                           posts=posts,
                           messages=get_flashed_messages(),
                           page=page,
                           total_pages=total_pages)

# NEW ROUTE FOR AUTHOR PROFILE
@app.route("/user/<int:user_id>")
def user_posts(user_id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    # Get the username for the profile page header
    c.execute("SELECT username FROM users WHERE id = ?", (user_id,))
    user = c.fetchone()
    if not user:
        conn.close()
        flash("User not found.", "error")
        return redirect(url_for("home"))
    
    username = user[0]

    # Pagination for user's posts
    posts_per_page = 5 # You can use the same or a different number here
    page = request.args.get('page', 1, type=int)
    offset = (page - 1) * posts_per_page

    # Get total number of posts by this user
    c.execute("SELECT COUNT(id) FROM posts WHERE user_id = ?", (user_id,))
    total_posts = c.fetchone()[0]
    total_pages = (total_posts + posts_per_page - 1) // posts_per_page

    # Fetch posts by this user for the current page
    c.execute("""
        SELECT p.id, p.title, p.content, p.created_at, p.updated_at, u.username, u.id
        FROM posts p JOIN users u ON p.user_id = u.id
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """, (user_id, posts_per_page, offset))
    posts = c.fetchall()
    conn.close()

    return render_template("user_profile.html",
                           username=username,
                           posts=posts,
                           messages=get_flashed_messages(),
                           page=page,
                           total_pages=total_pages,
                           user_id=user_id) # Pass user_id for pagination links

# Other routes (No changes here unless specified)
@app.route("/new", methods=["GET", "POST"])
def new_post():
    if g.user is None: # CHANGED from app.g.user
        flash("You need to log in to create a post.", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form["title"]
        content = request.form["content"]
        current_time = datetime.now().strftime("%Y-%m-%m %H:%M:%S")
        user_id = g.user[0] # CHANGED from app.g.user

        conn = sqlite3.connect("database.db")
        c = conn.cursor()
        c.execute("INSERT INTO posts (user_id, title, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                  (user_id, title, content, current_time, current_time))
        conn.commit()
        conn.close()

        flash("Post created successfully!", "success")
        return redirect(url_for("home"))

    return render_template("new_post.html", messages=get_flashed_messages())

@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def post_detail(post_id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("""
        SELECT p.id, p.title, p.content, p.created_at, p.updated_at, u.username, u.id
        FROM posts p JOIN users u ON p.user_id = u.id
        WHERE p.id = ?
    """, (post_id,))
    post = c.fetchone()
    if not post:
        conn.close()
        return "Post not found", 404

    if request.method == "POST":
        if g.user is None: # CHANGED from app.g.user
            flash("You need to log in to add a comment.", "error")
            return redirect(url_for("login"))

        comment_text = request.form["comment"]
        if comment_text.strip():
            current_time = datetime.now().strftime("%Y-%m-%m %H:%M:%S")
            user_id = g.user[0] # CHANGED from app.g.user
            c.execute("INSERT INTO comments (post_id, user_id, comment, created_at) VALUES (?, ?, ?, ?)",
                      (post_id, user_id, comment_text, current_time))
            conn.commit()
            flash("Comment added!", "success")
            return redirect(url_for("post_detail", post_id=post_id))
        else:
            flash("Comment cannot be empty.", "error")

    c.execute("""
        SELECT c.id, c.post_id, c.comment, c.created_at, u.username, u.id
        FROM comments c JOIN users u ON c.user_id = u.id
        WHERE c.post_id = ? ORDER BY c.created_at ASC
    """, (post_id,))
    comments = c.fetchall()
    conn.close()
    return render_template("post_detail.html", post=post, comments=comments, messages=get_flashed_messages())

@app.route("/post/edit/<int:post_id>", methods=["GET", "POST"])
def edit_post(post_id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT id, user_id, title, content FROM posts WHERE id = ?", (post_id,))
    post = c.fetchone()

    if post is None:
        conn.close()
        return "Post not found", 404

    if g.user is None or g.user[0] != post[1]: # CHANGED from app.g.user
        flash("You are not authorized to edit this post.", "error")
        conn.close()
        return redirect(url_for("post_detail", post_id=post_id))

    if request.method == "POST":
        new_title = request.form["title"]
        new_content = request.form["content"]
        updated_time = datetime.now().strftime("%Y-%m-%m %H:%M:%S")
        c.execute("UPDATE posts SET title = ?, content = ?, updated_at = ? WHERE id = ?",
                  (new_title, new_content, updated_time, post_id))
        conn.commit()
        flash("Post updated successfully!", "success")
        conn.close()
        return redirect(url_for("post_detail", post_id=post_id))

    conn.close()
    return render_template("edit_post.html", post=post, messages=get_flashed_messages())

@app.route("/post/delete/<int:post_id>")
def delete_post(post_id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()
    c.execute("SELECT user_id FROM posts WHERE id = ?", (post_id,))
    post_user_id = c.fetchone()

    if post_user_id is None:
        conn.close()
        return "Post not found", 404

    if g.user is None or g.user[0] != post_user_id[0]: # CHANGED from app.g.user
        flash("You are not authorized to delete this post.", "error")
        conn.close()
        return redirect(url_for("post_detail", post_id=post_id))

    c.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    c.execute("DELETE FROM posts WHERE id = ?", (post_id,))
    conn.commit()
    flash("Post and its comments deleted successfully!", "success")
    conn.close()
    return redirect(url_for("home"))

@app.route("/comment/edit/<int:comment_id>", methods=["GET", "POST"])
def edit_comment(comment_id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT id, post_id, comment, user_id FROM comments WHERE id = ?", (comment_id,))
    comment = c.fetchone()

    if comment is None:
        conn.close()
        return "Comment not found", 404

    if g.user is None or g.user[0] != comment[3]: # CHANGED from app.g.user
        flash("You are not authorized to edit this comment.", "error")
        conn.close()
        return redirect(url_for("post_detail", post_id=comment[1]))

    if request.method == "POST":
        new_text = request.form["comment"]
        c.execute("UPDATE comments SET comment = ? WHERE id = ?", (new_text, comment_id))
        conn.commit()

        flash("Comment updated successfully!", "success")
        conn.close()
        return redirect(url_for("post_detail", post_id=comment[1]))

    conn.close()
    return render_template("edit_comment.html", comment=comment, messages=get_flashed_messages())

@app.route("/comment/delete/<int:comment_id>")
def delete_comment(comment_id):
    conn = sqlite3.connect("database.db")
    c = conn.cursor()

    c.execute("SELECT post_id, user_id FROM comments WHERE id = ?", (comment_id,))
    comment_info = c.fetchone()
    if comment_info is None:
        conn.close()
        return "Comment not found", 404

    if g.user is None or g.user[0] != comment_info[1]: # CHANGED from app.g.user
        flash("You are not authorized to delete this comment.", "error")
        conn.close()
        return redirect(url_for("post_detail", post_id=comment_info[0]))

    post_id = comment_info[0]
    c.execute("DELETE FROM comments WHERE id = ?", (comment_id,))
    conn.commit()
    conn.close()

    flash("Comment deleted successfully!", "success")
    return redirect(url_for("post_detail", post_id=post_id))

if __name__ == "__main__":
    app.run(debug=True)