import json

import pulumi
import pulumi_aws as aws
import pulumi_aws_apigateway as apigateway
from config import Config


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


def lambdas(conf: Config, dynamo_table) -> dict[str, aws.lambda_.Function]:
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
        environment={
            "variables": {
                "DDB_TABLE": dynamo_table.name,
                "FRONTEND_URL": conf.frontend_url,
            }
        },
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
    options_lambda = aws.lambda_.Function(
        "optionsLambda", handler="package.options.handler", **lambda_kwargs
    )

    return {
        "create": create_lambda,
        "redirect": redir_lambda,
        "get": get_lambda,
        "options": options_lambda,
    }


def configure_gateway(
    domain_stack: pulumi.StackReference,
    prefix: str,
    gateway: apigateway.RestAPI,
):
    domain_name = domain_stack.get_output(f"{prefix}_domain")
    zone_id = domain_stack.get_output(f"{prefix}_zone_id")
    zone = aws.route53.get_zone(zone_id=zone_id)  # pyright: ignore

    certificate = aws.acm.Certificate.get(
        f"{prefix}Cert", id=domain_stack.get_output(f"{prefix}_cert_arn")
    )

    # Setup the custom domain name for API Gateway
    gateway_domain_name = aws.apigateway.DomainName(
        f"{prefix}DomainName",
        domain_name=domain_name,
        certificate_arn=certificate.arn,
    )

    # Create a DNS record to point the custom domain to the API Gateway
    aws.route53.Record(
        f"{prefix}DnsRecord",
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
        f"{prefix}PathMapping",
        aws.apigateway.BasePathMappingArgs(
            rest_api=gateway.api,
            domain_name=gateway_domain_name.domain_name,
            stage_name=gateway.stage.stage_name,
        ),
    )

    # Export the URL of the API Gateway
    # to be used to trigger the Lambda function
    pulumi.export(
        f"{prefix}_url",
        pulumi.Output.concat("https://", base_path_mapping.domain_name),
    )


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

    handlers = lambdas(conf, dynamo_table)

    # Create an API Gateway to trigger the Lambda functions
    api_gateway = apigateway.RestAPI(
        "api",
        stage_name=conf.env,
        request_validator=apigateway.RequestValidator.ALL,
        routes=[
            apigateway.RouteArgs(
                path="/create",
                method=apigateway.Method.POST,
                event_handler=handlers["create"],
                api_key_required=True,
            ),
            apigateway.RouteArgs(
                path="/get",
                method=apigateway.Method.POST,
                event_handler=handlers["get"],
                api_key_required=True,
            ),
            apigateway.RouteArgs(
                path="/create",
                method=apigateway.Method.OPTIONS,
                event_handler=handlers["options"],
                api_key_required=False,
            ),
            apigateway.RouteArgs(
                path="/get",
                method=apigateway.Method.OPTIONS,
                event_handler=handlers["options"],
                api_key_required=False,
            ),
        ],
    )
    plan_key = api_usage_plan(conf, api_gateway)
    pulumi.export("api_key", plan_key.value)

    redirect_gateway = apigateway.RestAPI(
        "redirect",
        stage_name=conf.env,
        request_validator=apigateway.RequestValidator.ALL,
        routes=[
            apigateway.RouteArgs(
                path="/{shortcode}",
                method=apigateway.Method.GET,
                event_handler=handlers["redirect"],
                api_key_required=False,
            ),
        ],
    )

    domain_stack = pulumi.StackReference(conf.domain_stack_name)
    configure_gateway(domain_stack, "api", api_gateway)
    configure_gateway(domain_stack, "redirect", redirect_gateway)


config = Config()
stack(config)
