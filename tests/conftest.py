"""
Pytest configuration and fixtures for Orzion Chat tests
"""
import pytest
import asyncio
from typing import AsyncGenerator
from httpx import AsyncClient
from starlette.testclient import TestClient
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_client():
    """Test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Async test client for FastAPI app."""
    from httpx import ASGITransport
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def mock_user():
    """Mock user data for testing."""
    return {
        "id": 1,
        "email": "test@example.com",
        "full_name": "Test User",
        "is_active": True
    }


@pytest.fixture
def mock_token():
    """Mock JWT token for testing."""
    return "mock_jwt_token_12345"


@pytest.fixture
def sample_chat_message():
    """Sample chat message for testing."""
    return {
        "prompt": "Hello, how are you?",
        "model": "Orzion Pro",
        "enable_search": False,
        "history": [],
        "conversation_id": None
    }


@pytest.fixture
def sample_conversation():
    """Sample conversation data."""
    return {
        "id": 1,
        "user_id": 1,
        "title": "Test Conversation",
        "model": "Orzion Pro",
        "is_archived": False
    }


@pytest.fixture
def mock_supabase_client():
    """Mock Supabase client for testing."""
    class MockSupabaseClient:
        def table(self, table_name):
            return self
        
        def select(self, *args, **kwargs):
            return self
        
        def limit(self, n):
            return self
        
        def execute(self):
            class MockResult:
                data = []
                count = 0
            return MockResult()
    
    return MockSupabaseClient()


@pytest.fixture
def sample_pdf_code():
    """Sample PDF generation code for testing."""
    return """
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

c = canvas.Canvas(output_file, pagesize=letter)
c.drawString(100, 750, "Test PDF Document")
c.save()
"""


@pytest.fixture
def sample_zip_code():
    """Sample ZIP generation code for testing."""
    return """
import zipfile

with zipfile.ZipFile(output_file, 'w') as zipf:
    zipf.writestr('test.txt', 'Test content')
"""


@pytest.fixture
def malicious_code_samples():
    """Collection of malicious code samples for security testing."""
    return {
        "os_system": "import os; os.system('ls')",
        "subprocess": "import subprocess; subprocess.run(['ls'])",
        "eval": "eval('print(1)')",
        "exec": "exec('import os')",
        "file_write": "open('/tmp/test.txt', 'w').write('test')",
        "unauthorized_import": "import requests; requests.get('http://evil.com')"
    }
