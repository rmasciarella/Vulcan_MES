"""
Supabase client integration for FastAPI backend.
Provides connection to Supabase for real-time features and storage.
"""

import os
from typing import Optional, Dict, Any
from functools import lru_cache

from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
import httpx

from app.core.config import settings


class SupabaseClient:
    """Wrapper for Supabase client with FastAPI integration."""
    
    def __init__(self):
        self._client: Optional[Client] = None
        self._admin_client: Optional[Client] = None
    
    @property
    def client(self) -> Client:
        """Get the Supabase client with anon key (for public operations)."""
        if not self._client:
            self._client = create_client(
                supabase_url=settings.SUPABASE_URL,
                supabase_key=(settings.SUPABASE_PUBLISHABLE_KEY or settings.SUPABASE_ANON_KEY),
                options=ClientOptions(
                    auto_refresh_token=True,
                    persist_session=False,
                )
            )
        return self._client
    
    @property
    def admin(self) -> Client:
        """Get the Supabase admin client with service key (for admin operations)."""
        if not self._admin_client:
            self._admin_client = create_client(
                supabase_url=settings.SUPABASE_URL,
                supabase_key=(settings.SUPABASE_SECRET or settings.SUPABASE_SERVICE_KEY),
                options=ClientOptions(
                    auto_refresh_token=False,
                    persist_session=False,
                )
            )
        return self._admin_client
    
    async def verify_jwt_token(self, token: str) -> Dict[str, Any]:
        """Verify a Supabase JWT token and return user data."""
        try:
            # Set the auth header for this request
            self.client.auth.set_session(token)
            user = self.client.auth.get_user(token)
            return user.dict() if user else None
        except Exception as e:
            print(f"Error verifying Supabase token: {e}")
            return None
    
    def get_user_client(self, access_token: str) -> Client:
        """Get a Supabase client authenticated with a user's access token."""
        client = create_client(
            supabase_url=settings.SUPABASE_URL,
            supabase_key=settings.SUPABASE_ANON_KEY,
            options=ClientOptions(
                headers={"Authorization": f"Bearer {access_token}"},
                auto_refresh_token=False,
                persist_session=False,
            )
        )
        return client
    
    async def sync_user_to_local_db(self, supabase_user: Dict[str, Any], db) -> Any:
        """
        Sync a Supabase user to the local database.
        This ensures users authenticated via Supabase also exist in our local DB.
        """
        from app import crud
        from app.schemas.user import UserCreate
        
        # Check if user exists in local DB
        local_user = crud.user.get_by_email(db, email=supabase_user["email"])
        
        if not local_user:
            # Create user in local DB
            user_in = UserCreate(
                email=supabase_user["email"],
                full_name=supabase_user.get("user_metadata", {}).get("full_name", ""),
                password="supabase_auth",  # Placeholder since auth is handled by Supabase
                is_superuser=False,
                is_active=True,
            )
            local_user = crud.user.create(db, obj_in=user_in)
        
        return local_user
    
    def create_realtime_channel(self, channel_name: str) -> Any:
        """Create a real-time subscription channel."""
        return self.client.channel(channel_name)
    
    async def upload_file(
        self, 
        bucket: str, 
        path: str, 
        file_content: bytes,
        content_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """Upload a file to Supabase Storage."""
        try:
            response = self.admin.storage.from_(bucket).upload(
                path=path,
                file=file_content,
                file_options={"content-type": content_type} if content_type else {}
            )
            return {"success": True, "path": path, "response": response}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_file_url(self, bucket: str, path: str, expires_in: int = 3600) -> str:
        """Get a signed URL for a file in Supabase Storage."""
        try:
            response = self.admin.storage.from_(bucket).create_signed_url(
                path=path,
                expires_in=expires_in
            )
            return response["signedURL"] if response else None
        except Exception as e:
            print(f"Error getting file URL: {e}")
            return None


@lru_cache()
def get_supabase_client() -> SupabaseClient:
    """Get the singleton Supabase client instance."""
    return SupabaseClient()


# Export for easy access
supabase = get_supabase_client()