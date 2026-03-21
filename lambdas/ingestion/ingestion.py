import json
import os
import time
import logging
import boto3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
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
    target = datetime.now(timezone.utc).date() - timedelta(days=1)
    while target.weekday() >= 5:  # Skip weekends
         target -= timedelta(days=1)
    return target.isoformat()

def handler(event, context):
        logger.info("Starting Ingestion")
        try:
            api_key = get_api_key()
            date_str = get_target_date()
            candidates = []

            #Secure headers
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

                        change = ((close_price - open_price) / open_price) * 100
                        candidates.append({
                            'ticker': ticker,
                            'change_percent': change,
                            'absolute_change': close_price - open_price,
                            'price': close_price,
                            'timestamp': datetime.now().isoformat()
                        })
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
                    'ticker': winner['ticker'],
                    'change_percent': Decimal(str(round(winner['change_percent']))),
                    'absolute_change': Decimal(str(round(winner['absolute_change']))),
                    'price': Decimal(str(winner['price']))
                }
            )
            logger.info(f"Inserted top mover: {winner['ticker']} with change {winner['change_percent']}%")
            return {"statusCode": 200, "body": f"Successfully ingested data for {date_str}"}
        except Exception as exc:
             logger.exception("Critical Ingestion Failure")
             return {"statusCode": 500, "body": str(exc)}