"""
Sync available models from OpenRouter API
Run this daily via cron to keep models up-to-date
"""
import os
import sys
import requests
import logging
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from saas.database import get_connection

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

OPENROUTER_API = "https://openrouter.ai/api/v1/models"

# Model categorization thresholds (avg price per 1M tokens)
BUDGET_MAX = 1.0      # < $1/1M tokens average
RECOMMENDED_MAX = 10.0  # $1-10/1M tokens average
# Premium: > $10/1M tokens average

# Models to exclude (not suitable for trading decisions)
EXCLUDE_KEYWORDS = [
    'vision', 'image', 'video', 'audio', 'whisper', 'tts',
    'embedding', 'moderation', 'dall-e', 'stable-diffusion',
    'playground', 'midjourney'
]

# Models to mark as recommended (proven good for trading)
RECOMMENDED_MODELS = [
    'openai/gpt-4o-mini',
    'anthropic/claude-sonnet-4.5',
    'google/gemini-2.5-flash-preview',
    'deepseek/deepseek-v3.1-terminus',
    'qwen/qwen-plus-2025-07-28',
    'google/gemini-2.5-flash-lite-preview'
]


def fetch_openrouter_models():
    """Fetch all models from OpenRouter API"""
    try:
        logger.info(f"🔄 Fetching models from {OPENROUTER_API}")
        response = requests.get(OPENROUTER_API, timeout=15)
        response.raise_for_status()

        data = response.json()
        models = data.get('data', [])

        logger.info(f"📊 Fetched {len(models)} total models from OpenRouter")
        return models

    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Error fetching models from OpenRouter: {e}")
        raise


def calculate_avg_price(model):
    """Calculate average price per 1M tokens"""
    try:
        # Prices are in format "0.00000015" (per token)
        # Convert to per 1M tokens
        prompt_price = float(model['pricing']['prompt']) * 1_000_000
        completion_price = float(model['pricing']['completion']) * 1_000_000

        # Average of input and output
        avg_price = (prompt_price + completion_price) / 2

        return prompt_price, completion_price, avg_price

    except (KeyError, ValueError, TypeError) as e:
        logger.warning(f"⚠️ Error calculating price for {model.get('id', 'unknown')}: {e}")
        return 0, 0, 0


def categorize_model(model, avg_price):
    """Categorize model based on pricing and performance"""
    model_id = model['id']

    # Check if in recommended list
    if model_id in RECOMMENDED_MODELS:
        return 'recommended', 'balanced'

    # Categorize by price
    if avg_price < BUDGET_MAX:
        return 'budget', 'fast'
    elif avg_price < RECOMMENDED_MAX:
        return 'recommended', 'balanced'
    else:
        return 'premium', 'highest'


def should_include_model(model):
    """Filter models suitable for trading decisions"""
    model_id = model['id'].lower()
    model_name = model.get('name', '').lower()

    # Exclude by keywords
    for keyword in EXCLUDE_KEYWORDS:
        if keyword in model_id or keyword in model_name:
            return False

    # Only include chat/completion models
    architecture = model.get('architecture', {})
    modality = architecture.get('modality', '').lower()

    if 'text->text' not in modality and 'chat' not in modality:
        return False

    # Exclude models with extremely high pricing (>$150/1M avg)
    _, _, avg_price = calculate_avg_price(model)
    if avg_price > 150:
        logger.debug(f"Excluding {model['id']} - price too high (${avg_price:.2f}/1M avg)")
        return False

    # Exclude models with zero context length
    context_length = model.get('context_length', 0)
    if context_length == 0:
        logger.debug(f"Excluding {model['id']} - no context length")
        return False

    return True


def sync_models():
    """Sync models from OpenRouter to database"""
    try:
        # Fetch models
        all_models = fetch_openrouter_models()

        # Filter suitable models
        suitable_models = [m for m in all_models if should_include_model(m)]
        logger.info(f"✅ {len(suitable_models)} models suitable for trading (filtered from {len(all_models)})")

        # Connect to database
        conn = get_connection()
        cursor = conn.cursor()

        synced_count = 0
        skipped_count = 0

        for model in suitable_models:
            try:
                # Calculate pricing
                prompt_per_1m, completion_per_1m, avg_price = calculate_avg_price(model)

                # Categorize
                category, tier = categorize_model(model, avg_price)

                # Extract data
                model_id = model['id']
                model_name = model['name']
                context_length = model.get('context_length', 0)

                # Upsert model
                cursor.execute("""
                    INSERT INTO ai_model_configs
                    (name, provider, api_endpoint, model_identifier,
                     cost_per_1m_input, cost_per_1m_output, context_length,
                     category, performance_tier, is_active, synced_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (provider, model_identifier)
                    DO UPDATE SET
                        name = EXCLUDED.name,
                        cost_per_1m_input = EXCLUDED.cost_per_1m_input,
                        cost_per_1m_output = EXCLUDED.cost_per_1m_output,
                        context_length = EXCLUDED.context_length,
                        category = EXCLUDED.category,
                        performance_tier = EXCLUDED.performance_tier,
                        synced_at = NOW()
                """, (
                    model_name,
                    'openrouter',
                    'https://openrouter.ai/api/v1/chat/completions',
                    model_id,
                    prompt_per_1m,
                    completion_per_1m,
                    context_length,
                    category,
                    tier,
                    True  # is_active
                ))

                synced_count += 1

                if synced_count % 50 == 0:
                    logger.info(f"📝 Synced {synced_count}/{len(suitable_models)} models...")

            except Exception as e:
                logger.error(f"❌ Error syncing model {model.get('id', 'unknown')}: {e}")
                skipped_count += 1
                continue

        # Commit changes
        conn.commit()

        # Get stats
        cursor.execute("""
            SELECT
                category,
                COUNT(*) as count,
                AVG(cost_per_1m_input) as avg_input_cost,
                AVG(cost_per_1m_output) as avg_output_cost
            FROM ai_model_configs
            WHERE provider = 'openrouter' AND is_active = true
            GROUP BY category
            ORDER BY category
        """)

        stats = cursor.fetchall()

        cursor.close()
        conn.close()

        # Print summary
        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Model sync complete!")
        logger.info(f"{'='*60}")
        logger.info(f"✅ Successfully synced: {synced_count} models")
        logger.info(f"⚠️ Skipped: {skipped_count} models")
        logger.info(f"\n📊 Category Breakdown:")
        logger.info(f"{'-'*60}")
        logger.info(f"{'Category':<15} {'Count':<8} {'Avg Input':<15} {'Avg Output':<15}")
        logger.info(f"{'-'*60}")

        for category, count, avg_in, avg_out in stats:
            logger.info(
                f"{category:<15} {count:<8} "
                f"${float(avg_in):<14.2f} ${float(avg_out):<14.2f}"
            )

        logger.info(f"{'-'*60}")
        logger.info(f"🕐 Sync completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return synced_count

    except Exception as e:
        logger.error(f"❌ Fatal error during sync: {e}")
        raise


if __name__ == '__main__':
    try:
        synced_count = sync_models()
        sys.exit(0)
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        sys.exit(1)
