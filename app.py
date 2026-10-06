import os
import uuid
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'change-this-secret-key')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
FILES_BUCKET = os.environ.get('SUPABASE_FILES_BUCKET', 'creator-files')
PRODUCTS_BUCKET = os.environ.get('SUPABASE_PRODUCTS_BUCKET', 'creator-products')
ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError('SUPABASE_URL and SUPABASE_KEY environment variables are required.')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

CREATOR = {
    'name': 'CreatorHub Official',
    'whatsapp': '918886868894',
    'whatsapp_display': '+91 88868 68894',
    'email': 'dineshkarthik0724@gmail.com',
    'instagram': 'https://www.instagram.com/its_me__gymson?stkn=MWxrenZjcTI5ZWVjcA=='
}


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return fn(*args, **kwargs)
    return wrapper


def public_url(bucket, path):
    return supabase.storage.from_(bucket).get_public_url(path)


@app.context_processor
def inject_creator():
    return {'creator': CREATOR, 'logged_in': bool(session.get('admin_logged_in'))}


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/files')
def files():
    rows = supabase.table('files').select('*').order('created_at', desc=True).execute().data or []
    for row in rows:
        row['url'] = public_url(FILES_BUCKET, row.get('file_path', ''))
    return render_template('files.html', files=rows)


@app.route('/updates')
def updates():
    rows = supabase.table('posts').select('*').order('created_at', desc=True).execute().data or []
    return render_template('updates.html', posts=rows)


@app.route('/products')
def products():
    rows = supabase.table('products').select('*').order('created_at', desc=True).execute().data or []
    for row in rows:
        row['image_url'] = public_url(PRODUCTS_BUCKET, row.get('image_path', '')) if row.get('image_path') else ''
    return render_template('products.html', products=rows)


@app.route('/suggestions', methods=['GET', 'POST'])
def suggestions():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        message = request.form.get('message', '').strip()
        if not message:
            flash('Please enter your suggestion.', 'error')
            return redirect(url_for('suggestions'))
        supabase.table('suggestions').insert({
            'name': name,
            'email': email,
            'message': message
        }).execute()
        flash('Thank you! Your suggestion was submitted.', 'success')
        return redirect(url_for('suggestions'))
    return render_template('suggestions.html')


@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin'))
        flash('Invalid username or password.', 'error')
    return render_template('admin_login.html')


@app.route('/admin/logout')
def admin_logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/admin')
@admin_required
def admin():
    files_rows = supabase.table('files').select('*').order('created_at', desc=True).execute().data or []
    posts = supabase.table('posts').select('*').order('created_at', desc=True).execute().data or []
    products_rows = supabase.table('products').select('*').order('created_at', desc=True).execute().data or []
    suggestions_rows = supabase.table('suggestions').select('*').order('created_at', desc=True).execute().data or []
    return render_template('admin.html', files=files_rows, posts=posts, products=products_rows, suggestions=suggestions_rows)


@app.route('/admin/file/add', methods=['POST'])
@admin_required
def add_file():
    uploaded = request.files.get('file')
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    if not uploaded or not uploaded.filename:
        flash('Please select a file.', 'error')
        return redirect(url_for('admin'))
    original = uploaded.filename
    ext = os.path.splitext(original)[1]
    path = f"{uuid.uuid4().hex}{ext}"
    data = uploaded.read()
    content_type = uploaded.mimetype or 'application/octet-stream'
    supabase.storage.from_(FILES_BUCKET).upload(path, data, {'content-type': content_type, 'upsert': 'false'})
    supabase.table('files').insert({
        'title': title or original,
        'description': description,
        'original_name': original,
        'file_path': path
    }).execute()
    flash('File uploaded successfully.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/file/delete/<int:file_id>', methods=['POST'])
@admin_required
def delete_file(file_id):
    row = supabase.table('files').select('file_path').eq('id', file_id).single().execute().data
    if row:
        try:
            supabase.storage.from_(FILES_BUCKET).remove([row['file_path']])
        finally:
            supabase.table('files').delete().eq('id', file_id).execute()
    flash('File deleted.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/post/add', methods=['POST'])
@admin_required
def add_post():
    title = request.form.get('title', '').strip()
    body = request.form.get('body', '').strip()
    link = request.form.get('link', '').strip()
    if not title or not body:
        flash('Title and update text are required.', 'error')
        return redirect(url_for('admin'))
    supabase.table('posts').insert({'title': title, 'body': body, 'link': link}).execute()
    flash('Update posted.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/post/delete/<int:post_id>', methods=['POST'])
@admin_required
def delete_post(post_id):
    supabase.table('posts').delete().eq('id', post_id).execute()
    flash('Update deleted.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/product/add', methods=['POST'])
@admin_required
def add_product():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    link = request.form.get('link', '').strip()
    image = request.files.get('image')
    if not name or not link:
        flash('Product name and product link are required.', 'error')
        return redirect(url_for('admin'))
    image_path = ''
    if image and image.filename:
        ext = os.path.splitext(image.filename)[1]
        image_path = f"{uuid.uuid4().hex}{ext}"
        supabase.storage.from_(PRODUCTS_BUCKET).upload(image_path, image.read(), {'content-type': image.mimetype or 'application/octet-stream', 'upsert': 'false'})
    supabase.table('products').insert({
        'name': name,
        'description': description,
        'image_path': image_path,
        'link': link
    }).execute()
    flash('Product added.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/product/delete/<int:product_id>', methods=['POST'])
@admin_required
def delete_product(product_id):
    row = supabase.table('products').select('image_path').eq('id', product_id).single().execute().data
    if row:
        if row.get('image_path'):
            try:
                supabase.storage.from_(PRODUCTS_BUCKET).remove([row['image_path']])
            except Exception:
                pass
        supabase.table('products').delete().eq('id', product_id).execute()
    flash('Product deleted.', 'success')
    return redirect(url_for('admin'))


@app.route('/admin/suggestion/delete/<int:suggestion_id>', methods=['POST'])
@admin_required
def delete_suggestion(suggestion_id):
    supabase.table('suggestions').delete().eq('id', suggestion_id).execute()
    flash('Suggestion deleted.', 'success')
    return redirect(url_for('admin'))


@app.errorhandler(413)
def too_large(_):
    return 'File is too large. Maximum size is 50 MB.', 413


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=True)
