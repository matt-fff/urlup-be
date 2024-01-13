import json

import pulumi
import pulumi_aws as aws
import pulumi_aws_apigateway as apigateway

from urlup_be.stacks.aws.config import Config


def api_usage_plan(
    conf: Config,
    api_gateway: apigateway.RestAPI,
) -> aws.apigateway.UsagePlanKey:
    key = aws.apigateway.ApiKey("defaultKey")

    plan = aws.apigateway.UsagePlan(
        "defaultPlan",
        aws.apigateway.UsagePlanArgs(
            api_stages=[
                aws.apigateway.UsagePlanApiStageArgs(
                    api_id=api_gateway.api.id,
                    stage=api_gateway.stage.stage_name,
                ),
            ],
            quota_settings=aws.apigateway.UsagePlanQuotaSettingsArgs(
                limit=conf.usage.period_limit,
                period=conf.usage.period_type,
            ),
            throttle_settings=aws.apigateway.UsagePlanThrottleSettingsArgs(
                burst_limit=conf.usage.burst_limit,
                rate_limit=conf.usage.rate_limit,
            ),
        ),
    )

    plan_key = aws.apigateway.UsagePlanKey(
        "defaultPlanKey",
        aws.apigateway.UsagePlanKeyArgs(
            key_id=key.id,
            key_type="API_KEY",
            usage_plan_id=plan.id,
        ),
    )

    return plan_key


def lambdas(conf: Config, dynamo_table) -> tuple:
    lambdas_dir = "../../lambdas"

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
        tags=conf.tags,
        managed_policy_arns=[
            aws.iam.ManagedPolicy.AWS_LAMBDA_BASIC_EXECUTION_ROLE
        ],
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
        tags=conf.tags,
    )

    # Attach the policy to the role.
    aws.iam.RolePolicyAttachment(
        "dynamoRoleAttachment",
        role=lambda_role.name,
        policy_arn=dynamo_policy.arn,
    )

    dependencies_layer = aws.lambda_.LayerVersion(
        "lambdaDependenciesLayer",
        layer_name="lambda-dependencies",
        code=pulumi.asset.AssetArchive(
            {".": pulumi.FileArchive(f"{lambdas_dir}/.venv")}
        ),
        compatible_runtimes=["python3.11"],
    )

    lambda_kwargs = dict(
        role=lambda_role.arn,
        runtime="python3.11",
        layers=[dependencies_layer.arn],
        code=pulumi.asset.AssetArchive(
            {".": pulumi.asset.FileArchive(f"{lambdas_dir}/handlers")}
        ),
        tags=conf.tags,
        environment={"variables": {"DDB_TABLE": dynamo_table.name}},
    )

    # Create the Lambda functions
    create_lambda = aws.lambda_.Function(
        "shortenLambda", handler="package.shorten.handler", **lambda_kwargs
    )
    redir_lambda = aws.lambda_.Function(
        "redirectLambda", handler="package.redirect.handler", **lambda_kwargs
    )
    get_lambda = aws.lambda_.Function(
        "getLambda", handler="package.get.handler", **lambda_kwargs
    )

    return create_lambda, redir_lambda, get_lambda


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
        tags=conf.tags,
    )

    domain_stack = pulumi.StackReference(conf.domain_stack_name)
    domain_name = domain_stack.get_output("domain")
    zone_id = domain_stack.get_output("zone_id")
    zone = aws.route53.get_zone(zone_id=zone_id)  # pyright: ignore

    create_lambda, redir_lambda, get_lambda = lambdas(conf, dynamo_table)

    # Create an API Gateway to trigger the Lambda functions
    api_gateway = apigateway.RestAPI(
        "api",
        stage_name=conf.env,
        request_validator=apigateway.RequestValidator.ALL,
        routes=[
            apigateway.RouteArgs(
                path="/create",
                method=apigateway.Method.POST,
                event_handler=create_lambda,
                api_key_required=True,
            ),
            apigateway.RouteArgs(
                path="/redirect",
                method=apigateway.Method.POST,
                event_handler=redir_lambda,
                api_key_required=True,
            ),
            apigateway.RouteArgs(
                path="/get",
                method=apigateway.Method.POST,
                event_handler=get_lambda,
                api_key_required=True,
            ),
        ],
    )

    certificate = aws.acm.Certificate.get(
        "shortCert", id=domain_stack.get_output("certificate_arn")
    )

    # Setup the custom domain name for API Gateway
    gateway_domain_name = aws.apigateway.DomainName(
        "apiDomainName",
        domain_name=domain_name,
        certificate_arn=certificate.arn,
        tags=conf.tags,
    )

    # Create a DNS record to point the custom domain to the API Gateway
    aws.route53.Record(
        "apiDnsRecord",
        name=domain_name,
        type="A",
        zone_id=zone.id,
        aliases=[
            aws.route53.RecordAliasArgs(
                name=gateway_domain_name.cloudfront_domain_name,
                zone_id=gateway_domain_name.cloudfront_zone_id,
                evaluate_target_health=True,
            )
        ],
    )

    base_path_mapping = aws.apigateway.BasePathMapping(
        "apiPathMapping",
        aws.apigateway.BasePathMappingArgs(
            rest_api=api_gateway.api,
            domain_name=gateway_domain_name.domain_name,
            stage_name=api_gateway.stage.stage_name,
        ),
    )

    plan_key = api_usage_plan(conf, api_gateway)

    # Export the URL of the API Gateway
    # to be used to trigger the Lambda function
    pulumi.export(
        "url", pulumi.Output.concat("https://", base_path_mapping.domain_name)
    )
    pulumi.export("api_key", plan_key.value)


config = Config()
stack(config)
