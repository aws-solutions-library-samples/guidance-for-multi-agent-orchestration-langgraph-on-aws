"""Setup script for the multi-agent customer support system."""

from setuptools import setup, find_packages

setup(
    name="multi-agent-customer-support",
    version="1.0.0",
    description="Distributed multi-agent customer support system",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "fastapi>=0.104.1",
        "uvicorn[standard]>=0.24.0",
        "langchain-aws>=0.2.27",
        "boto3>=1.34.0",
        "httpx>=0.25.2",
        "pydantic>=2.5.0",
        "pydantic-settings>=2.1.0",
        "python-dotenv>=1.0.0",
        "langgraph>=0.5.1",
        "psycopg2-binary>=2.9.9",
        "asyncpg>=0.29.0",
        "sqlalchemy>=2.0.23",
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
    ],
)