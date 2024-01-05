import json
import pulumi
import pulumi_aws as aws
from functools import partial

from .config import Config


def stack(conf: Config):
    # Define the DynamoDB table
    dynamo_table = aws.dynamodb.Table(
        conf.table_name,
        attributes=[
            aws.dynamodb.TableAttributeArgs(
                name="short",
                type="S",
            ),
        ],
        hash_key="short",
        billing_mode="PAY_PER_REQUEST",
    )

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

    policy_document = dynamo_table.arn.apply(
        lambda arn: json.dumps(
            {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": [
                            "dynamodb:GetItem",
                            "dynamodb:Scan",
                            "dynamodb:Query",
                            "dynamodb:PutItem",
                            "dynamodb:UpdateItem",
                        ],
                        "Resource": arn,
                    }
                ],
            }
        )
    )

    dynamo_policy = aws.iam.Policy(
        "dynamoTablePolicy",
        policy=policy_document,
    )

    # Attach the policy to the role.
    aws.iam.RolePolicyAttachment(
        "dynamoRoleAttachment", role=lambda_role.name, policy_arn=dynamo_policy.arn
    )

    lambdas_dir = "./src/urlup_be/lambdas"

    # Attach the AWSLambdaBasicExecutionRole policy to the role created
    aws.iam.RolePolicyAttachment(
        "lambdaRoleAttach",
        role=lambda_role.name,
        policy_arn="arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    )

    shorten_dependencies_layer = aws.lambda_.LayerVersion(
        "shortenDependenciesLayer",
        layer_name="shorten-dependencies",
        code=pulumi.asset.AssetArchive(
            {".": pulumi.FileAsset(f"{lambdas_dir}/shorten/dependencies_layer.zip")}
        ),
        compatible_runtimes=["python3.11"],
    )

    # Create the Lambda function
    shorten_lambda = aws.lambda_.Function(
        "shrtLda",
        role=lambda_role.arn,
        handler="index.handler",
        runtime="python3.11",
        layers=[shorten_dependencies_layer.arn],
        code=pulumi.asset.AssetArchive(
            {".": pulumi.asset.FileArchive(f"{lambdas_dir}/shorten")}
        ),
    )

    # Create the Lambda function
    redir_lambda = aws.lambda_.Function(
        "redirLda",
        role=lambda_role.arn,
        handler="index.handler",
        runtime="python3.11",
        # layers=[redir_dependencies_layer.arn],
        code=pulumi.asset.AssetArchive(
            {".": pulumi.asset.FileArchive(f"{lambdas_dir}/redirect")}
        ),
    )

    zone = aws.route53.get_zone(name=conf.zone_domain)

    # Create an API Gateway to trigger the Lambda functions
    api_gateway = aws.apigatewayv2.Api("apiGateway", protocol_type="HTTP")
    certificate = aws.acm.Certificate.get(
        "shortCert", id=conf.cert_arn, arn=conf.cert_arn
    )

    api_mapping = aws.apigatewayv2.ApiMapping(
        "apiMapping",
        api_id=api_gateway.id,
        domain_name=conf.gateway_domain,
        stage="$default",
    )

    # Setup the custom domain name for API Gateway
    domain_name_config = aws.apigateway.DomainName(
        "apiDomainName",
        domain_name=conf.gateway_domain,
        certificate_arn=certificate.arn,
        endpoint_configuration={"types": "REGIONAL"},
    )

    # Create a DNS record to point the custom domain to the API Gateway
    dns_record = aws.route53.Record(
        "apiDnsRecord",
        name=conf.gateway_domain,
        type="A",
        zone_id=zone.id,  # Your Route 53 Hosted Zone ID
        aliases=[
            aws.route53.RecordAliasArgs(
                name=domain_name_config.cloudfront_domain_name,
                zone_id=domain_name_config.cloudfront_zone_id,
                evaluate_target_health=True,
            )
        ],
    )

    redir_integration = aws.apigatewayv2.Integration(
        "apiGatewayRedirIntegration",
        api_id=api_gateway.id,
        integration_type="AWS_PROXY",
        integration_uri=redir_lambda.invoke_arn,
        payload_format_version="2.0",
        timeout_milliseconds=30000,
    )

    shorten_integration = aws.apigatewayv2.Integration(
        "apiGatewayShortenIntegration",
        api_id=api_gateway.id,
        integration_type="AWS_PROXY",
        integration_uri=shorten_lambda.invoke_arn,
        payload_format_version="2.0",
        timeout_milliseconds=30000,
    )

    # Create a route for the first Lambda function
    aws.apigatewayv2.Route(
        "shortRoute",
        api_id=api_gateway.id,
        route_key="POST /shorten",
        target=shorten_integration.id.apply(lambda id: f"integrations/{id}"),
    )

    # Create a route for the second Lambda function
    aws.apigatewayv2.Route(
        "redirectRoute",
        api_id=api_gateway.id,
        route_key="POST /redirect",
        target=redir_integration.id.apply(lambda id: f"integrations/{id}"),
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
