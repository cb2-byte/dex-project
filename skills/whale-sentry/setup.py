from setuptools import setup, find_packages

setup(
    name="whale-sentry",
    version="1.0.0",
    description="On-chain whale monitoring and alerting system using free APIs",
    author="penny",
    packages=find_packages(where="."),
    package_dir={"": "."},
    install_requires=[
        "aiohttp>=3.9.0",
        "python-dotenv>=1.0.0",
        "python-telegram-bot>=20.0",
        "asyncio-throttle>=1.0.0",
        "pydantic>=2.0.0",
        "pydantic-settings>=2.0.0",
    ],
    python_requires=">=3.10",
)
