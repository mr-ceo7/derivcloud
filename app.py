from flask import Flask, render_template, jsonify, request, make_response
import threading
import time
import os
import csv
import io
from datetime import datetime
from trading_bot import bot

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def status():
    runtime = "0s"
    if bot.is_running and bot.start_time:
        delta = datetime.now() - bot.start_time
        # Format as HH:MM:SS
        seconds = int(delta.total_seconds())
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        runtime = f"{h:02d}:{m:02d}:{s:02d}"

    return jsonify({
        'is_running': bot.is_running,
        'running_time': runtime,
        'balance': bot.current_balance,
        'profit': round(bot.total_profit, 2),
        'wins': bot.wins,
        'losses': bot.losses,
        'total_trades': bot.total_trades,
        'logs': bot.logs,
        'recent_ticks': [],
        'current_digit': bot.current_digit,
        'settings': {
            'market': bot.market,
            'stake': bot.stake,
            'duration': bot.duration,
            'prediction': bot.prediction_digit,
            'consecutive': bot.consecutive_triggers,
            'smart_mode': bot.smart_mode,
            'token_set': bot.api_token != "YOUR_API_TOKEN"
        }
    })

@app.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.json
    bot.update_settings(
        token=data.get('token'),
        market=data.get('market'),
        stake=data.get('stake'),
        duration=data.get('duration'),
        prediction=data.get('prediction'),
        consecutive=data.get('consecutive'),
        smart_mode=data.get('smart_mode')
    )
    return jsonify({'status': 'success', 'message': 'Settings updated'})

@app.route('/api/start', methods=['POST'])
def start_bot():
    if not bot.api_token:
        return jsonify({'status': 'error', 'message': 'API Token missing'}), 400
    bot.start_bot()
    return jsonify({'status': 'success', 'message': 'Bot started'})

@app.route('/api/stop', methods=['POST'])
def stop_bot():
    bot.stop_bot()
    return jsonify({'status': 'success', 'message': 'Bot stopped'})

@app.route('/api/reset', methods=['POST'])
def reset_bot():
    bot.reset_stats()
    return jsonify({'status': 'success', 'message': 'Stats reset'})

@app.route('/api/export_logs')
def export_logs():
    si = io.StringIO()
    cw = csv.writer(si)
    # Header
    cw.writerow(["Contract ID", "Type", "Entry Time", "Entry Quote", "Entry Digit", "Exit Time", "Exit Quote", "Exit Digit", "Status", "Profit"])
    
    # Rows
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
    output.headers["Content-Disposition"] = "attachment; filename=trading_logs.csv"
    output.headers["Content-type"] = "text/csv"
    return output

if __name__ == '__main__':
    # Threaded mode is essential for the bot background thread to work alongside Flask dev server
    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)
