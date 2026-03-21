def handler(event, context):
    print("Received event: " + str(event))
    # Your ingestion logic here
    return {"statusCode": 200, "body": "Hello from the api lambda"}