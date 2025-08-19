#!/usr/bin/env python3
"""
Multi-Account Fanvue Auto Responder System

This script starts the multi-account system that:
1. Connects to the PostgreSQL database
2. Loads all active FanvueAccount records
3. Runs monitoring for each account concurrently
4. Uses each account's specific API key and system prompt
5. Continuously monitors for new messages without delays
6. Automatically detects new accounts every 5 minutes

Usage:
    python run_multi_account_system.py

Requirements:
    - Install dependencies: pip install -r requirements.txt
    - Database must be accessible and contain FanvueAccount table
    - LLM endpoint must be accessible

Press Ctrl+C to stop gracefully.
"""

import sys
import asyncio
from multi_account_manager import main

if __name__ == "__main__":
    print("🌟 Multi-Account Fanvue Auto Responder System")
    print("=" * 50)
    print()
    
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n🛑 System stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ System error: {e}")
        sys.exit(1)
