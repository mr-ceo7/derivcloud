import time
from trading_bot import manager, global_tick_manager

def on_log(bot_id, message):
    print(f"[Bot {bot_id}] {message}")

def run_test():
    key1 = "PMkMmH6Niqp0cMO"
    key2 = "HONfyqBtnsbp9a4"

    print("Adding accounts...")
    acc1, bal1, cur1 = manager.add_account(key1)
    acc2, bal2, cur2 = manager.add_account(key2)
    print(f"Acct1: {acc1} ({bal1} {cur1})")
    print(f"Acct2: {acc2} ({bal2} {cur2})")

    bot1 = manager.get_account(acc1)
    bot2 = manager.get_account(acc2)

    # Override logging
    bot1.log = lambda msg: on_log(1, msg)
    bot2.log = lambda msg: on_log(2, msg)

    # Set up Range Threshold strategy with consecutive=3 so it takes a few ticks to trigger
    bot1.update_settings(
        market="R_100",
        strategy="range_threshold",
        range_barrier=5,
        range_direction="below",
        consecutive=3,
        stake=0.35,
        take_profit=0  # no TP limit
    )
    bot2.update_settings(
        market="R_100",
        strategy="range_threshold",
        range_barrier=5,
        range_direction="below",
        consecutive=3,
        stake=0.35,
        take_profit=0
    )

    print("Starting bots staggered by 2 seconds...")
    bot1.start_bot()
    time.sleep(2)
    bot2.start_bot()

    print("Letting them run for 60 seconds to collect enough trades...")
    for i in range(60):
        if not bot1.is_running and not bot2.is_running:
            break
        if i % 10 == 0 and i > 0:
            print(f"  [{i}s] Bot1: {bot1.total_trades} trades, Bot2: {bot2.total_trades} trades")
        time.sleep(1)

    print(f"\n===== FINAL RESULTS =====")
    print(f"Bot1: Trades={bot1.total_trades}, W={bot1.wins}, L={bot1.losses}, P/L={bot1.total_profit:.2f}")
    print(f"Bot2: Trades={bot2.total_trades}, W={bot2.wins}, L={bot2.losses}, P/L={bot2.total_profit:.2f}")
    
    if bot1.total_trades == bot2.total_trades:
        print("✅ PERFECT SYNC: Both bots have the same trade count!")
    else:
        print(f"❌ DESYNC: Bot1 has {bot1.total_trades} trades, Bot2 has {bot2.total_trades} trades")
    
    bot1.stop_bot()
    bot2.stop_bot()

if __name__ == "__main__":
    run_test()
