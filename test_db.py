from models import db, User, Company, Risk
from flask import Flask

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/project.db'
db.init_app(app)

with app.app_context():
    print('Users:', User.query.count())
    print('Companies:', Company.query.count())
    print('Risks:', Risk.query.count())
    user = User.query.filter_by(email='kristina@erm-strategies.com').first()
    if user:
        print('Admin user found:', user.first_name, user.last_name)