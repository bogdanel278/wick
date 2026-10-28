import os

os.environ["WICK_ENV"] = "dev"
os.environ.pop("ANTHROPIC_API_KEY", None)
