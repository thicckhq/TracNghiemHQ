import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# Lấy chuỗi kết nối từ biến môi trường
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Định nghĩa mô hình cơ sở dữ liệu
class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(200), nullable=False)
    answer = db.Column(db.String(100), nullable=False)

@app.route('/')
def home():
    return '<h1>Ứng dụng đã kết nối với cơ sở dữ liệu!</h1>'

# (Đoạn code để thêm dữ liệu vào database)
@app.route('/create_table')
def create_table():
    with app.app_context():
        db.create_all()
    return "Table created successfully!"

if __name__ == '__main__':
    app.run(debug=True)