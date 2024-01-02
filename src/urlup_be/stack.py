import pulumi
import pulumi_aws as aws


def stack():
    # Create an IAM role that the Lambda function can assume
    lambda_role = aws.iam.Role(
        "lambdaRole",
        assume_role_policy="""{
            "Version": "2012-10-17",
            "Statement": [{
                "Action": "sts:AssumeRole",
                "Effect": "Allow",
                "Principal": {
                    "Service": "lambda.amazonaws.com"
                }
            }]
        }""",
    )

    # Attach the AWSLambdaBasicExecutionRole policy to the role created
    aws.iam.RolePolicyAttachment(
        "lambdaRoleAttach",
        role=lambda_role.name,
        policy_arn=(
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
        ),
    )

    # Create the Lambda function
    shorten_lambda = aws.lambda_.Function(
        "shortenLambda",
        role=lambda_role.arn,
        handler="index.handler",
        runtime="python3.8",
        code=pulumi.asset.AssetArchive(
            {".": pulumi.asset.FileArchive("./lambdas/shorten.py")}
        ),
    )

    # Create the Lambda function
    redir_lambda = aws.lambda_.Function(
        "redirectLambda",
        role=lambda_role.arn,
        handler="index.handler",
        runtime="python3.8",
        code=pulumi.asset.AssetArchive(
            {".": pulumi.asset.FileArchive("./lambdas/redirect.py")}
        ),
    )

    # Create an API Gateway to trigger the Lambda functions
    api_gateway = aws.apigatewayv2.Api("apiGateway", protocol_type="HTTP")

    # Create a route for the first Lambda function
    aws.apigatewayv2.Route(
        "shortenRoute",
        api_id=api_gateway.id,
        route_key="POST /shorten",
        target=shorten_lambda.invoke_arn,
    )

    # Create a route for the second Lambda function
    aws.apigatewayv2.Route(
        "redirectRoute",
        api_id=api_gateway.id,
        route_key="POST /redirect",
        target=redir_lambda.invoke_arn,
    )

    # Lambda permission to allow invocation from API Gateway
    aws.lambda_.Permission(
        "apiGatewayShortenPermission",
        action="lambda:InvokeFunction",
        function=shorten_lambda.name,
        principal="apigateway.amazonaws.com",
        source_arn=pulumi.Output.concat(api_gateway.execution_arn, "/*/*"),
    )

    aws.lambda_.Permission(
        "apiGatewayRedirectPermission",
        action="lambda:InvokeFunction",
        function=redir_lambda.name,
        principal="apigateway.amazonaws.com",
        source_arn=pulumi.Output.concat(api_gateway.execution_arn, "/*/*"),
    )

    # Export the URL of the API Gateway
    # to be used to trigger the Lambda function
    pulumi.export("api_gateway_url", api_gateway.api_endpoint)
