from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
import os
import secrets

app = Flask(__name__)

# Database configuration
database_url = os.environ.get('DATABASE_URL', 'postgresql://fintech_user:fintech_password@localhost:5432/fintech_db')
app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# API Keys for authentication
VALID_API_KEYS = [os.environ.get('API_KEY', 'test-key-12345')]

# Account model
class Account(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), unique=True, nullable=False)
    balance = db.Column(db.Float, default=1000.0)
    currency = db.Column(db.String(3), default='USD')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'balance': self.balance,
            'currency': self.currency
        }

# Authentication decorator
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key or api_key not in VALID_API_KEYS:
            return jsonify({"error": "Invalid or missing API key"}), 401
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
def home():
    return jsonify({"message": "Welcome to My Fintech App", "version": "1.0"})

@app.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

@app.route('/api/accounts', methods=['GET'])
@require_api_key
def get_all_accounts():
    accounts = Account.query.all()
    return jsonify([account.to_dict() for account in accounts]), 200

@app.route('/api/accounts', methods=['POST'])
@require_api_key
def create_account():
    data = request.get_json()
    
    if not data or 'user_id' not in data:
        return jsonify({"error": "user_id is required"}), 400
    
    user_id = data.get('user_id')
    balance = data.get('balance', 1000.0)
    currency = data.get('currency', 'USD')
    
    # Check if account already exists
    existing = Account.query.filter_by(user_id=user_id).first()
    if existing:
        return jsonify({"error": f"Account for user_id '{user_id}' already exists"}), 409
    
    try:
        account = Account(user_id=user_id, balance=balance, currency=currency)
        db.session.add(account)
        db.session.commit()
        return jsonify({"message": "Account created", "account": account.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/balance/<user_id>', methods=['GET'])
@require_api_key
def get_balance(user_id):
    account = Account.query.filter_by(user_id=user_id).first()
    if not account:
        return jsonify({"error": "Account not found"}), 404
    return jsonify(account.to_dict()), 200

@app.route('/api/balance/<user_id>', methods=['PUT'])
@require_api_key
def update_balance(user_id):
    data = request.get_json()
    
    if not data or 'balance' not in data:
        return jsonify({"error": "balance is required"}), 400
    
    account = Account.query.filter_by(user_id=user_id).first()
    if not account:
        return jsonify({"error": "Account not found"}), 404
    
    try:
        account.balance = data['balance']
        db.session.commit()
        return jsonify({"message": "Balance updated", "account": account.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
