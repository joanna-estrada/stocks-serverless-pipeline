from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_dynamodb as dynamodb,
    aws_apigateway as apigw,
    aws_events as events,
    aws_events_targets as targets,
    aws_iam as iam,
    RemovalPolicy,
    Duration,
)

from constructs import Construct

class BackendStack(Stack):
    def __init__(self,scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB table
        table = dynamodb.Table(
            self, "TopMoversTable",
            table_name="TopMovers",
            partition_key=dynamodb.Attribute(
                name="timestamp", 
                type=dynamodb.AttributeType.STRING
            ),
            removal_policy=RemovalPolicy.DESTROY,
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
        )

        # Create Lambda function
        ingestion_lambda = _lambda.Function(
            self,"IngestionLambda",
            function_name="IngestionLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="ingestion.handler",
            code=_lambda.Code.from_asset("../lambdas/ingestion"),
            timeout=Duration.seconds(30),
            environment={
                "TABLE_NAME": table.table_name,
                "SECRET_NAME": "MassiveApiKey",
                "API_BASE_URL": "https://api.massiveapi.com/",
            },
        )

        # Grant Lambda function permissions to read/write to the DynamoDB table
        table.grant_read_write_data(ingestion_lambda)

        #Grant Lambda function access to Secrets Manager
        ingestion_lambda.add_to_role_policy(
            iam.PolicyStatement(
                actions=["secretsmanager:GetSecretValue"],
                resources=["*"],
            )
        )

        #EventBridge rule to trigger Lambda function every hour
        rule = events.Rule(
            self, "IngestionRule",
            rule_name="IngestionRule",
            schedule=events.Schedule.cron(
                minute="0",
                hour="22",
                month="*",
                week_day="MON-FRI",
                year="*",
            )
        )
        rule.add_target(targets.LambdaFunction(ingestion_lambda))

        # API Lambda
        api_lambda = _lambda.Function(
            self,"ApiLambda",
            function_name="stock-api",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="api_lambda.handler",
            code=_lambda.Code.from_asset("../lambdas/api"),
            timeout=Duration.seconds(10),
            environment={
                "TABLE_NAME": table.table_name,
            },
        )
        # Grant API Lambda permissions to read from the DynamoDB table
        table.grant_read_data(api_lambda)


        # Create API Gateway REST API
        api = apigw.RestApi(
            self, "StockDataApi",
            rest_api_name="Stock Data Service",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS, #TODO: change later to AWS Amplify domain
                allow_methods=["GET", "POST", "OPTIONS"],
            )
        )

        movers = api.root.add_resource("top-movers")
        movers.add_method(
            "GET",
            apigw.LambdaIntegration(api_lambda),
        )