from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt

app = Flask(__name__)
bcrypt = Bcrypt(app)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'root'
app.config['MYSQL_DB'] = 'blogging_system'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
mysql = MySQL(app)

# Secret Key for Session
app.secret_key = 'your_secret_key'

# Routes
@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT posts.id, posts.title, posts.content, users.username AS author, posts.created_at, 
        (SELECT COUNT(*) FROM likes WHERE likes.post_id = posts.id) AS like_count,
        (SELECT COUNT(*) FROM comments WHERE comments.post_id = posts.id) AS comment_count
        FROM posts 
        JOIN users ON posts.author_id = users.id 
        ORDER BY posts.created_at DESC
    """)
    posts = cur.fetchall()
    cur.close()
    return render_template('index.html', posts=posts)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')

        cur = mysql.connection.cursor()
        try:
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed_password))
            mysql.connection.commit()
            flash('Registration successful! Please log in.', 'success')
            return redirect(url_for('login'))
        except:
            flash('Username already exists.', 'danger')
        finally:
            cur.close()
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()

        if user and bcrypt.check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('login'))

@app.route('/create', methods=['GET', 'POST'])
def create():
    if 'user_id' not in session:
        flash('Please log in to create a post.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        author_id = session['user_id']

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO posts (title, content, author_id) VALUES (%s, %s, %s)", (title, content, author_id))
        mysql.connection.commit()
        cur.close()

        flash('Post created successfully!', 'success')
        return redirect(url_for('index'))
    return render_template('create.html')

@app.route('/post/<int:post_id>', methods=['GET', 'POST'])
def post(post_id):
    cur = mysql.connection.cursor()
    # Fetch post details
    cur.execute("""
        SELECT posts.id, posts.title, posts.content, users.username AS author, posts.created_at 
        FROM posts 
        JOIN users ON posts.author_id = users.id 
        WHERE posts.id = %s
    """, (post_id,))
    post = cur.fetchone()

    # Fetch comments
    cur.execute("""
        SELECT comments.id, comments.content, users.username, comments.created_at 
        FROM comments 
        JOIN users ON comments.user_id = users.id 
        WHERE comments.post_id = %s
        ORDER BY comments.created_at DESC
    """, (post_id,))
    comments = cur.fetchall()

    # Check if the current user liked the post
    liked = False
    if 'user_id' in session:
        cur.execute("SELECT * FROM likes WHERE post_id = %s AND user_id = %s", (post_id, session['user_id']))
        liked = bool(cur.fetchone())

    # Count likes
    cur.execute("SELECT COUNT(*) AS like_count FROM likes WHERE post_id = %s", (post_id,))
    like_count = cur.fetchone()['like_count']

    cur.close()

    if request.method == 'POST' and 'user_id' in session:
        content = request.form['comment']
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO comments (post_id, user_id, content) VALUES (%s, %s, %s)", (post_id, session['user_id'], content))
        mysql.connection.commit()
        cur.close()
        flash('Comment added!', 'success')
        return redirect(url_for('post', post_id=post_id))

    return render_template('post.html', post=post, comments=comments, liked=liked, like_count=like_count)


@app.route('/like/<int:post_id>')
def like(post_id):
    if 'user_id' not in session:
        flash('Please log in to like posts.', 'danger')
        return redirect(url_for('login'))

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO likes (post_id, user_id) VALUES (%s, %s) ON DUPLICATE KEY UPDATE id=id", (post_id, session['user_id']))
    mysql.connection.commit()
    cur.close()

    flash('Post liked!', 'success')
    return redirect(url_for('post', post_id=post_id))


@app.route('/update/<int:post_id>', methods=['GET', 'POST'])
def update(post_id):
    if 'user_id' not in session:
        flash('You need to log in to update a post.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']

        cursor = mysql.connection.cursor()
        cursor.execute("UPDATE posts SET title = %s, content = %s WHERE id = %s AND author_id = %s",
                       (title, content, post_id, session['user_id']))
        mysql.connection.commit()
        cursor.close()

        flash('Post updated successfully!', 'success')
        return redirect(url_for('index'))

    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM posts WHERE id = %s AND author_id = %s", (post_id, session['user_id']))
    post = cursor.fetchone()
    cursor.close()

    if not post:
        flash('Post not found or unauthorized access.', 'danger')
        return redirect(url_for('index'))

    return render_template('update.html', post=post)


@app.route('/delete/<int:post_id>', methods=[ 'GET','POST'])
def delete(post_id):

    if 'user_id' not in session:
        flash("You need to log in to delete a post.", "error")
        return redirect(url_for('login'))

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("DELETE FROM posts WHERE id=%s AND author_id=%s",(post_id,session['user_id']))
        mysql.connection.commit()
        if cursor.rowcount>0:
            flash("Post deleted successfully!","success")
        else:
            flash("Failed to delete the post. It may not exist or you may not be the author.","danger")
    finally:
        cursor.close()
    return redirect(url_for('index'))




