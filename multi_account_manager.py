import asyncio
import signal
import sys
from typing import Dict, List
from datetime import datetime
from database import DatabaseManager, FanvueAccount
from fanvue_responder_enhanced import EnhancedFanvueAutoResponder

class MultiAccountManager:
    def __init__(self, llm_config: dict):
        """
        Initialize the Multi-Account Manager
        
        Args:
            llm_config: Dictionary containing LLM configuration
        """
        self.llm_config = llm_config
        self.db_manager = DatabaseManager()
        self.responders: Dict[str, EnhancedFanvueAutoResponder] = {}
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.shutdown_event = asyncio.Event()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        print("🚀 Multi-Account Manager initialized")

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"\n🛑 Received signal {signum}, initiating graceful shutdown...")
        asyncio.create_task(self.shutdown())

    async def shutdown(self):
        """Gracefully shutdown all tasks"""
        print("🛑 Shutting down all account monitors...")
        self.shutdown_event.set()
        
        # Cancel all running tasks
        for account_id, task in self.running_tasks.items():
            print(f"📴 Stopping monitor for account {account_id}")
            task.cancel()
            
        # Wait for all tasks to complete
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks.values(), return_exceptions=True)
        
        # Save all responder states
        for account_id, responder in self.responders.items():
            responder.save_state()
            print(f"💾 Saved state for account {account_id}")
        
        # Close database connection
        await self.db_manager.close()
        print("✅ Graceful shutdown completed")

    async def load_accounts_from_database(self) -> List[FanvueAccount]:
        """Load all active Fanvue accounts from database"""
        try:
            accounts = await self.db_manager.get_all_fanvue_accounts()
            print(f"📊 Loaded {len(accounts)} active accounts from database")
            return accounts
        except Exception as e:
            print(f"❌ Error loading accounts from database: {e}")
            return []

    async def create_responder_for_account(self, account: FanvueAccount) -> EnhancedFanvueAutoResponder:
        """Create a responder instance for a specific account"""
        try:
            responder = EnhancedFanvueAutoResponder(account, self.llm_config)
            return responder
        except Exception as e:
            print(f"❌ Error creating responder for account {account.id}: {e}")
            return None

    async def monitor_account_continuously(self, account: FanvueAccount):
        """Continuously monitor a single account for new messages"""
        responder = await self.create_responder_for_account(account)
        if not responder:
            return
        
        self.responders[account.id] = responder
        
        print(f"🔄 Starting continuous monitoring for account {account.id}")
        consecutive_errors = 0
        max_consecutive_errors = 5
        
        try:
            while not self.shutdown_event.is_set():
                try:
                    # Run a single monitoring cycle
                    message_count = await responder.monitor_single_cycle()
                    
                    if message_count > 0:
                        print(f"✅ Processed {message_count} message(s) for account {account.id}")
                        consecutive_errors = 0  # Reset error counter on success
                    
                    # Very brief pause to prevent excessive CPU usage
                    # This is much shorter than the original 60-second delay
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    consecutive_errors += 1
                    print(f"❌ Error in monitoring cycle for account {account.id} (Error {consecutive_errors}/{max_consecutive_errors}): {e}")
                    
                    if consecutive_errors >= max_consecutive_errors:
                        print(f"🚨 Too many consecutive errors for account {account.id}, stopping monitor")
                        break
                    
                    # Wait a bit longer on errors to avoid spam
                    await asyncio.sleep(5)
                    
        except asyncio.CancelledError:
            print(f"📴 Monitor for account {account.id} was cancelled")
        except Exception as e:
            print(f"❌ Fatal error in monitor for account {account.id}: {e}")
        finally:
            # Clean up
            if account.id in self.responders:
                self.responders[account.id].save_state()
                del self.responders[account.id]
            if account.id in self.running_tasks:
                del self.running_tasks[account.id]

    async def start_monitoring_all_accounts(self):
        """Start monitoring all accounts concurrently"""
        # Load accounts from database
        accounts = await self.load_accounts_from_database()
        
        if not accounts:
            print("❌ No active accounts found. Exiting...")
            return
        
        print(f"🚀 Starting monitoring for {len(accounts)} accounts")
        
        # Create and start monitoring tasks for each account
        for account in accounts:
            task = asyncio.create_task(self.monitor_account_continuously(account))
            self.running_tasks[account.id] = task
            print(f"▶️  Started monitor for account {account.id}")
        
        # Wait for shutdown signal or all tasks to complete
        try:
            await self.shutdown_event.wait()
        except KeyboardInterrupt:
            print("\n🛑 Received keyboard interrupt")
        
        await self.shutdown()

    async def periodic_account_refresh(self):
        """Periodically check for new accounts in the database"""
        print("🔄 Starting periodic account refresh task")
        
        while not self.shutdown_event.is_set():
            try:
                # Wait 5 minutes before checking for new accounts
                await asyncio.wait_for(self.shutdown_event.wait(), timeout=300)
                break  # If shutdown event is set, exit
            except asyncio.TimeoutError:
                pass  # Continue to check for new accounts
            
            try:
                # Load current accounts from database
                current_accounts = await self.load_accounts_from_database()
                current_account_ids = {acc.id for acc in current_accounts}
                running_account_ids = set(self.running_tasks.keys())
                
                # Start monitoring for new accounts
                new_account_ids = current_account_ids - running_account_ids
                for account in current_accounts:
                    if account.id in new_account_ids:
                        print(f"🆕 Found new account {account.id}, starting monitor")
                        task = asyncio.create_task(self.monitor_account_continuously(account))
                        self.running_tasks[account.id] = task
                
                # Stop monitoring for removed/expired accounts
                removed_account_ids = running_account_ids - current_account_ids
                for account_id in removed_account_ids:
                    print(f"🗑️  Account {account_id} removed/expired, stopping monitor")
                    if account_id in self.running_tasks:
                        self.running_tasks[account_id].cancel()
                
            except Exception as e:
                print(f"❌ Error during periodic account refresh: {e}")

    async def run(self):
        """Main entry point to run the multi-account manager"""
        print("🌟 Starting Multi-Account Fanvue Auto Responder System")
        print("📡 This system will monitor ALL accounts in the database continuously")
        print("🔄 New accounts will be detected automatically every 5 minutes")
        print("Press Ctrl+C to stop gracefully\n")
        
        try:
            # Start the account refresh task
            refresh_task = asyncio.create_task(self.periodic_account_refresh())
            
            # Start monitoring all current accounts
            await self.start_monitoring_all_accounts()
            
            # Cancel refresh task if we're shutting down
            refresh_task.cancel()
            
        except Exception as e:
            print(f"❌ Fatal error in multi-account manager: {e}")
            await self.shutdown()

def main():
    """Main function to start the multi-account manager"""
    
    # LLM Configuration - you can modify these settings
    LLM_CONFIG = {
        "api_key": "SHHHNXH43KX5AF986LR7WEPFFILV6OKKKIT4NVSF",
        "model": "Sao10K/L3-8B-Stheno-v3.2",
        "base_url": "https://c40shf7xpyl0ky-8000.proxy.runpod.net/v1",
        "temperature": 0.7
    }
    
    # Create and run the manager
    manager = MultiAccountManager(LLM_CONFIG)
    
    try:
        asyncio.run(manager.run())
    except KeyboardInterrupt:
        print("\n🛑 Received keyboard interrupt, shutting down...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
    finally:
        print("👋 Multi-Account Manager stopped")

if __name__ == "__main__":
    main()
