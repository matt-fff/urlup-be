import pulumi
import pulumi_aws as aws


def stack(conf: pulumi.Config):
    # We explicitly use us-east-1 for the cert,
    # since it's required for EDGE endpoints
    us_east_1 = aws.Provider(
        "us-east-1",
        aws.ProviderArgs(
            region="us-east-1",
        ),
    )
    tags = conf.require_object("tags")

    for prefix, domain_conf in (
        ("api", conf.require_object("api_domain")),
        ("redirect", conf.require_object("redirect_domain")),
        ("fe-prod", conf.require_object("frontend_prod_domain")),
        ("fe-staging", conf.require_object("frontend_staging_domain")),
    ):
        zone = aws.route53.get_zone(name=domain_conf["zone_domain"])
        cert = aws.acm.Certificate(
            f"{prefix}Cert",
            domain_name=domain_conf["cert_domain"],
            validation_method="DNS",
            tags=tags,
            opts=pulumi.ResourceOptions(provider=us_east_1),
        )
        validation_option = cert.domain_validation_options[0]

        # Set up the DNS records for validation
        validation_record = aws.route53.Record(
            f"{prefix}CertValidationRecord",
            # Use the zone ID for the domain's hosted zone in Route 53
            zone_id=zone.id,
            name=validation_option["resource_record_name"],
            type=validation_option["resource_record_type"],
            records=[validation_option["resource_record_value"]],
            ttl=60,
        )

        aws.acm.CertificateValidation(
            f"{prefix}CertValidation",
            certificate_arn=cert.arn,
            validation_record_fqdns=[validation_record.fqdn],
            opts=pulumi.ResourceOptions(provider=us_east_1),
        )

        # Exports
        pulumi.export(f"{prefix}_zone_arn", pulumi.Output.secret(zone.arn))
        pulumi.export(f"{prefix}_zone_id", pulumi.Output.secret(zone.id))
        pulumi.export(f"{prefix}_cert_arn", pulumi.Output.secret(cert.arn))
        pulumi.export(f"{prefix}_cert_id", pulumi.Output.secret(cert.id))
        pulumi.export(f"{prefix}_domain", domain_conf["cert_domain"])


# Import the program's configuration settings.
config = pulumi.Config()
stack(config)
