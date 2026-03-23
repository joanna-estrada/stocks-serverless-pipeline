import json
import os
import time
import logging
import boto3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
import urllib3
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)
http = urllib3.PoolManager()

# AWS resources
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')

#CDK environment variables
TABLE_NAME = os.environ['TABLE_NAME']
SECRET_NAME = os.environ.get('SECRET_NAME', 'MassiveApiKey')
API_BASE_URL = os.environ.get('API_BASE_URL', 'https://api.massive.com')
WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"]

table = dynamodb.Table(TABLE_NAME)

def get_api_key():
    try:
        response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
        return response.get('SecretString')
    except ClientError as e:
        logger.exception("Error retrieving secret: %s", e)
        raise


def get_target_date():
    MARKET_HOLIDAYS = {
    "2026-01-01",
    "2026-01-19",
    "2026-02-16",
    "2026-04-03",  
    "2026-05-25",
    "2026-06-19",
    "2026-07-03",
    "2026-09-07",
    "2026-11-26",
    "2026-12-25",
    }
    
    eastern_now = datetime.now(timezone.utc).astimezone(
        ZoneInfo("America/New_York")
    )

    target = eastern_now.date()

    if eastern_now.hour < 16:
        target -= timedelta(days=1)

    while target.weekday() >= 5 or target.isoformat() in MARKET_HOLIDAYS:
        target -= timedelta(days=1)

    return target.isoformat()

def handler(event, context):
    logger.info("Starting Ingestion")
    try:
        api_key = get_api_key()
        date_str = get_target_date()
        candidates = []

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }

        for ticker in WATCHLIST:
            url = f"{API_BASE_URL}/v1/open-close/{ticker}/{date_str}?adjusted=true"
            try:
                response = http.request('GET', url, headers=headers, timeout=10.0)

                if response.status == 200:
                    data = json.loads(response.data.decode('utf-8'))
                    open_price = float(data['open'])
                    close_price = float(data['close'])
                    absolute_change = close_price - open_price
                    change_percent = (absolute_change / open_price) * 100

                    candidates.append({
                        'date': date_str,
                        'ticker': ticker,
                        'change_percent': change_percent,
                        'absolute_change': absolute_change,
                        'closing_price': close_price,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                    time.sleep(2.5)  # Rate limiting
                else:
                    logger.warning(f"Failed to fetch data for {ticker} on {date_str}: {response.status}")
                
            except Exception as e:
                logger.error(f"Error fetching data for {ticker} on {date_str}: {e}")

        if not candidates:
            return {"statusCode": 200, "body": "No data available for the target date."}

        winner = max(candidates, key=lambda x: abs(x['change_percent']))
        table.put_item(
            Item={
                'timestamp': winner['timestamp'],
                'date': winner['date'],
                'ticker': winner['ticker'],
                'change_percent': Decimal(str(winner['change_percent'])),
                'closing_price': Decimal(str(winner['closing_price'])),
            }
        )
        logger.info(f"Inserted top mover: {winner['ticker']} with change {winner['change_percent']}%")
        return {"statusCode": 200, "body": f"Successfully ingested data for {date_str}"}
    except Exception as exc:
        logger.exception("Critical Ingestion Failure")
        return {"statusCode": 500, "body": str(exc)}
