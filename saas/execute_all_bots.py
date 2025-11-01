#!/usr/bin/env python3
"""
Execute all active bots once (called by Render Cron Job every 5 minutes)
"""
import os
import sys
import subprocess
import logging
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from saas.database import get_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def log_bot_execution(bot_id: int, level: str, message: str):
    """Log bot execution to database"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO bot_logs (bot_id, level, message, created_at)
                VALUES (%s, %s, %s, NOW())
            """, (bot_id, level, message))
            conn.commit()
    except Exception as e:
        logger.error(f"Failed to log bot execution: {e}")


def persist_execution_metrics(bot_id: int, metrics_list: list, execution_time_seconds: float):
    """Persist execution metrics to database for graphing and analysis"""
    if not metrics_list:
        return

    try:
        execution_time_ms = int(execution_time_seconds * 1000)

        with get_db() as conn:
            cursor = conn.cursor()

            for metrics in metrics_list:
                cursor.execute("""
                    INSERT INTO execution_metrics (
                        bot_id, symbol, executed_at,
                        total_balance, position_size, position_value,
                        unrealized_pnl, unrealized_pnl_pct, margin_level,
                        entry_price, current_price, leverage, side,
                        action, conclusion, ema_200, ema_50, execution_time_ms
                    ) VALUES (
                        %s, %s, NOW(),
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    )
                """, (
                    bot_id,
                    metrics.get('symbol'),
                    metrics.get('total_balance'),
                    metrics.get('position_size'),
                    metrics.get('position_value'),
                    metrics.get('unrealized_pnl'),
                    metrics.get('unrealized_pnl_pct'),
                    metrics.get('margin_level'),
                    metrics.get('entry_price'),
                    metrics.get('current_price'),
                    metrics.get('leverage'),
                    metrics.get('side'),
                    metrics.get('action'),
                    metrics.get('conclusion'),
                    metrics.get('ema_200'),
                    metrics.get('ema_50'),
                    execution_time_ms
                ))

            conn.commit()
            logger.info(f"✅ Persisted {len(metrics_list)} execution metric(s) for bot {bot_id}")

    except Exception as e:
        logger.error(f"Failed to persist execution metrics: {e}")


def execute_bot(bot_id: int):
    """Execute a single bot by calling main.py with BOT_ID"""
    from datetime import datetime
    start_time = datetime.now()

    # Log execution start
    log_bot_execution(bot_id, 'INFO', '🤖 Bot execution started')

    try:
        env = os.environ.copy()
        env['BOT_ID'] = str(bot_id)

        # Ensure required env vars are passed to subprocess
        # These are needed for database access and API key decryption
        required_vars = ['DATABASE_URL', 'ENCRYPTION_KEY']
        for var in required_vars:
            if var not in env:
                logger.warning(f"{var} not set in environment")

        # Use the same Python interpreter that's running this script
        # This ensures we use the venv Python locally and the correct Python in production
        python_executable = sys.executable

        result = subprocess.run(
            [python_executable, 'main.py'],
            env=env,
            capture_output=True,
            text=True,
            timeout=120  # 2 min timeout per bot
        )

        execution_time = (datetime.now() - start_time).total_seconds()

        if result.returncode == 0:
            logger.info(f"✅ Bot {bot_id} executed successfully")

            # Parse execution conclusions and metrics from stdout
            conclusions = []
            metrics_list = []

            if result.stdout:
                import json
                for line in result.stdout.split('\n'):
                    if 'EXECUTION_CONCLUSION:' in line:
                        # Extract conclusion after the marker
                        conclusion_text = line.split('EXECUTION_CONCLUSION:', 1)[1].strip()
                        conclusions.append(conclusion_text)
                        # Log each conclusion separately
                        log_bot_execution(bot_id, 'INFO', f'📊 {conclusion_text}')

                    elif 'EXECUTION_METRICS:' in line:
                        # Extract and parse metrics JSON
                        try:
                            metrics_json = line.split('EXECUTION_METRICS:', 1)[1].strip()
                            metrics = json.loads(metrics_json)
                            metrics_list.append(metrics)
                        except json.JSONDecodeError as e:
                            logger.error(f"Failed to parse metrics JSON: {e}")

            # Persist metrics to database
            persist_execution_metrics(bot_id, metrics_list, execution_time)

            # Log overall completion
            conclusions_summary = f" with {len(conclusions)} pair(s)" if conclusions else ""
            log_bot_execution(bot_id, 'INFO', f'✅ Execution completed successfully ({execution_time:.1f}s){conclusions_summary}')
            return True
        else:
            logger.error(f"❌ Bot {bot_id} failed: {result.stderr}")
            error_msg = result.stderr[:200] if result.stderr else "Unknown error"
            log_bot_execution(bot_id, 'ERROR', f'❌ Execution failed: {error_msg}')
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"⏱ Bot {bot_id} execution timeout (>2 min)")
        log_bot_execution(bot_id, 'ERROR', '⏱ Execution timeout (>2 minutes)')
        return False
    except Exception as e:
        logger.error(f"❌ Bot {bot_id} error: {e}")
        log_bot_execution(bot_id, 'ERROR', f'❌ Execution error: {str(e)}')
        return False


def main():
    logger.info("🤖 Starting bot execution cycle")

    try:
        # Get all active bots from database
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, user_id
                FROM bots
                WHERE status = 'running'
                ORDER BY id
            """)
            active_bots = cursor.fetchall()

        if not active_bots:
            logger.info("No active bots to execute")
            return

        logger.info(f"Found {len(active_bots)} active bots")

        # Execute each bot
        success_count = 0
        for bot_id, bot_name, user_id in active_bots:
            logger.info(f"Executing bot {bot_id} ({bot_name}) for user {user_id}")
            if execute_bot(bot_id):
                success_count += 1

        logger.info(f"✅ Execution cycle complete: {success_count}/{len(active_bots)} successful")

    except Exception as e:
        logger.error(f"❌ Execution cycle failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
