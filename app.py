from flask import Flask, jsonify, request
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from datetime import datetime
import os
import secrets

app = Flask(__name__)

# Database configuration
database_url = os.environ.get('DATABASE_URL', 'postgresql://fintech_user:[REDACTED]@localhost:5432/fintech_db')
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'balance': self.balance,
            'currency': self.currency,
            'created_at': self.created_at.isoformat()
        }

# Transaction model
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    from_user_id = db.Column(db.String(50), nullable=True)
    to_user_id = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)  # deposit, withdraw, transfer
    status = db.Column(db.String(20), default='completed')  # completed, pending, failed
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'from_user_id': self.from_user_id,
            'to_user_id': self.to_user_id,
            'amount': self.amount,
            'transaction_type': self.transaction_type,
            'status': self.status,
            'description': self.description,
            'created_at': self.created_at.isoformat()
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
    return jsonify({"message": "Welcome to My Fintech App", "version": "2.0"})

@app.route('/health')
def health():
    try:
        db.session.execute(db.text('SELECT 1'))
        return jsonify({"status": "healthy", "database": "connected"}), 200
    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500

# Account endpoints
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

# Transaction endpoints
@app.route('/api/deposit', methods=['POST'])
@require_api_key
def deposit():
    data = request.get_json()
    
    if not data or 'user_id' not in data or 'amount' not in data:
        return jsonify({"error": "user_id and amount are required"}), 400
    
    user_id = data.get('user_id')
    amount = data.get('amount')
    description = data.get('description', 'Deposit')
    
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400
    
    account = Account.query.filter_by(user_id=user_id).first()
    if not account:
        return jsonify({"error": "Account not found"}), 404
    
    try:
        account.balance += amount
        transaction = Transaction(
            to_user_id=user_id,
            amount=amount,
            transaction_type='deposit',
            status='completed',
            description=description
        )
        db.session.add(transaction)
        db.session.commit()
        return jsonify({
            "message": "Deposit successful",
            "account": account.to_dict(),
            "transaction": transaction.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/withdraw', methods=['POST'])
@require_api_key
def withdraw():
    data = request.get_json()
    
    if not data or 'user_id' not in data or 'amount' not in data:
        return jsonify({"error": "user_id and amount are required"}), 400
    
    user_id = data.get('user_id')
    amount = data.get('amount')
    description = data.get('description', 'Withdrawal')
    
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400
    
    account = Account.query.filter_by(user_id=user_id).first()
    if not account:
        return jsonify({"error": "Account not found"}), 404
    
    if account.balance < amount:
        return jsonify({"error": "Insufficient funds"}), 400
    
    try:
        account.balance -= amount
        transaction = Transaction(
            from_user_id=user_id,
            to_user_id=user_id,
            amount=amount,
            transaction_type='withdraw',
            status='completed',
            description=description
        )
        db.session.add(transaction)
        db.session.commit()
        return jsonify({
            "message": "Withdrawal successful",
            "account": account.to_dict(),
            "transaction": transaction.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/transfer', methods=['POST'])
@require_api_key
def transfer():
    data = request.get_json()
    
    if not data or 'from_user_id' not in data or 'to_user_id' not in data or 'amount' not in data:
        return jsonify({"error": "from_user_id, to_user_id, and amount are required"}), 400
    
    from_user_id = data.get('from_user_id')
    to_user_id = data.get('to_user_id')
    amount = data.get('amount')
    description = data.get('description', 'Transfer')
    
    if amount <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400
    
    if from_user_id == to_user_id:
        return jsonify({"error": "Cannot transfer to the same account"}), 400
    
    from_account = Account.query.filter_by(user_id=from_user_id).first()
    to_account = Account.query.filter_by(user_id=to_user_id).first()
    
    if not from_account:
        return jsonify({"error": f"From account '{from_user_id}' not found"}), 404
    if not to_account:
        return jsonify({"error": f"To account '{to_user_id}' not found"}), 404
    
    if from_account.balance < amount:
        return jsonify({"error": "Insufficient funds"}), 400
    
    try:
        from_account.balance -= amount
        to_account.balance += amount
        transaction = Transaction(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            amount=amount,
            transaction_type='transfer',
            status='completed',
            description=description
        )
        db.session.add(transaction)
        db.session.commit()
        return jsonify({
            "message": "Transfer successful",
            "from_account": from_account.to_dict(),
            "to_account": to_account.to_dict(),
            "transaction": transaction.to_dict()
        }), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/transactions/<user_id>', methods=['GET'])
@require_api_key
def get_transactions(user_id):
    transactions = Transaction.query.filter(
        (Transaction.from_user_id == user_id) | (Transaction.to_user_id == user_id)
    ).order_by(Transaction.created_at.desc()).all()
    return jsonify([transaction.to_dict() for transaction in transactions]), 200

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
