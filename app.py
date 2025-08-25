import os
from flask import Flask, jsonify, request, render_template, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import pandas as pd
import json

app = Flask(__name__)
# Thiết lập secret key để sử dụng session
app.secret_key = os.environ.get('SECRET_KEY', 'a_very_secret_key_that_you_should_change')

# Lấy chuỗi kết nối từ biến môi trường của Render
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# =========================================================================
# === Các mô hình (Models) cho cơ sở dữ liệu
# =========================================================================

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(100), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    options = db.Column(db.String(500), nullable=False) # Lưu dưới dạng JSON string
    answer = db.Column(db.String(100), nullable=False)

# =========================================================================
# === Các route (API endpoints) cho ứng dụng
# =========================================================================

# Decorator để kiểm tra trạng thái đăng nhập
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return jsonify({'message': 'Unauthorized, login required'}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def index():
    # Hiển thị file HTML tĩnh của ứng dụng
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    user = User.query.filter_by(username=username).first()
    
    # Kiểm tra user admin đặc biệt
    if username == 'vinhnguyen' and password == 'vinh123':
        session['logged_in'] = True
        session['username'] = username
        return jsonify({'message': 'Đăng nhập thành công', 'is_admin': True}), 200

    # Kiểm tra user từ database
    if user and user.check_password(password):
        session['logged_in'] = True
        session['username'] = username
        return jsonify({'message': 'Đăng nhập thành công', 'is_admin': False}), 200
    
    return jsonify({'message': 'Tên người dùng hoặc mật khẩu không đúng'}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return jsonify({'message': 'Đăng xuất thành công'}), 200

@app.route('/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    """Quản lý người dùng."""
    if request.method == 'POST':
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not username or not password:
            return jsonify({'message': 'Thiếu tên người dùng hoặc mật khẩu'}), 400

        # Kiểm tra nếu người dùng đã tồn tại
        if User.query.filter_by(username=username).first():
            return jsonify({'message': 'Tên người dùng đã tồn tại'}), 409

        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return jsonify({'message': 'Thêm người dùng thành công'}), 201
    
    # GET request: Lấy danh sách người dùng
    users = User.query.all()
    user_list = [{'id': user.id, 'username': user.username} for user in users]
    return jsonify(user_list)

@app.route('/users/<int:user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    """Cập nhật người dùng."""
    user_to_update = User.query.get_or_404(user_id)
    data = request.get_json()
    new_username = data.get('username')
    new_password = data.get('password')

    if new_username:
        user_to_update.username = new_username
    if new_password:
        user_to_update.set_password(new_password)
    
    db.session.commit()
    return jsonify({'message': 'Cập nhật người dùng thành công'}), 200

@app.route('/users/<int:user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """Xóa một người dùng."""
    user_to_delete = User.query.get_or_404(user_id)
    db.session.delete(user_to_delete)
    db.session.commit()
    return jsonify({'message': 'Người dùng đã được xóa thành công'}), 200

@app.route('/upload_questions', methods=['POST'])
@login_required
def upload_questions():
    """Tải lên câu hỏi từ file Excel."""
    try:
        questions_data = request.get_json()
        if not questions_data:
            return jsonify({'message': 'Dữ liệu không hợp lệ.'}), 400

        for q_data in questions_data:
            new_question = Question(
                subject=q_data['subject'],
                text=q_data['text'],
                options=json.dumps(q_data['options']),
                answer=q_data['answer']
            )
            db.session.add(new_question)
        
        db.session.commit()
        return jsonify({'message': 'Đã tải lên câu hỏi thành công'}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({'message': f'Lỗi khi xử lý file Excel: {str(e)}'}), 500

@app.route('/subjects', methods=['GET'])
@login_required
def get_subjects():
    """Lấy danh sách các môn học có trong database."""
    subjects = db.session.query(Question.subject).distinct().all()
    subject_list = [s[0] for s in subjects]
    return jsonify(subject_list)

@app.route('/questions/<string:subject>', methods=['GET'])
@login_required
def get_questions(subject):
    """Lấy tất cả câu hỏi theo môn học."""
    questions = Question.query.filter_by(subject=subject).all()
    question_list = [{
        'id': q.id,
        'subject': q.subject,
        'text': q.text,
        'options': json.loads(q.options),
        'answer': q.answer
    } for q in questions]
    return jsonify(question_list)

if __name__ == '__main__':
    with app.app_context():
        # Tạo bảng nếu chưa có và thêm admin user
        db.create_all()
        # Thêm admin user nếu chưa tồn tại
        admin_user = User.query.filter_by(username='vinhnguyen').first()
        if not admin_user:
            admin_user = User(username='vinhnguyen')
            admin_user.set_password('vinh123')
            db.session.add(admin_user)
            db.session.commit()
    app.run(debug=True)