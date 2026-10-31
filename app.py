
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "blogspace_secret_key_2026"

DATABASE = "blog.db"


# Database connection
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# Initialize database
def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            post_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(post_id) REFERENCES posts(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()


# Website login protection
def login_required(route):
    @wraps(route)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please login to continue.", "error")
            return redirect(url_for("login"))
        return route(*args, **kwargs)
    return wrapper


# API login protection
def api_login_required(route):
    @wraps(route)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Please login first"}), 401
        return route(*args, **kwargs)
    return wrapper


# ================= WEBSITE ROUTES =================

# Home page
@app.route("/")
def index():
    conn = get_db()

    posts = conn.execute("""
        SELECT posts.*, users.username,
        (SELECT COUNT(*) FROM comments
         WHERE comments.post_id = posts.id) AS comment_count
        FROM posts
        JOIN users ON posts.user_id = users.id
        ORDER BY posts.created_at DESC
    """).fetchall()

    conn.close()
    return render_template("index.html", posts=posts)


# Registration
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not email or not password:
            flash("Please fill all fields.", "error")

        elif len(password) < 6:
            flash("Password must contain at least 6 characters.", "error")

        else:
            conn = get_db()

            try:
                conn.execute("""
                    INSERT INTO users (username, email, password)
                    VALUES (?, ?, ?)
                """, (
                    username,
                    email,
                    generate_password_hash(password)
                ))

                conn.commit()
                conn.close()

                flash("Account created! Please login.", "success")
                return redirect(url_for("login"))

            except sqlite3.IntegrityError:
                conn.close()
                flash("Email already registered.", "error")

    return render_template("register.html")


# Login
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()

        user = conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(user["password"], password):
            session.clear()
            session["user_id"] = user["id"]
            session["username"] = user["username"]

            flash("Welcome back!", "success")
            return redirect(url_for("index"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# Logout
@app.route("/logout")
@login_required
def logout():
    session.clear()
    flash("Logged out successfully.", "success")
    return redirect(url_for("index"))


# Create post
@app.route("/create", methods=["GET", "POST"])
@login_required
def create_post():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title or not content:
            flash("Title and content are required.", "error")

        else:
            conn = get_db()

            conn.execute("""
                INSERT INTO posts (title, content, user_id)
                VALUES (?, ?, ?)
            """, (title, content, session["user_id"]))

            conn.commit()
            conn.close()

            flash("Your story has been published!", "success")
            return redirect(url_for("index"))

    return render_template("create_post.html", post=None)


# View post and comments
@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def post_detail(post_id):
    conn = get_db()

    post = conn.execute("""
        SELECT posts.*, users.username
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = ?
    """, (post_id,)).fetchone()

    if not post:
        conn.close()
        return "Post not found", 404

    if request.method == "POST":
        if "user_id" not in session:
            conn.close()
            flash("Please login to comment.", "error")
            return redirect(url_for("login"))

        content = request.form.get("content", "").strip()

        if not content:
            flash("Comment cannot be empty.", "error")
        else:
            conn.execute("""
                INSERT INTO comments (content, post_id, user_id)
                VALUES (?, ?, ?)
            """, (content, post_id, session["user_id"]))

            conn.commit()
            conn.close()

            flash("Comment added!", "success")
            return redirect(url_for("post_detail", post_id=post_id))

    comments = conn.execute("""
        SELECT comments.*, users.username
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.post_id = ?
        ORDER BY comments.created_at DESC
    """, (post_id,)).fetchall()

    conn.close()

    return render_template(
        "post_detail.html",
        post=post,
        comments=comments
    )


# Edit post
@app.route("/edit/<int:post_id>", methods=["GET", "POST"])
@login_required
def edit_post(post_id):
    conn = get_db()

    post = conn.execute(
        "SELECT * FROM posts WHERE id = ?", (post_id,)
    ).fetchone()

    if not post:
        conn.close()
        return "Post not found", 404

    if post["user_id"] != session["user_id"]:
        conn.close()
        return "You cannot edit this post.", 403

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if title and content:
            conn.execute("""
                UPDATE posts SET title = ?, content = ?
                WHERE id = ?
            """, (title, content, post_id))

            conn.commit()
            conn.close()

            flash("Post updated successfully!", "success")
            return redirect(url_for("post_detail", post_id=post_id))

        flash("Please fill all fields.", "error")

    conn.close()
    return render_template("create_post.html", post=post)


# Delete post
@app.route("/delete/<int:post_id>", methods=["POST"])
@login_required
def delete_post(post_id):
    conn = get_db()

    post = conn.execute(
        "SELECT * FROM posts WHERE id = ?", (post_id,)
    ).fetchone()

    if not post:
        conn.close()
        return "Post not found", 404

    if post["user_id"] != session["user_id"]:
        conn.close()
        return "You cannot delete this post.", 403

    conn.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    conn.commit()
    conn.close()

    flash("Post deleted successfully.", "success")
    return redirect(url_for("index"))


# ================= REST API ROUTES =================

# GET: All blog posts
@app.route("/api/posts", methods=["GET"])
def api_get_posts():
    conn = get_db()

    posts = conn.execute("""
        SELECT posts.*, users.username
        FROM posts
        JOIN users ON posts.user_id = users.id
        ORDER BY posts.created_at DESC
    """).fetchall()

    conn.close()

    return jsonify([dict(post) for post in posts]), 200


# GET: Single blog post
@app.route("/api/posts/<int:post_id>", methods=["GET"])
def api_get_post(post_id):
    conn = get_db()

    post = conn.execute("""
        SELECT posts.*, users.username
        FROM posts
        JOIN users ON posts.user_id = users.id
        WHERE posts.id = ?
    """, (post_id,)).fetchone()

    conn.close()

    if not post:
        return jsonify({"error": "Post not found"}), 404

    return jsonify(dict(post)), 200


# POST: Create a new blog post
@app.route("/api/posts", methods=["POST"])
@api_login_required
def api_create_post():
    data = request.get_json(silent=True) or {}

    title = data.get("title", "")
    content = data.get("content", "")

    if not isinstance(title, str) or not isinstance(content, str):
        return jsonify({"error": "Title and content must be text"}), 400

    title = title.strip()
    content = content.strip()

    if not title or not content:
        return jsonify({"error": "Title and content are required"}), 400

    conn = get_db()

    cursor = conn.execute("""
        INSERT INTO posts (title, content, user_id)
        VALUES (?, ?, ?)
    """, (title, content, session["user_id"]))

    conn.commit()
    post_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "message": "Post created successfully",
        "post_id": post_id
    }), 201


# PUT: Update a blog post
@app.route("/api/posts/<int:post_id>", methods=["PUT"])
@api_login_required
def api_update_post(post_id):
    data = request.get_json(silent=True) or {}

    title = data.get("title", "")
    content = data.get("content", "")

    if not isinstance(title, str) or not isinstance(content, str):
        return jsonify({"error": "Title and content must be text"}), 400

    title = title.strip()
    content = content.strip()

    if not title or not content:
        return jsonify({"error": "Title and content are required"}), 400

    conn = get_db()

    post = conn.execute(
        "SELECT * FROM posts WHERE id = ?", (post_id,)
    ).fetchone()

    if not post:
        conn.close()
        return jsonify({"error": "Post not found"}), 404

    if post["user_id"] != session["user_id"]:
        conn.close()
        return jsonify({"error": "You cannot update this post"}), 403

    conn.execute("""
        UPDATE posts
        SET title = ?, content = ?
        WHERE id = ?
    """, (title, content, post_id))

    conn.commit()
    conn.close()

    return jsonify({"message": "Post updated successfully"}), 200


# DELETE: Delete a blog post
@app.route("/api/posts/<int:post_id>", methods=["DELETE"])
@api_login_required
def api_delete_post(post_id):
    conn = get_db()

    post = conn.execute(
        "SELECT * FROM posts WHERE id = ?", (post_id,)
    ).fetchone()

    if not post:
        conn.close()
        return jsonify({"error": "Post not found"}), 404

    if post["user_id"] != session["user_id"]:
        conn.close()
        return jsonify({"error": "You cannot delete this post"}), 403

    conn.execute("DELETE FROM comments WHERE post_id = ?", (post_id,))
    conn.execute("DELETE FROM posts WHERE id = ?", (post_id,))

    conn.commit()
    conn.close()

    return jsonify({"message": "Post deleted successfully"}), 200


# GET: Comments of a blog post
@app.route("/api/posts/<int:post_id>/comments", methods=["GET"])
def api_get_comments(post_id):
    conn = get_db()

    post = conn.execute(
        "SELECT id FROM posts WHERE id = ?", (post_id,)
    ).fetchone()

    if not post:
        conn.close()
        return jsonify({"error": "Post not found"}), 404

    comments = conn.execute("""
        SELECT comments.*, users.username
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE comments.post_id = ?
        ORDER BY comments.created_at DESC
    """, (post_id,)).fetchall()

    conn.close()

    return jsonify([dict(comment) for comment in comments]), 200


# POST: Add a comment
@app.route("/api/posts/<int:post_id>/comments", methods=["POST"])
@api_login_required
def api_add_comment(post_id):
    data = request.get_json(silent=True) or {}
    content = data.get("content", "")

    if not isinstance(content, str):
        return jsonify({"error": "Comment must be text"}), 400

    content = content.strip()

    if not content:
        return jsonify({"error": "Comment cannot be empty"}), 400

    conn = get_db()

    post = conn.execute(
        "SELECT id FROM posts WHERE id = ?", (post_id,)
    ).fetchone()

    if not post:
        conn.close()
        return jsonify({"error": "Post not found"}), 404

    cursor = conn.execute("""
        INSERT INTO comments (content, post_id, user_id)
        VALUES (?, ?, ?)
    """, (content, post_id, session["user_id"]))

    conn.commit()
    comment_id = cursor.lastrowid
    conn.close()

    return jsonify({
        "message": "Comment added successfully",
        "comment_id": comment_id
    }), 201


# ================= RUN APPLICATION =================

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
