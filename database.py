import asyncpg
import os
from typing import List, Dict, Optional
from datetime import datetime

DATABASE_URL = "postgres://postgres:qQH37KoLqRNPpBOUe9YOtsO42czYJKnCgsmSwmw0KX8EuIcidvgsfxIrrxKwtRyU@5.78.129.71:13442/postgres"

class FanvueAccount:
    def __init__(self, id: str, api_key: str, system_prompt: Optional[str], 
                 expires_at: datetime, created_at: datetime, updated_at: datetime, 
                 user_id: str, llm: Optional[str] = None):
        self.id = id
        self.api_key = api_key
        self.system_prompt = system_prompt
        self.expires_at = expires_at
        self.created_at = created_at
        self.updated_at = updated_at
        self.user_id = user_id
        self.llm = llm

class DatabaseManager:
    def __init__(self, database_url: str = DATABASE_URL):
        self.database_url = database_url
        self.pool = None

    async def connect(self):
        """Create connection pool"""
        try:
            self.pool = await asyncpg.create_pool(
                self.database_url,
                min_size=1,
                max_size=10,
                command_timeout=60
            )
            print("✅ Database connection pool created successfully")
        except Exception as e:
            print(f"❌ Failed to create database connection pool: {e}")
            raise

    async def close(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            print("📁 Database connection pool closed")

    async def get_all_fanvue_accounts(self) -> List[FanvueAccount]:
        """Fetch all active Fanvue accounts from database"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as connection:
                # Get all accounts that haven't expired
                query = """
                    SELECT id, "apiKey", "systemPrompt", "expiresAt", 
                           "createdAt", "updatedAt", "userId", llm
                    FROM "FanvueAccount" 
                    WHERE "expiresAt" > NOW()
                    ORDER BY "createdAt" ASC
                """
                
                rows = await connection.fetch(query)
                accounts = []
                
                for row in rows:
                    account = FanvueAccount(
                        id=row['id'],
                        api_key=row['apiKey'],
                        system_prompt=row['systemPrompt'],
                        expires_at=row['expiresAt'],
                        created_at=row['createdAt'],
                        updated_at=row['updatedAt'],
                        user_id=row['userId'],
                        llm=row['llm']
                    )
                    accounts.append(account)
                
                print(f"📊 Found {len(accounts)} active Fanvue accounts")
                return accounts
                
        except Exception as e:
            print(f"❌ Error fetching Fanvue accounts: {e}")
            return []

    async def check_account_exists(self, api_key: str) -> bool:
        """Check if an account with given API key exists and is active"""
        if not self.pool:
            await self.connect()
        
        try:
            async with self.pool.acquire() as connection:
                query = """
                    SELECT COUNT(*) as count
                    FROM "FanvueAccount" 
                    WHERE "apiKey" = $1 AND "expiresAt" > NOW()
                """
                
                result = await connection.fetchrow(query, api_key)
                return result['count'] > 0
                
        except Exception as e:
            print(f"❌ Error checking account existence: {e}")
            return False
