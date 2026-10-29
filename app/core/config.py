"""Shared project settings. The API key comes from .env only."""
import os

from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

load_dotenv(os.path.join(BASE_DIR, ".env"))

MODEL_API_KEY = os.environ.get("MODEL_API_KEY", "")
CHAT_URL = "https://api.meta.ai/v1/chat/completions"
IMAGE_URL = "https://api.meta.ai/v1/images/generations"
SPARK_MODEL = "muse-spark-1.3"
IMAGE_MODEL = "muse-image-1.0"

SPECS_PATH = os.path.join(BASE_DIR, "data", "fabric_specs.json")
CATALOG_DIR = os.path.join(BASE_DIR, "data", "catalog")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
REPORT_PATH = os.path.join(BASE_DIR, "data", "verify_report.json")


def runtime_logs_dir():
    """Volume-backed dir for logs written while serving.

    UPLOAD_DIR is the Modal Volume mount in production, so anything
    here survives redeploys; locally it is the gitignored uploads/.
    """
    path = os.path.join(UPLOAD_DIR, "logs")
    os.makedirs(path, exist_ok=True)
    return path


def require_api_key():
    if not MODEL_API_KEY:
        raise RuntimeError("MODEL_API_KEY is not set in .env")
    return MODEL_API_KEY
