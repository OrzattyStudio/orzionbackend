
"""
AWS Lambda Handler for Orzion Chat Backend
Adapts FastAPI application to AWS Lambda using Mangum
"""

from mangum import Mangum
from app import app

# Create Lambda handler
handler = Mangum(app, lifespan="off")
