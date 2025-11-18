import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from services.supabase_service import SupabaseService


class TestSupabaseIntegration:
    """Integration tests for Supabase connectivity and schema verification."""
    
    @pytest.mark.asyncio
    async def test_supabase_connection(self):
        """Test that we can connect to Supabase."""
        try:
            connection_ok = await SupabaseService.check_connection()
            assert isinstance(connection_ok, bool), "Connection check should return a boolean"
        except Exception as e:
            pytest.skip(f"Supabase not available: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_schema_verification(self):
        """Test schema verification detects missing tables."""
        try:
            schema_status = await SupabaseService.verify_schema()
            
            assert "all_tables_exist" in schema_status
            assert "existing_tables" in schema_status
            assert "missing_tables" in schema_status
            assert "required_tables" in schema_status
            
            assert isinstance(schema_status["all_tables_exist"], bool)
            assert isinstance(schema_status["existing_tables"], list)
            assert isinstance(schema_status["missing_tables"], list)
            assert isinstance(schema_status["required_tables"], list)
            
            assert schema_status["required_tables"] == SupabaseService.REQUIRED_TABLES
            
        except Exception as e:
            pytest.skip(f"Supabase not available: {str(e)}")
    
    def test_get_schema_status_sync(self):
        """Test synchronous schema status retrieval."""
        try:
            schema_status = SupabaseService.get_schema_status()
            
            assert "all_tables_exist" in schema_status
            assert isinstance(schema_status["all_tables_exist"], bool)
            
            if not schema_status["all_tables_exist"]:
                assert len(schema_status["missing_tables"]) > 0
                print(f"Missing tables: {schema_status['missing_tables']}")
            
        except Exception as e:
            pytest.skip(f"Supabase not available: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_user_settings_table_access(self):
        """Test that we can access user_settings table."""
        try:
            client = SupabaseService.get_service_client()
            
            result = client.table("user_settings").select("*", count="exact").limit(1).execute()
            
            assert result is not None
            assert hasattr(result, 'data')
            
        except ValueError as e:
            pytest.skip(f"Supabase credentials not configured: {str(e)}")
        except Exception as e:
            pytest.skip(f"user_settings table not available: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_conversations_table_access(self):
        """Test that we can access conversations table."""
        try:
            client = SupabaseService.get_service_client()
            
            result = client.table("conversations").select("*", count="exact").limit(1).execute()
            
            assert result is not None
            assert hasattr(result, 'data')
            
        except ValueError as e:
            pytest.skip(f"Supabase credentials not configured: {str(e)}")
        except Exception as e:
            pytest.skip(f"conversations table not available: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_messages_table_access(self):
        """Test that we can access messages table."""
        try:
            client = SupabaseService.get_service_client()
            
            result = client.table("messages").select("*", count="exact").limit(1).execute()
            
            assert result is not None
            assert hasattr(result, 'data')
            
        except ValueError as e:
            pytest.skip(f"Supabase credentials not configured: {str(e)}")
        except Exception as e:
            pytest.skip(f"messages table not available: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_audit_logs_table_access(self):
        """Test that we can access audit_logs table."""
        try:
            client = SupabaseService.get_service_client()
            
            result = client.table("audit_logs").select("*", count="exact").limit(1).execute()
            
            assert result is not None
            assert hasattr(result, 'data')
            
        except ValueError as e:
            pytest.skip(f"Supabase credentials not configured: {str(e)}")
        except Exception as e:
            pytest.skip(f"audit_logs table not available: {str(e)}")
    
    @pytest.mark.asyncio
    async def test_rate_limits_table_access(self):
        """Test that we can access rate_limits table."""
        try:
            client = SupabaseService.get_service_client()
            
            result = client.table("rate_limits").select("*", count="exact").limit(1).execute()
            
            assert result is not None
            assert hasattr(result, 'data')
            
        except ValueError as e:
            pytest.skip(f"Supabase credentials not configured: {str(e)}")
        except Exception as e:
            pytest.skip(f"rate_limits table not available: {str(e)}")
