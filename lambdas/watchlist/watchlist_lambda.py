import json
import logging
import os

import boto3
import urllib3
from botocore.exceptions import ClientError
from datetime import datetime, timedelta, timezone

TRACKED_COMPANIES = {
    "AAPL": "Apple Inc.",
    "MSFT": "Microsoft Corp.",
    "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.",
    "TSLA": "Tesla Inc.",
    "NVDA": "NVIDIA Corporation",
}

# Add known 2026 market holidays
MARKET_HOLIDAYS = {
    "2026-01-01",  # New Year's Day
    "2026-01-19",  # MLK Day
    "2026-02-16",  # Presidents Day
    "2026-04-03",  # Good Friday 
    "2026-05-25",  # Memorial Day
    "2026-06-19",  # Juneteenth
    "2026-07-03",  # Independence Day (observed)
    "2026-09-07",  # Labor Day
    "2026-11-26",  # Thanksgiving
    "2026-12-25",  # Christmas
}

logger = logging.getLogger()
logger.setLevel(logging.INFO)

http = urllib3.PoolManager()
secrets_client = boto3.client('secretsmanager')

SECRET_NAME = os.environ.get('SECRET_NAME', 'MassiveApiKey')
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.massive.com')
WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"]
ALLOWED_ORIGINS = {
    origin.strip()
    for origin in os.environ.get(
        'ALLOWED_ORIGINS',
        'http://localhost:3000,https://main.d2o5xbreubwc5h.amplifyapp.com',
    ).split(',')
    if origin.strip()
}


def get_api_key():
    try:
        response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
        return response.get('SecretString')
    except ClientError as exc:
        logger.exception("Error retrieving secret: %s", exc)
        raise


def get_allowed_origin(event):
    headers = event.get('headers') or {}
    origin = headers.get('origin') or headers.get('Origin')
    if origin and origin in ALLOWED_ORIGINS:
        return origin
    return next(iter(ALLOWED_ORIGINS), '*')


def build_response(status_code, body, origin):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
        },
        'body': json.dumps(body),
    }


def request_json(path, api_key):
    separator = "&" if "?" in path else "?"
    url = f"{API_BASE_URL}{path}{separator}apiKey={api_key}"
    response = http.request(
        'GET',
        url,
        headers={
            "Accept": "application/json",
        },
        timeout=10.0,
    )

    if response.status != 200:
        body = response.data.decode('utf-8', errors = "ignore")
        raise RuntimeError(f"Massive API request failed for {path} with status {response.status}: {body}") 

    return json.loads(response.data.decode('utf-8'))


def first_numeric(*values):
    for value in values:
        if value is None:
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None

def get_previous_close_date():
    target_date = datetime.now(timezone.utc).date() - timedelta(days=1)

    while target_date.weekday() >= 5 or target_date.isoformat() in MARKET_HOLIDAYS:
        target_date -= timedelta(days=1)

    return target_date.isoformat()

def get_daily_open_close(ticker, date_str, api_key):
    try:
        payload = request_json(f"/v1/open-close/{ticker}/{date_str}?adjusted=true", api_key)
        return payload
    except Exception as exc:
        logger.error("Failed to fetch open/close data for %s on %s: %s", ticker, date_str, exc)
        return {}

def build_watchlist_rows(api_key):
    date_str = get_previous_close_date()
    logger.info("Fetching previous close data for date: %s", date_str)
    rows = []

    for ticker in WATCHLIST:
        data = get_daily_open_close(ticker, date_str, api_key)

        open_price = first_numeric(data.get('open'))
        close_price = first_numeric(data.get('close'))

        change = None
        change_percent = None
        if open_price and close_price and open_price != 0:
            change = round(close_price - open_price, 2)
            change_percent = round((change / open_price) * 100, 2)

        rows.append({
            'ticker': ticker,
            'company': TRACKED_COMPANIES.get(ticker, ticker),
            'price': round(close_price, 2) if close_price is not None else None,
            'change': change,
            'change_percent': change_percent,
            'volume': first_numeric(data.get('volume')),
            'date': date_str,   
        })
    return rows


def handler(event, context):
    origin = get_allowed_origin(event)

    try:
        api_key = get_api_key()
        watchlist = build_watchlist_rows(api_key)
        return build_response(200, {'watchlist': watchlist}, origin)
    except Exception as exc:
        logger.exception("Failed to load watchlist data: %s", exc)
        return build_response(500, {'error': 'Failed to fetch watchlist data'}, origin)
