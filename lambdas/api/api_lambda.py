import json
import os
import boto3
from decimal import Decimal


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return super(DecimalEncoder, self).default(obj)


dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['TABLE_NAME'])
allowed_origins = {
    origin.strip()
    for origin in os.environ.get(
        'ALLOWED_ORIGINS',
        'http://localhost:3000,https://main.d2o5xbreubwc5h.amplifyapp.com',
    ).split(',')
    if origin.strip()
}


def get_allowed_origin(event):
    headers = event.get('headers') or {}
    origin = headers.get('origin') or headers.get('Origin')
    if origin and origin in allowed_origins:
        return origin
    return next(iter(allowed_origins), '*')


def build_response(status_code, body, origin):
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Methods': 'GET, OPTIONS',
        },
        'body': json.dumps(body, cls=DecimalEncoder),
    }


def get_scan_items():
    items = []
    response = table.scan()
    items.extend(response.get('Items', []))

    while 'LastEvaluatedKey' in response:
        response = table.scan(ExclusiveStartKey=response['LastEvaluatedKey'])
        items.extend(response.get('Items', []))

    return items


def get_limit(event):
    params = event.get('queryStringParameters') or {}
    raw_days = params.get('days')

    if not raw_days:
        return 7

    try:
        days = int(raw_days)
    except (TypeError, ValueError):
        return 7

    return max(1, min(days, 365))


def normalize_item(item):
    timestamp = item.get('timestamp', '')
    date = item.get('date') or timestamp.split('T')[0]

    return {
        'date': date,
        'ticker': item.get('ticker'),
        'change_percent': item.get('change_percent'),
        'closing_price': item.get('closing_price', item.get('price')),
    }


def handler(event, context):
    origin = get_allowed_origin(event)

    try:
        items = get_scan_items()
        limit = get_limit(event)
        # Deduplicate by date - keep the most recent entry for each date
        date_map = {}
        for item in items:
            date = item.get('date', '')
            timestamp = item.get('timestamp', '')
            
            # If this date doesn't exist yet, or this entry is newer, use it
            if date not in date_map or timestamp > date_map[date].get('timestamp', ''):
                date_map[date] = item
        
        # Convert back to list and sort
        unique_items = list(date_map.values())
        sorted_items = sorted(unique_items, key=lambda x: x.get('date', ''), reverse=True)[:limit]
        movers = [normalize_item(item) for item in sorted_items]
        return build_response(200, {'movers': movers}, origin)
    except Exception as e:
        print(f"Error fetching data: {e}")
        return build_response(500, {'error': 'Failed to fetch data'}, origin)
