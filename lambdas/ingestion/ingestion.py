def handler(event, context):
    print("Received event: " + str(event))
    # Ingestion logic here
    return {"statusCode": 200, "body": "Hello from the ingestion lambda"}