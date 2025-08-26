import os
import threading
import time
import requests
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from sqlalchemy import create_engine, text
from werkzeug.security import check_password_hash, generate_password_hash
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import socket

# ---------- Flask config ----------
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "secret123")

# ---------- Database config ----------
DATABASE_URL = os.getenv("DATABASE_URL",
    "postgresql://vinhnguyen:uDpQGHxIAMFtuWlXztNE86cDAXmNF4VH@dpg-d2m1nljuibrs73fo7dig-a.oregon-postgres.render.com/db_tracnghiemhq"
)
engine = create_engine(DATABASE_URL, echo=False)

# ---------- Ping thread tránh ngủ đông ----------
def ping_server():
    while True:
        try:
            url = os.getenv("PING_URL", "https://tracnghiemhq.onrender.com")
            requests.get(url)
        except Exception as e:
            print("Ping error:", e)
        time.sleep(600)

threading.Thread(target=ping_server, daemon=True).start()

# ---------- Đăng nhập ----------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        with engine.connect() as conn:
            user = conn.execute(
                text("SELECT * FROM Nguoidung WHERE username = :u"),
                {"u": username}
            ).mappings().first()

        if user:
            if check_password_hash(user["password_hash"], password):
                session['username'] = user["username"]
                session['ten_thuc'] = user["ten_thuc"]
                session['is_admin'] = user["is_admin"]
                session['so_dien_thoai'] = user["so_dien_thoai"]
                session['email'] = user["email"]
                return redirect(url_for('index'))
            else:
                flash("Sai mật khẩu!")
        else:
            flash("Không tìm thấy người dùng!")

    return render_template('login.html')

# ---------- Kiểm tra username tồn tại ----------
@app.route('/check-username', methods=['POST'])
def check_username():
    username = request.form.get('username')
    if not username:
        return jsonify({"exists": False})

    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT 1 FROM Nguoidung WHERE username=:u"),
            {"u": username}
        ).first()

    return jsonify({"exists": True if user else False})

# ---------- Đăng ký ----------
@app.route('/register', methods=['POST'])
def register():
    username = request.form.get('username')
    password = request.form.get('password')
    display_name = request.form.get('display_name')
    phone = request.form.get('phone')
    email = request.form.get('email')
    company = request.form.get('company')
    mon_dang_ky = request.form.get('mon_dang_ky')
    ngay_het_han = request.form.get('ngay_het_han')

    if not username or not password:
        flash("Thiếu thông tin bắt buộc!")
        return redirect(url_for('login'))

    with engine.begin() as conn:
        exist = conn.execute(
            text("SELECT 1 FROM Nguoidung WHERE username=:u OR email=:e"),
            {"u": username, "e": email}
        ).first()
        if exist:
            flash("Tên đăng nhập hoặc Email đã tồn tại!")
            return redirect(url_for('login'))
        pw_hash = generate_password_hash(password)
        conn.execute(text("""
            INSERT INTO Nguoidung (username, password_hash, ten_thuc, so_dien_thoai, email, cong_ty)
            VALUES (:u, :p, :t, :ph, :e, :c)
        """), {
            "u": username,
            "p": pw_hash,
            "t": display_name,
            "ph": phone,
            "e": email,
            "c": company
        })
    flash("Đăng ký thành công, vui lòng đăng nhập!")
    return redirect(url_for('login'))

# ---------- Quên mật khẩu ----------
@app.route('/forgot-password', methods=['POST'])
def forgot_password():
    flash("Chức năng này đang cập nhật, hãy liên hệ Admin để lấy lại mật khẩu.")
    return redirect(url_for('login'))

# ---------- Trang chủ ----------
@app.route('/')
def index():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', username=session['username'], is_admin=session.get('is_admin'))

# ---------- Đăng xuất ----------
@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('ten_thuc', None)
    session.pop('is_admin', None)
    return redirect(url_for('login'))

# ---------- Tác giả ----------
@app.route('/tac-gia')
def tac_gia():
    data = {
        'ten': 'Nguyễn Văn A',
        'mo_ta': 'Tác giả của bộ đề thi.',
        'anh_qr': 'https://placehold.co/200x200/png?text=QR+Code'
    }
    return render_template('tac_gia.html', tac_gia=data)

# ---------- Tài khoản của tôi ----------
@app.route('/tai-khoan')
def tai_khoan():
    if 'username' not in session:
        return redirect(url_for('login'))

    username = session['username']
    with engine.connect() as conn:
        user_info = conn.execute(
            text("SELECT so_dien_thoai, email, mon_dang_ky, ngay_het_han, ten_thuc FROM Nguoidung WHERE username = :u"),
            {"u": username}
        ).mappings().first()

    if user_info:
        # Chuyển đổi mon_dang_ky
        mon_dang_ky_raw = user_info['mon_dang_ky']
        mon_dang_ky_list = []
        if mon_dang_ky_raw:
            if '1' in mon_dang_ky_raw:
                mon_dang_ky_list.append("Pháp luật hải quan")
            if '2' in mon_dang_ky_raw:
                mon_dang_ky_list.append("Kỹ thuật nghiệp vụ ngoại thương")
            if '3' in mon_dang_ky_raw:
                mon_dang_ky_list.append("Kỹ thuật nghiệp vụ hải quan")

        return render_template('tai_khoan.html',
                               username=username,
                               ten_thuc=user_info['ten_thuc'],
                               so_dien_thoai=user_info['so_dien_thoai'],
                               email=user_info['email'],
                               mon_dang_ky=mon_dang_ky_list,
                               ngay_het_han=user_info['ngay_het_han'],
                               is_admin=session.get('is_admin'))
    else:
        flash("Không tìm thấy thông tin tài khoản.")
        return redirect(url_for('index'))

# ---------- Chạy ứng dụng ----------
if __name__ == '__main__':
    # Kiểm tra xem có cần tạo bảng không (chỉ chạy 1 lần)
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS Nguoidung (
                username VARCHAR(50) PRIMARY KEY,
                password_hash VARCHAR(200) NOT NULL,
                ten_thuc VARCHAR(100),
                is_admin BOOLEAN DEFAULT FALSE,
                so_dien_thoai VARCHAR(20),
                email VARCHAR(100),
                cong_ty VARCHAR(100),
                mon_dang_ky VARCHAR(100),
                ngay_het_han DATE
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS Cauhoi (
                id SERIAL PRIMARY KEY,
                ma_mon VARCHAR(50) NOT NULL,
                cau_hoi TEXT NOT NULL,
                dap_an_a TEXT,
                dap_an_b TEXT,
                dap_an_c TEXT,
                dap_an_d TEXT,
                dap_an_dung VARCHAR(1),
                ghi_chu TEXT
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS Ketqua (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) REFERENCES Nguoidung(username),
                ma_mon VARCHAR(50),
                cau_tra_loi JSONB,
                diem INTEGER,
                ngay_thi DATE DEFAULT CURRENT_DATE
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS Monthi (
                ma_mon VARCHAR(50) PRIMARY KEY,
                ten_mon VARCHAR(100)
            );
        """))
    app.run(debug=True)
