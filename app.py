from flask import Flask, render_template, jsonify, request, make_response, send_from_directory
import threading
import time
import os
import csv
import io
from datetime import datetime
from trading_bot import manager

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'favicon.png', mimetype='image/png')

# ── Multi-Account API ──────────────────────────────────────────────

@app.route('/api/status')
def status():
    return jsonify({
        'accounts': manager.get_all_statuses(),
        'total_profit': manager.total_profit(),
        'active_count': manager.active_count(),
        'total_accounts': len(manager.bots)
    })

@app.route('/api/add_account', methods=['POST'])
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
def remove_account():
    data = request.json
    account_id = data.get('account_id')
    try:
        manager.remove_account(account_id)
        return jsonify({'status': 'success', 'message': f'Account {account_id} removed'})
    except ValueError as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/api/settings', methods=['POST'])
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

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True, use_reloader=False)
