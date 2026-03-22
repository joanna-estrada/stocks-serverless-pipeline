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

def handler(event, context):
    try:
        response = table.scan()
        items = response.get('Items', [])
        #Sort, 7 days history
        sorted_items = sorted(items, key=lambda x: x['timestamp'], reverse=True)[:7]
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': 'https://main.d2o5xbreubwc5h.amplifyapp.com/',
                'Access-Control-Allow-Methods': 'GET, OPTIONS'
            },
            'body': json.dumps(sorted_items, cls=DecimalEncoder)
        }
    except Exception as e:
        print(f"Error fetching data: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Failed to fetch data'})
        }
    
