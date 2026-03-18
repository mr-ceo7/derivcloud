from flask import Flask, render_template, jsonify, request, make_response, send_from_directory, session, redirect, url_for
import threading
import time
import os
import csv
import io
import json
from datetime import datetime
from trading_bot import manager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'deriv-bot-secret-key-x9k2m'

# ── Collaborator Data ──────────────────────────────────────────────

COLLAB_FILE = os.path.join(os.path.dirname(__file__), 'collaborators.json')

def load_collab_data():
    """Load collaborator data from JSON file."""
    try:
        with open(COLLAB_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        default = {
            'admin_password': 'admin123',
            'viewer_password': 'view123',
            'collaborators': []
        }
        save_collab_data(default)
        return default

def save_collab_data(data):
    """Save collaborator data to JSON file."""
    with open(COLLAB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ── Auth Helpers ───────────────────────────────────────────────────

def require_login(f):
    """Decorator: require any login (admin or viewer)."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'role' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    """Decorator: require admin login."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get('role') != 'admin':
            return jsonify({'status': 'error', 'message': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

# ── Auth Routes ────────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password', '')
        data = load_collab_data()
        if password == data['admin_password']:
            session['role'] = 'admin'
            return redirect(url_for('index'))
        elif password == data['viewer_password']:
            session['role'] = 'viewer'
            return redirect(url_for('viewer'))
        else:
            return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ── Page Routes ────────────────────────────────────────────────────

@app.route('/')
@require_login
def index():
    if session.get('role') == 'viewer':
        return redirect(url_for('viewer'))
    return render_template('index.html', is_readonly=False, role='admin')

@app.route('/viewer')
@require_login
def viewer():
    return render_template('index.html', is_readonly=True, role='viewer')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.png', mimetype='image/png')

# ── Multi-Account API ──────────────────────────────────────────────

@app.route('/api/status')
@require_login
def status():
    return jsonify({
        'accounts': manager.get_all_statuses(),
        'total_profit': manager.total_profit(),
        'active_count': manager.active_count(),
        'total_accounts': len(manager.bots)
    })

@app.route('/api/add_account', methods=['POST'])
@require_admin
def add_account():
    data = request.json
    token = data.get('token')
    if not token:
        return jsonify({'status': 'error', 'message': 'Token is required'}), 400
    try:
        account_id, balance, currency = manager.add_account(token)
        return jsonify({
            'status': 'success',
            'message': f'Account {account_id} added',
            'account_id': account_id,
            'balance': balance,
            'currency': currency
        })
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/remove_account', methods=['POST'])
@require_admin
def remove_account():
    data = request.json
    account_id = data.get('account_id')
    try:
        manager.remove_account(account_id)
        return jsonify({'status': 'success', 'message': f'Account {account_id} removed'})
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/settings', methods=['POST'])
@require_admin
def update_settings():
    data = request.json
    account_id = data.get('account_id')
    apply_to_all = data.get('apply_to_all', False)

    settings_kwargs = {
        'market': data.get('market'),
        'stake': data.get('stake'),
        'duration': data.get('duration'),
        'prediction': data.get('prediction'),
        'consecutive': data.get('consecutive'),
        'smart_mode': data.get('smart_mode'),
        'take_profit': data.get('take_profit'),
        'strategy': data.get('strategy'),
        'range_barrier': data.get('range_barrier'),
        'range_direction': data.get('range_direction'),
        'martingale_enabled': data.get('martingale_enabled'),
        'martingale_mode': data.get('martingale_mode'),
        'martingale_multiplier': data.get('martingale_multiplier'),
        'martingale_increment': data.get('martingale_increment'),
        'martingale_max_stake': data.get('martingale_max_stake'),
        'trio_role': data.get('trio_role'),
        'trio_trigger': data.get('trio_trigger'),
        'trio_digit': data.get('trio_digit'),
        'duo_role': data.get('duo_role'),
        'duo_trigger': data.get('duo_trigger'),
        'duo_trigger_digit': data.get('duo_trigger_digit'),
        'duo_switch_enabled': data.get('duo_switch_enabled'),
        'duo_switch_after': data.get('duo_switch_after'),
        'cooldown_enabled': data.get('cooldown_enabled'),
        'cooldown_after': data.get('cooldown_after'),
        'cooldown_check': data.get('cooldown_check'),
    }

    if apply_to_all:
        for bot in manager.bots.values():
            bot.update_settings(**settings_kwargs)
        return jsonify({'status': 'success', 'message': 'Settings applied to all accounts'})
    elif account_id:
        try:
            bot = manager.get_account(account_id)
            bot.update_settings(**settings_kwargs)
            return jsonify({'status': 'success', 'message': f'Settings updated for {account_id}'})
        except ValueError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
    else:
        return jsonify({'status': 'error', 'message': 'Provide account_id or set apply_to_all'}), 400

@app.route('/api/start', methods=['POST'])
@require_admin
def start_bot():
    data = request.json
    account_id = data.get('account_id')
    start_all = data.get('start_all', False)

    if start_all:
        for bot in manager.bots.values():
            if not bot.is_running:
                bot.start_bot()
                time.sleep(1.0) # Stagger connections to avoid auth rate limit
        return jsonify({'status': 'success', 'message': 'All bots started'})
    elif account_id:
        try:
            bot = manager.get_account(account_id)
            bot.start_bot()
            return jsonify({'status': 'success', 'message': f'{account_id} started'})
        except ValueError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
    else:
        return jsonify({'status': 'error', 'message': 'Provide account_id or start_all'}), 400

@app.route('/api/stop', methods=['POST'])
@require_admin
def stop_bot():
    data = request.json
    account_id = data.get('account_id')
    stop_all = data.get('stop_all', False)

    if stop_all:
        for bot in manager.bots.values():
            if bot.is_running:
                bot.stop_bot()
        return jsonify({'status': 'success', 'message': 'All bots stopped'})
    elif account_id:
        try:
            bot = manager.get_account(account_id)
            bot.stop_bot()
            return jsonify({'status': 'success', 'message': f'{account_id} stopped'})
        except ValueError as e:
            return jsonify({'status': 'error', 'message': str(e)}), 400
    else:
        return jsonify({'status': 'error', 'message': 'Provide account_id or stop_all'}), 400

@app.route('/api/reset', methods=['POST'])
@require_admin
def reset_bot():
    data = request.json
    account_id = data.get('account_id')
    try:
        bot = manager.get_account(account_id)
        bot.reset_stats()
        return jsonify({'status': 'success', 'message': f'{account_id} stats reset'})
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/export_logs')
@require_login
def export_logs():
    account_id = request.args.get('account_id')
    try:
        bot = manager.get_account(account_id)
    except ValueError:
        return "Account not found", 404

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Contract ID", "Type", "Entry Time", "Entry Quote", "Entry Digit", "Exit Time", "Exit Quote", "Exit Digit", "Status", "Profit"])
    
    for trade in bot.trade_history:
        cw.writerow([
            trade.get("Contract ID"),
            trade.get("Type"),
            trade.get("Entry Time"),
            trade.get("Entry Quote"),
            trade.get("Entry Digit"),
            trade.get("Exit Time"),
            trade.get("Exit Quote"),
            trade.get("Exit Digit"),
            trade.get("Status"),
            trade.get("Profit")
        ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=trading_logs_{account_id}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route('/api/export_all_logs')
@require_login
def export_all_logs():
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Account", "Contract ID", "Type", "Entry Time", "Entry Quote", "Entry Digit", "Exit Time", "Exit Quote", "Exit Digit", "Status", "Profit"])
    
    for account_id, bot in manager.bots.items():
        for trade in bot.trade_history:
            cw.writerow([
                account_id,
                trade.get("Contract ID"),
                trade.get("Type"),
                trade.get("Entry Time"),
                trade.get("Entry Quote"),
                trade.get("Entry Digit"),
                trade.get("Exit Time"),
                trade.get("Exit Quote"),
                trade.get("Exit Digit"),
                trade.get("Status"),
                trade.get("Profit")
            ])
        
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=trading_logs_all.csv"
    output.headers["Content-type"] = "text/csv"
    return output

# ── Collaborator API ───────────────────────────────────────────────

@app.route('/api/collaborators')
@require_login
def get_collaborators():
    """Get all collaborators with P/L breakdown."""
    data = load_collab_data()
    collabs = data.get('collaborators', [])
    net_pnl = manager.total_profit()
    num_collabs = len(collabs)
    
    breakdown = []
    for c in collabs:
        if net_pnl >= 0:
            # Profit: split by percentage
            share = round(net_pnl * (c['percentage'] / 100), 2)
        else:
            # Loss: split equally
            share = round(net_pnl / num_collabs, 2) if num_collabs > 0 else 0
        breakdown.append({
            'name': c['name'],
            'percentage': c['percentage'],
            'pnl': share
        })
    
    return jsonify({
        'collaborators': breakdown,
        'net_pnl': net_pnl
    })

@app.route('/api/collaborators', methods=['POST'])
@require_admin
def add_collaborator():
    """Add a new collaborator."""
    req = request.json
    name = req.get('name', '').strip()
    percentage = req.get('percentage')
    
    if not name:
        return jsonify({'status': 'error', 'message': 'Name is required'}), 400
    if percentage is None:
        return jsonify({'status': 'error', 'message': 'Percentage is required'}), 400
    
    try:
        percentage = float(percentage)
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Invalid percentage'}), 400
    
    if percentage <= 0 or percentage > 100:
        return jsonify({'status': 'error', 'message': 'Percentage must be between 0 and 100'}), 400
    
    data = load_collab_data()
    collabs = data.get('collaborators', [])
    
    # Check total doesn't exceed 100
    current_total = sum(c['percentage'] for c in collabs)
    if current_total + percentage > 100:
        return jsonify({'status': 'error', 'message': f'Total would be {current_total + percentage}%. Max is 100%.'}), 400
    
    # Check duplicate name
    if any(c['name'].lower() == name.lower() for c in collabs):
        return jsonify({'status': 'error', 'message': f'{name} already exists'}), 400
    
    collabs.append({'name': name, 'percentage': percentage})
    data['collaborators'] = collabs
    save_collab_data(data)
    
    return jsonify({'status': 'success', 'message': f'{name} added with {percentage}%'})

@app.route('/api/collaborators', methods=['DELETE'])
@require_admin
def remove_collaborator():
    """Remove a collaborator by name."""
    req = request.json
    name = req.get('name', '').strip()
    
    data = load_collab_data()
    collabs = data.get('collaborators', [])
    original_len = len(collabs)
    collabs = [c for c in collabs if c['name'].lower() != name.lower()]
    
    if len(collabs) == original_len:
        return jsonify({'status': 'error', 'message': f'{name} not found'}), 400
    
    data['collaborators'] = collabs
    save_collab_data(data)
    return jsonify({'status': 'success', 'message': f'{name} removed'})

@app.route('/api/passwords', methods=['POST'])
@require_admin
def update_passwords():
    """Update admin and/or viewer passwords."""
    req = request.json
    data = load_collab_data()
    
    if req.get('admin_password'):
        data['admin_password'] = req['admin_password']
    if req.get('viewer_password'):
        data['viewer_password'] = req['viewer_password']
    
    save_collab_data(data)
    return jsonify({'status': 'success', 'message': 'Passwords updated'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True, use_reloader=False)
