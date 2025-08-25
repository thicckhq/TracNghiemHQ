from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return '<h1>Đây là trang web của tôi, được tạo bằng Flask và Render!</h1><p>Bạn có thể tùy chỉnh nội dung theo ý muốn.</p>'

if __name__ == '__main__':
    app.run(debug=True)