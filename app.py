from flask import Flask, render_template, jsonify, request
from trading_bot import bot
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    return jsonify({
        'is_running': bot.is_running,
        'balance': bot.current_balance,
        'profit': round(bot.total_profit, 2),
        'wins': bot.wins,
        'losses': bot.losses,
        'total_trades': bot.total_trades,
        'logs': bot.logs,
        'settings': {
            'market': bot.market,
            'stake': bot.stake,
            'duration': bot.duration,
            'prediction': bot.prediction_digit,
            'consecutive': bot.consecutive_triggers,
            'token_set': bool(bot.api_token)
        }
    })

@app.route('/api/settings', methods=['POST'])
def update_settings():
    data = request.json
    bot.update_settings(
        token=data.get('token') or bot.api_token,
        market=data.get('market'),
        stake=data.get('stake'),
        duration=data.get('duration'),
        prediction=data.get('prediction'),
        consecutive=data.get('consecutive')
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

if __name__ == '__main__':
    # Threaded mode is essential for the bot background thread to work alongside Flask dev server
    app.run(debug=True, host='0.0.0.0', port=5001, threaded=True)
