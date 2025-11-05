#!/usr/bin/env python3
"""
Test AI Bot Executor
Inserts a test AI bot and runs the executor to verify end-to-end integration
"""

import os
import sys

# Set required environment variables
os.environ['DATABASE_URL'] = 'postgresql://dcabot:dcabot_dev_password@localhost:5435/dcabot_dev'
os.environ['ENCRYPTION_KEY'] = 'rP1PrLu4WNeIU1U6kR5klFil5d7SJjTPe36eNrvCll0='  # Valid Fernet key

# Your actual API keys (from conversation summary)
PHEMEX_API_KEY = '540fcfd6-0310-47eb-a0a6-29ef4dcad4f9'
PHEMEX_API_SECRET = 'wCL5bS8BWY2lRtejV1Pzz_F5Upyr8A2YuO09nn1vzo04OTA3MTllYi00NDcyLTQxODgtYmU3NS05NzJkMDUzZjRmNzI'

# Get GLM API key from environment (you need to set this)
GLM_API_KEY = os.getenv('GLM_API_KEY', '')

if not GLM_API_KEY:
    print("❌ Please set GLM_API_KEY environment variable")
    print("   Get your key from: https://open.bigmodel.cn/")
    sys.exit(1)

from saas import database as db
from saas.security import encrypt_api_key
from saas.execute_ai_bots import AIBotExecutor

print("=" * 60)
print("AI Bot Executor Test")
print("=" * 60)

# Step 1: Get or create test user
print("\n1️⃣ Finding/creating test user...")
with db.get_db() as conn:
    cursor = conn.cursor()

    # Check if test user exists
    cursor.execute("SELECT id FROM users WHERE email = %s", ('test@example.com',))
    user = cursor.fetchone()

    if not user:
        print("   Creating test user...")
        cursor.execute("""
            INSERT INTO users (email, password_hash, is_active, is_approved)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        """, ('test@example.com', 'dummy_hash', True, True))
        user_id = cursor.fetchone()[0]
        print(f"   ✅ Created test user: {user_id}")
    else:
        user_id = user[0]
        print(f"   ✅ Using existing test user: {user_id}")

# Step 2: Get GLM-4.5-Air model config
print("\n2️⃣ Getting AI model config...")
with db.get_db() as conn:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, name FROM ai_model_configs
        WHERE model_identifier = 'glm-4.5-air'
    """)
    model = cursor.fetchone()
    if not model:
        print("   ❌ GLM-4.5-Air model not found in database!")
        sys.exit(1)

    model_config_id, model_name = model
    print(f"   ✅ Using model: {model_name} (ID: {model_config_id})")

# Step 3: Create test AI bot
print("\n3️⃣ Creating test AI bot...")
with db.get_db() as conn:
    cursor = conn.cursor()

    # Delete existing test bot if exists
    cursor.execute("""
        DELETE FROM ai_bots
        WHERE user_id = %s AND name = 'Test BTC Bot'
    """, (user_id,))

    # Encrypt API keys
    encrypted_phemex_key = encrypt_api_key(PHEMEX_API_KEY)
    encrypted_phemex_secret = encrypt_api_key(PHEMEX_API_SECRET)
    encrypted_glm_key = encrypt_api_key(GLM_API_KEY)

    # Insert test bot
    cursor.execute("""
        INSERT INTO ai_bots (
            user_id, name, model_config_id, symbol, side, leverage,
            max_position_size, is_active, automatic_mode,
            exchange_api_key, exchange_api_secret, ai_api_key
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
        RETURNING id
    """, (
        user_id, 'Test BTC Bot', model_config_id, 'BTCUSDT', 'Long', 5,
        0.03, True, False,  # automatic_mode=False for testing
        encrypted_phemex_key, encrypted_phemex_secret, encrypted_glm_key
    ))

    bot_id = cursor.fetchone()[0]
    print(f"   ✅ Created AI bot: {bot_id}")

# Step 4: Run executor
print("\n4️⃣ Running AI bot executor...")
print("=" * 60)

try:
    executor = AIBotExecutor()
    executor.execute_all_bots()
    print("\n" + "=" * 60)
    print("✅ Executor completed successfully!")

except Exception as e:
    print("\n" + "=" * 60)
    print(f"❌ Executor failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 5: Check results
print("\n5️⃣ Checking results...")
with db.get_db() as conn:
    cursor = conn.cursor()

    # Get latest decision
    cursor.execute("""
        SELECT decision, confidence, reasoning, api_cost, response_time_ms
        FROM ai_decisions
        WHERE ai_bot_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """, (bot_id,))

    decision = cursor.fetchone()
    if decision:
        print(f"   Decision: {decision[0]}")
        print(f"   Confidence: {decision[1]}%")
        print(f"   Reasoning: {decision[2][:100]}...")
        print(f"   API Cost: ${decision[3]:.6f}")
        print(f"   Response Time: {decision[4]}ms")
        print("\n✅ Test completed successfully!")
    else:
        print("   ⚠️  No decision logged")

print("=" * 60)
