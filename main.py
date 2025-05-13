import os
import sys
import requests
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, current_user, logout_user, login_required
from werkzeug.utils import secure_filename
from requirements import products_list

app = Flask(__name__)
app.config['SECRET_KEY'] = 'ABraKAdaBRa12'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

UPLOAD_FOLDER = 'static/comment_images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAPS_FOLDER = 'static/maps'
app.config['MAPS_FOLDER'] = MAPS_FOLDER
if not os.path.exists(MAPS_FOLDER):
    os.makedirs(MAPS_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def api(adres):
    server_address = 'http://geocode-maps.yandex.ru/1.x/?'
    api_key = '8013b162-6b42-4997-9691-77b7074026e0'
    geocode = adres
    geocoder_request = f'{server_address}apikey={api_key}&geocode={geocode}&format=json'
    response = requests.get(geocoder_request)
    if response:
        json_response = response.json()
        toponym = json_response["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]
        toponym_address = toponym["metaDataProperty"]["GeocoderMetaData"]["text"]
        toponym_coodrinates = toponym["Point"]["pos"]
        return(toponym_address)
    else:
        print("Ошибка выполнения запроса:")
        print(geocoder_request)
        print("Http статус:", response.status_code, "(", response.reason, ")")

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    comments = db.relationship('Comment', backref='author', lazy=True)

    def repr(self):
        return f"<User('{self.username}', '{self.email}')>"

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)

    def repr(self):
        return f"<Product('{self.name}', '{self.price}')>"

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    image_filename = db.Column(db.String(255))
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)

    def repr(self):
        return f"<Comment('{self.text}')>"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route("/")
def index():
    products = Product.query.all()
    return render_template('index.html', products=products)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    comments = Comment.query.filter_by(product_id=product_id).all()
    return render_template('product_detail.html', product=product, comments=comments)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        if not username or not email or not password or not confirm_password:
            flash('Пожалуйста, заполните все поля', 'danger')
        elif password != confirm_password:
            flash('Пароли не совпадают', 'danger')
        elif User.query.filter_by(username=username).first():
            flash('Имя занято', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('Почта занята', 'danger')
        else:
            hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
            user = User(username=username, email=email, password=hashed_password)
            db.session.add(user)
            db.session.commit()
            flash('Создан новый аккаунт', 'success')
            return redirect(url_for('login'))
    return render_template('register.html')

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user:
            if bcrypt.check_password_hash(user.password, password):
                login_user(user)
                flash('Добро пожаловать!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page) if next_page else redirect(url_for('index'))
            else:
                flash('Неверное имя или пароль', 'danger')
        else:
            flash('Неверное имя или пароль', 'danger')
    return render_template('login.html')

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash('Вы вышли из аккаунта', 'info')
    return redirect(url_for('index'))

@app.route("/product/<int:product_id>/comment", methods=['POST'])
@login_required
def add_comment(product_id):
    text = request.form['comment']
    image = request.files['image']
    image_filename = None
    if text:
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(filepath)
            image_filename = filename
        comment = Comment(text=text, user_id=current_user.id, image_filename=image_filename, product_id=product_id)
        db.session.add(comment)
        db.session.commit()
        flash('Комментарий добавлен', 'success')
    else:
        flash('Комментарий не может быть пустым', 'danger')
    return redirect(url_for('product_detail', product_id=product_id))

@app.route("/product/<int:product_id>/checkout")
@login_required
def checkout(product_id):
    product = Product.query.get_or_404(product_id)
    return render_template('checkout.html', product=product)

@app.route("/product/<int:product_id>/process_order", methods=['POST'])
@login_required
def process_order(product_id):
    card_number = request.form['card_number']
    address = request.form['address']
    product = Product.query.get_or_404(product_id)
    flash('Заказ успешно оформлен!', 'success')
    return render_template('order_confirmation.html', product_name=product.name, product_price=product.price, card_number=card_number, address=api(address))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        Product.query.delete()
        db.session.commit()
        for product_data in products_list:
            new_product = Product(
                name=product_data['name'],
                description=product_data['description'],
                price=product_data['price']
            )
            db.session.add(new_product)
        db.session.commit()
        if not os.path.exists(UPLOAD_FOLDER):
            os.makedirs(UPLOAD_FOLDER)
        if not os.path.exists(MAPS_FOLDER):
            os.makedirs(MAPS_FOLDER)
        app.run(port=8080, host='127.0.0.1')
