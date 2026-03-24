import json
import os
import time
import boto3
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
import urllib3
from botocore.exceptions import ClientError

# Configuration
TABLE_NAME = 'TopMovers'  
SECRET_NAME = 'MassiveApiKey'
API_BASE_URL = 'https://api.massive.com'
WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA"]

# AWS clients
dynamodb = boto3.resource('dynamodb')
secrets_client = boto3.client('secretsmanager')
table = dynamodb.Table(TABLE_NAME)
http = urllib3.PoolManager()

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


def get_api_key():
    try:
        response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
        return response.get('SecretString')
    except ClientError as e:
        print(f"Error retrieving secret: {e}")
        raise


def get_trading_days(num_days=7):
    """Get the last N trading days (excluding weekends and holidays)"""
    eastern_now = datetime.now(timezone.utc).astimezone(ZoneInfo("America/New_York"))
    target = eastern_now.date()
    
    # If before market close (4 PM ET), start from previous day
    if eastern_now.hour < 16:
        target -= timedelta(days=1)
    
    trading_days = []
    
    while len(trading_days) < num_days:
        # Skip weekends and holidays
        while target.weekday() >= 5 or target.isoformat() in MARKET_HOLIDAYS:
            target -= timedelta(days=1)
        
        trading_days.append(target.isoformat())
        target -= timedelta(days=1)
    
    return trading_days


def check_date_exists(date_str):
    """Check if we already have data for this date"""
    try:
        response = table.scan(
            FilterExpression='#d = :date',
            ExpressionAttributeNames={'#d': 'date'},
            ExpressionAttributeValues={':date': date_str}
        )
        return len(response.get('Items', [])) > 0
    except Exception as e:
        print(f"Error checking if date exists: {e}")
        return False


def fetch_winner_for_date(api_key, date_str):
    """Fetch stock data for a specific date and determine the winner"""
    candidates = []
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json"
    }
    
    print(f"\nFetching data for {date_str}...")
    
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
                    'ticker': ticker,
                    'change_percent': change_percent,
                    'absolute_change': absolute_change,
                    'closing_price': close_price,
                })
                print(f"  {ticker}: {change_percent:+.2f}%")
            else:
                print(f"  {ticker}: Failed (status {response.status})")
            
            time.sleep(5)  # Rate limiting
            
        except Exception as e:
            print(f"  {ticker}: Error - {e}")
    
    if not candidates:
        print(f"  No data available for {date_str}")
        return None
    
    # Find the stock with the highest absolute percentage change
    winner = max(candidates, key=lambda x: abs(x['change_percent']))
    return winner


def store_winner(date_str, winner):
    """Store the winner in DynamoDB"""
    timestamp = datetime.now(timezone.utc).isoformat()
    
    item = {
        'timestamp': timestamp,
        'date': date_str,
        'ticker': winner['ticker'],
        'change_percent': Decimal(str(winner['change_percent'])),
        'closing_price': Decimal(str(winner['closing_price'])),
    }
    
    try:
        table.put_item(Item=item)
        print(f"  ✓ Stored winner: {winner['ticker']} ({winner['change_percent']:+.2f}%)")
        return True
    except Exception as e:
        print(f"  ✗ Error storing data: {e}")
        return False


def main():
    print("=== Stock Watchlist 7-Day Backfill ===\n")
    
    try:
        api_key = get_api_key()
        trading_days = get_trading_days(7)
        
        print(f"Target trading days: {trading_days}\n")
        
        processed = 0
        skipped = 0
        failed = 0
        
        for date_str in trading_days:
            # Check if date already exists
            if check_date_exists(date_str):
                print(f"\n{date_str}: Already exists, skipping")
                skipped += 1
                continue
            
            # Fetch and store winner
            winner = fetch_winner_for_date(api_key, date_str)
            if winner:
                if store_winner(date_str, winner):
                    processed += 1
                else:
                    failed += 1
            else:
                failed += 1
            
            #add delay between days to avoid hitting API rate limits
            if date_str != trading_days[-1]:
                print("  Waiting 5 seconds before next day...")
                time.sleep(5.0)  
        
        print("\n" + "="*50)
        print(f"Backfill complete!")
        print(f"  Processed: {processed}")
        print(f"  Skipped: {skipped}")
        print(f"  Failed: {failed}")
        print("="*50)
        
    except Exception as e:
        print(f"\nCritical error: {e}")
        raise


if __name__ == "__main__":
    main()