#!/usr/bin/env python3
"""Clean up all AI bots and related data"""
import sys
import os
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv('.env.local')
load_dotenv('.env')

# Add saas to path
sys.path.insert(0, str(Path(__file__).parent / 'saas'))

from saas.database import get_db

with get_db() as conn:
    cursor = conn.cursor()

    # Delete all AI bots (CASCADE will clean up related tables)
    cursor.execute('DELETE FROM ai_bots')
    deleted = cursor.rowcount
    print(f'✅ Deleted {deleted} AI bots')

    # Verify cleanup
    cursor.execute('SELECT COUNT(*) FROM ai_decisions')
    decisions_count = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM ai_model_performance')
    performance_count = cursor.fetchone()[0]

    print(f'✅ Remaining ai_decisions: {decisions_count}')
    print(f'✅ Remaining ai_model_performance: {performance_count}')

    conn.commit()

print('✅ Cleanup complete!')
