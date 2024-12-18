from .type_system import TypeDefinition, FieldDefinition, TypeConstraint, CustomType

def register_builtin_types(type_registry):
    """Register all built-in types with the type registry"""
    
    # Base Types
    type_registry.register_type(TypeDefinition(
        name="AwsTaggable",
        fields={
            "tags": FieldDefinition(
                name="tags",
                constraint=TypeConstraint(CustomType("map")),
                default_value={"ManagedBy": "Terraform"},
                description="Resource tags"
            )
        }
    ))

    type_registry.register_type(TypeDefinition(
        name="AwsNameable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Resource name"
            ),
            "name_prefix": FieldDefinition(
                name="name_prefix",
                constraint=TypeConstraint(CustomType("string")),
                description="Resource name prefix",
                default_value=""
            )
        }
    ))

    # EC2 Instance Type
    type_registry.register_type(TypeDefinition(
        name="AwsEc2Instance",
        base_type="AwsTaggable",
        fields={
            "instance_type": FieldDefinition(
                name="instance_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="t2.micro",
                description="EC2 instance type"
            ),
            "ami": FieldDefinition(
                name="ami",
                constraint=TypeConstraint(CustomType("string")),
                description="AMI ID"
            ),
            "subnet_id": FieldDefinition(
                name="subnet_id",
                constraint=TypeConstraint(CustomType("string")),
                description="Subnet ID"
            ),
            "vpc_security_group_ids": FieldDefinition(
                name="vpc_security_group_ids",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[],
                description="List of VPC security group IDs"
            ),
            "key_name": FieldDefinition(
                name="key_name",
                constraint=TypeConstraint(CustomType("string")),
                description="SSH key pair name"
            ),
            "associate_public_ip_address": FieldDefinition(
                name="associate_public_ip_address",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=False,
                description="Associate public IP address"
            ),
            "root_block_device": FieldDefinition(
                name="root_block_device",
                constraint=TypeConstraint(CustomType("map")),
                default_value={
                    "volume_size": 20,
                    "volume_type": "gp2",
                    "delete_on_termination": True
                },
                description="Root block device configuration"
            )
        }
    ))

    # VPC Type
    type_registry.register_type(TypeDefinition(
        name="AwsVpc",
        base_type="AwsTaggable",
        fields={
            "cidr_block": FieldDefinition(
                name="cidr_block",
                constraint=TypeConstraint(CustomType("string")),
                default_value="10.0.0.0/16",
                description="CIDR block for the VPC"
            ),
            "enable_dns_hostnames": FieldDefinition(
                name="enable_dns_hostnames",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=True,
                description="Enable DNS hostnames"
            ),
            "enable_dns_support": FieldDefinition(
                name="enable_dns_support",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=True,
                description="Enable DNS support"
            )
        }
    ))

    # Security Group Type
    type_registry.register_type(TypeDefinition(
        name="AwsSecurityGroup",
        base_type="AwsTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Security group name"
            ),
            "description": FieldDefinition(
                name="description",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Managed by Terraform",
                description="Security group description"
            ),
            "vpc_id": FieldDefinition(
                name="vpc_id",
                constraint=TypeConstraint(CustomType("string")),
                description="VPC ID"
            ),
            "ingress": FieldDefinition(
                name="ingress",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[],
                description="Ingress rules"
            ),
            "egress": FieldDefinition(
                name="egress",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[{
                    "from_port": 0,
                    "to_port": 0,
                    "protocol": "-1",
                    "cidr_blocks": ["0.0.0.0/0"]
                }],
                description="Egress rules"
            )
        }
    ))

    # RDS Instance Type
    type_registry.register_type(TypeDefinition(
        name="AwsRdsInstance",
        base_type="AwsTaggable",
        fields={
            "engine": FieldDefinition(
                name="engine",
                constraint=TypeConstraint(CustomType("string")),
                description="Database engine"
            ),
            "engine_version": FieldDefinition(
                name="engine_version",
                constraint=TypeConstraint(CustomType("string")),
                description="Database engine version"
            ),
            "instance_class": FieldDefinition(
                name="instance_class",
                constraint=TypeConstraint(CustomType("string")),
                default_value="db.t3.micro",
                description="RDS instance class"
            ),
            "allocated_storage": FieldDefinition(
                name="allocated_storage",
                constraint=TypeConstraint(CustomType("number")),
                default_value=20,
                description="Allocated storage size in GB"
            ),
            "storage_type": FieldDefinition(
                name="storage_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="gp2",
                description="Storage type"
            ),
            "username": FieldDefinition(
                name="username",
                constraint=TypeConstraint(CustomType("string")),
                description="Master username"
            ),
            "password": FieldDefinition(
                name="password",
                constraint=TypeConstraint(CustomType("string")),
                description="Master password"
            ),
            "backup_retention_period": FieldDefinition(
                name="backup_retention_period",
                constraint=TypeConstraint(CustomType("number")),
                default_value=7,
                description="Backup retention period in days"
            ),
            "multi_az": FieldDefinition(
                name="multi_az",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=False,
                description="Enable Multi-AZ deployment"
            )
        }
    ))

    # S3 Bucket Type
    type_registry.register_type(TypeDefinition(
        name="AwsS3Bucket",
        base_type="AwsTaggable",
        fields={
            "bucket": FieldDefinition(
                name="bucket",
                constraint=TypeConstraint(CustomType("string")),
                description="Bucket name"
            ),
            "acl": FieldDefinition(
                name="acl",
                constraint=TypeConstraint(CustomType("string")),
                default_value="private",
                description="Access control list"
            ),
            "versioning": FieldDefinition(
                name="versioning",
                constraint=TypeConstraint(CustomType("map")),
                default_value={"enabled": True},
                description="Versioning configuration"
            ),
            "server_side_encryption_configuration": FieldDefinition(
                name="server_side_encryption_configuration",
                constraint=TypeConstraint(CustomType("map")),
                default_value={
                    "rule": {
                        "apply_server_side_encryption_by_default": {
                            "sse_algorithm": "AES256"
                        }
                    }
                },
                description="Server-side encryption configuration"
            )
        }
    ))

    # ECS Cluster Type
    type_registry.register_type(TypeDefinition(
        name="AwsEcsCluster",
        base_type="AwsTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Cluster name"
            ),
            "capacity_providers": FieldDefinition(
                name="capacity_providers",
                constraint=TypeConstraint(CustomType("list")),
                default_value=["FARGATE", "FARGATE_SPOT"],
                description="List of capacity providers"
            ),
            "default_capacity_provider_strategy": FieldDefinition(
                name="default_capacity_provider_strategy",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[{
                    "capacity_provider": "FARGATE",
                    "weight": 1,
                    "base": 1
                }],
                description="Default capacity provider strategy"
            )
        }
    ))

    # ----------------------------------
    # Compute Types
    # ----------------------------------

    # Auto Scaling Group Type
    type_registry.register_type(TypeDefinition(
        name="AwsAutoScalingGroup",
        base_type="AwsTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Auto Scaling Group name"
            ),
            "launch_template": FieldDefinition(
                name="launch_template",
                constraint=TypeConstraint(CustomType("map")),
                description="Launch template configuration"
            ),
            "min_size": FieldDefinition(
                name="min_size",
                constraint=TypeConstraint(CustomType("number")),
                default_value=1,
                description="Minimum number of instances"
            ),
            "max_size": FieldDefinition(
                name="max_size",
                constraint=TypeConstraint(CustomType("number")),
                default_value=3,
                description="Maximum number of instances"
            ),
            "desired_capacity": FieldDefinition(
                name="desired_capacity",
                constraint=TypeConstraint(CustomType("number")),
                default_value=2,
                description="Desired number of instances"
            ),
            "vpc_zone_identifier": FieldDefinition(
                name="vpc_zone_identifier",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[],
                description="List of subnet IDs"
            ),
            "tags": FieldDefinition(
                name="tags",
                constraint=TypeConstraint(CustomType("map")),
                default_value={"ManagedBy": "Terraform"},
                description="Tags for the Auto Scaling Group"
            )
        }
    ))

    # Launch Template Type
    type_registry.register_type(TypeDefinition(
        name="AwsLaunchTemplate",
        base_type="AwsTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Launch Template name"
            ),
            "image_id": FieldDefinition(
                name="image_id",
                constraint=TypeConstraint(CustomType("string")),
                description="AMI ID"
            ),
            "instance_type": FieldDefinition(
                name="instance_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="t2.micro",
                description="Instance type"
            ),
            "key_name": FieldDefinition(
                name="key_name",
                constraint=TypeConstraint(CustomType("string")),
                description="SSH key pair name"
            ),
            "security_group_ids": FieldDefinition(
                name="security_group_ids",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[],
                description="List of security group IDs"
            ),
            "user_data": FieldDefinition(
                name="user_data",
                constraint=TypeConstraint(CustomType("string")),
                default_value="",
                description="User data script"
            )
        }
    ))

    # Lambda Function Type
    type_registry.register_type(TypeDefinition(
        name="AwsLambdaFunction",
        base_type="AwsTaggable",
        fields={
            "function_name": FieldDefinition(
                name="function_name",
                constraint=TypeConstraint(CustomType("string")),
                description="Lambda function name"
            ),
            "runtime": FieldDefinition(
                name="runtime",
                constraint=TypeConstraint(CustomType("string")),
                description="Lambda runtime environment"
            ),
            "role": FieldDefinition(
                name="role",
                constraint=TypeConstraint(CustomType("string")),
                description="IAM role ARN"
            ),
            "handler": FieldDefinition(
                name="handler",
                constraint=TypeConstraint(CustomType("string")),
                description="Function handler"
            ),
            "code": FieldDefinition(
                name="code",
                constraint=TypeConstraint(CustomType("map")),
                description="Code configuration"
            ),
            "timeout": FieldDefinition(
                name="timeout",
                constraint=TypeConstraint(CustomType("number")),
                default_value=3,
                description="Function timeout in seconds"
            ),
            "memory_size": FieldDefinition(
                name="memory_size",
                constraint=TypeConstraint(CustomType("number")),
                default_value=128,
                description="Function memory size in MB"
            )
        }
    ))

    # ECS Service Type
    type_registry.register_type(TypeDefinition(
        name="AwsEcsService",
        base_type="AwsTaggable",
        fields={
            "cluster": FieldDefinition(
                name="cluster",
                constraint=TypeConstraint(CustomType("string")),
                description="ECS Cluster name or ARN"
            ),
            "service_name": FieldDefinition(
                name="service_name",
                constraint=TypeConstraint(CustomType("string")),
                description="ECS Service name"
            ),
            "task_definition": FieldDefinition(
                name="task_definition",
                constraint=TypeConstraint(CustomType("string")),
                description="Task Definition ARN"
            ),
            "desired_count": FieldDefinition(
                name="desired_count",
                constraint=TypeConstraint(CustomType("number")),
                default_value=1,
                description="Desired number of tasks"
            ),
            "launch_type": FieldDefinition(
                name="launch_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="FARGATE",
                description="Launch type (e.g., FARGATE)"
            ),
            "network_configuration": FieldDefinition(
                name="network_configuration",
                constraint=TypeConstraint(CustomType("map")),
                description="Network configuration for the service"
            )
        }
    ))

    # ECS Task Definition Type
    type_registry.register_type(TypeDefinition(
        name="AwsEcsTaskDefinition",
        base_type="AwsTaggable",
        fields={
            "family": FieldDefinition(
                name="family",
                constraint=TypeConstraint(CustomType("string")),
                description="Task definition family"
            ),
            "container_definitions": FieldDefinition(
                name="container_definitions",
                constraint=TypeConstraint(CustomType("list")),
                description="List of container definitions"
            ),
            "network_mode": FieldDefinition(
                name="network_mode",
                constraint=TypeConstraint(CustomType("string")),
                default_value="awsvpc",
                description="Network mode"
            ),
            "requires_compatibilities": FieldDefinition(
                name="requires_compatibilities",
                constraint=TypeConstraint(CustomType("list")),
                default_value=["FARGATE"],
                description="List of required compatibilities"
            ),
            "cpu": FieldDefinition(
                name="cpu",
                constraint=TypeConstraint(CustomType("string")),
                default_value="256",
                description="CPU units"
            ),
            "memory": FieldDefinition(
                name="memory",
                constraint=TypeConstraint(CustomType("string")),
                default_value="512",
                description="Memory in MiB"
            )
        }
    ))

    # ----------------------------------
    # Networking Types
    # ----------------------------------

    # Subnet Type
    type_registry.register_type(TypeDefinition(
        name="AwsSubnet",
        base_type="AwsTaggable",
        fields={
            "cidr_block": FieldDefinition(
                name="cidr_block",
                constraint=TypeConstraint(CustomType("string")),
                description="CIDR block for the subnet"
            ),
            "vpc_id": FieldDefinition(
                name="vpc_id",
                constraint=TypeConstraint(CustomType("string")),
                description="VPC ID"
            ),
            "availability_zone": FieldDefinition(
                name="availability_zone",
                constraint=TypeConstraint(CustomType("string")),
                description="Availability Zone"
            ),
            "map_public_ip_on_launch": FieldDefinition(
                name="map_public_ip_on_launch",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=False,
                description="Map public IP on launch"
            )
        }
    ))

    # Route Table Type
    type_registry.register_type(TypeDefinition(
        name="AwsRouteTable",
        base_type="AwsTaggable",
        fields={
            "vpc_id": FieldDefinition(
                name="vpc_id",
                constraint=TypeConstraint(CustomType("string")),
                description="VPC ID"
            ),
            "routes": FieldDefinition(
                name="routes",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[],
                description="List of routes"
            )
        }
    ))

    # Internet Gateway Type
    type_registry.register_type(TypeDefinition(
        name="AwsInternetGateway",
        base_type="AwsTaggable",
        fields={
            "vpc_id": FieldDefinition(
                name="vpc_id",
                constraint=TypeConstraint(CustomType("string")),
                description="VPC ID"
            )
        }
    ))

    # Load Balancer Type (ALB/NLB)
    type_registry.register_type(TypeDefinition(
        name="AwsLoadBalancer",
        base_type="AwsTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Load Balancer name"
            ),
            "subnets": FieldDefinition(
                name="subnets",
                constraint=TypeConstraint(CustomType("list")),
                description="List of subnet IDs"
            ),
            "security_groups": FieldDefinition(
                name="security_groups",
                constraint=TypeConstraint(CustomType("list")),
                description="List of security group IDs"
            ),
            "load_balancer_type": FieldDefinition(
                name="load_balancer_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="application",
                description="Type of load balancer (application or network)"
            ),
            "scheme": FieldDefinition(
                name="scheme",
                constraint=TypeConstraint(CustomType("string")),
                default_value="internet-facing",
                description="Scheme of the load balancer"
            )
        }
    ))

    # Route53 Record Type
    type_registry.register_type(TypeDefinition(
        name="AwsRoute53Record",
        base_type="AwsTaggable",
        fields={
            "zone_id": FieldDefinition(
                name="zone_id",
                constraint=TypeConstraint(CustomType("string")),
                description="Route53 Hosted Zone ID"
            ),
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="DNS record name"
            ),
            "type": FieldDefinition(
                name="type",
                constraint=TypeConstraint(CustomType("string")),
                description="DNS record type (e.g., A, CNAME)"
            ),
            "ttl": FieldDefinition(
                name="ttl",
                constraint=TypeConstraint(CustomType("number")),
                default_value=300,
                description="Time to live for the DNS record"
            ),
            "records": FieldDefinition(
                name="records",
                constraint=TypeConstraint(CustomType("list")),
                description="List of DNS record values"
            )
        }
    ))

    # ----------------------------------
    # Storage Types
    # ----------------------------------

    # EBS Volume Type
    type_registry.register_type(TypeDefinition(
        name="AwsEbsVolume",
        base_type="AwsTaggable",
        fields={
            "availability_zone": FieldDefinition(
                name="availability_zone",
                constraint=TypeConstraint(CustomType("string")),
                description="Availability Zone"
            ),
            "size": FieldDefinition(
                name="size",
                constraint=TypeConstraint(CustomType("number")),
                default_value=20,
                description="Size of the volume in GB"
            ),
            "volume_type": FieldDefinition(
                name="volume_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="gp2",
                description="Type of the EBS volume"
            ),
            "encrypted": FieldDefinition(
                name="encrypted",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=False,
                description="Enable encryption"
            ),
            "tags": FieldDefinition(
                name="tags",
                constraint=TypeConstraint(CustomType("map")),
                default_value={"ManagedBy": "Terraform"},
                description="Tags for the EBS volume"
            )
        }
    ))

    # EFS File System Type
    type_registry.register_type(TypeDefinition(
        name="AwsEfsFileSystem",
        base_type="AwsTaggable",
        fields={
            "creation_token": FieldDefinition(
                name="creation_token",
                constraint=TypeConstraint(CustomType("string")),
                description="Creation token for the file system"
            ),
            "performance_mode": FieldDefinition(
                name="performance_mode",
                constraint=TypeConstraint(CustomType("string")),
                default_value="generalPurpose",
                description="Performance mode of the file system"
            ),
            "encrypted": FieldDefinition(
                name="encrypted",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=False,
                description="Enable encryption"
            ),
            "tags": FieldDefinition(
                name="tags",
                constraint=TypeConstraint(CustomType("map")),
                default_value={"ManagedBy": "Terraform"},
                description="Tags for the EFS file system"
            )
        }
    ))

    # DynamoDB Table Type
    type_registry.register_type(TypeDefinition(
        name="AwsDynamodbTable",
        base_type="AwsTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="DynamoDB table name"
            ),
            "billing_mode": FieldDefinition(
                name="billing_mode",
                constraint=TypeConstraint(CustomType("string")),
                default_value="PROVISIONED",
                description="Billing mode (e.g., PROVISIONED, PAY_PER_REQUEST)"
            ),
            "hash_key": FieldDefinition(
                name="hash_key",
                constraint=TypeConstraint(CustomType("string")),
                description="Hash key attribute name"
            ),
            "range_key": FieldDefinition(
                name="range_key",
                constraint=TypeConstraint(CustomType("string")),
                description="Range key attribute name",
                default_value=""
            ),
            "attribute_definitions": FieldDefinition(
                name="attribute_definitions",
                constraint=TypeConstraint(CustomType("list")),
                description="List of attribute definitions"
            ),
            "provisioned_throughput": FieldDefinition(
                name="provisioned_throughput",
                constraint=TypeConstraint(CustomType("map")),
                default_value={
                    "read_capacity_units": 5,
                    "write_capacity_units": 5
                },
                description="Provisioned throughput settings"
            ),
            "tags": FieldDefinition(
                name="tags",
                constraint=TypeConstraint(CustomType("map")),
                default_value={"ManagedBy": "Terraform"},
                description="Tags for the DynamoDB table"
            )
        }
    ))

    # ----------------------------------
    # Security/IAM Types
    # ----------------------------------

    # IAM Role Type
    type_registry.register_type(TypeDefinition(
        name="AwsIamRole",
        base_type="AwsTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="IAM role name"
            ),
            "assume_role_policy": FieldDefinition(
                name="assume_role_policy",
                constraint=TypeConstraint(CustomType("string")),
                description="Policy that grants an entity permission to assume the role"
            ),
            "path": FieldDefinition(
                name="path",
                constraint=TypeConstraint(CustomType("string")),
                default_value="/",
                description="Path for the IAM role"
            ),
            "description": FieldDefinition(
                name="description",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Managed by Terraform",
                description="Description of the IAM role"
            )
        }
    ))

    # IAM Policy Type
    type_registry.register_type(TypeDefinition(
        name="AwsIamPolicy",
        base_type="AwsTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="IAM policy name"
            ),
            "policy": FieldDefinition(
                name="policy",
                constraint=TypeConstraint(CustomType("string")),
                description="JSON policy document"
            ),
            "description": FieldDefinition(
                name="description",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Managed by Terraform",
                description="Description of the IAM policy"
            )
        }
    ))

    # IAM User Type
    type_registry.register_type(TypeDefinition(
        name="AwsIamUser",
        base_type="AwsTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="IAM user name"
            ),
            "path": FieldDefinition(
                name="path",
                constraint=TypeConstraint(CustomType("string")),
                default_value="/",
                description="Path for the IAM user"
            ),
            "tags": FieldDefinition(
                name="tags",
                constraint=TypeConstraint(CustomType("map")),
                default_value={"ManagedBy": "Terraform"},
                description="Tags for the IAM user"
            )
        }
    ))

    # KMS Key Type
    type_registry.register_type(TypeDefinition(
        name="AwsKmsKey",
        base_type="AwsTaggable",
        fields={
            "description": FieldDefinition(
                name="description",
                constraint=TypeConstraint(CustomType("string")),
                description="Description of the KMS key"
            ),
            "key_usage": FieldDefinition(
                name="key_usage",
                constraint=TypeConstraint(CustomType("string")),
                default_value="ENCRYPT_DECRYPT",
                description="Key usage (e.g., ENCRYPT_DECRYPT)"
            ),
            "customer_master_key_spec": FieldDefinition(
                name="customer_master_key_spec",
                constraint=TypeConstraint(CustomType("string")),
                default_value="SYMMETRIC_DEFAULT",
                description="Type of key material"
            ),
            "policy": FieldDefinition(
                name="policy",
                constraint=TypeConstraint(CustomType("string")),
                description="IAM policy for the KMS key"
            ),
            "tags": FieldDefinition(
                name="tags",
                constraint=TypeConstraint(CustomType("map")),
                default_value={"ManagedBy": "Terraform"},
                description="Tags for the KMS key"
            )
        }
    ))

    # ----------------------------------
    # GCP Resource Types
    # ----------------------------------
    
    # Base Types for GCP
    type_registry.register_type(TypeDefinition(
        name="GcpTaggable",
        fields={
            "labels": FieldDefinition(
                name="labels",
                constraint=TypeConstraint(CustomType("map")),
                default_value={"managed_by": "terraform"},
                description="Resource labels"
            )
        }
    ))

    type_registry.register_type(TypeDefinition(
        name="GcpNameable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Resource name"
            ),
            "name_prefix": FieldDefinition(
                name="name_prefix",
                constraint=TypeConstraint(CustomType("string")),
                description="Resource name prefix",
                default_value=""
            )
        }
    ))
    
    # ----------------------------------
    # Compute Types
    # ----------------------------------

    # Compute Instance Type
    type_registry.register_type(TypeDefinition(
        name="GcpComputeInstance",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Compute instance name"
            ),
            "machine_type": FieldDefinition(
                name="machine_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="e2-medium",
                description="Machine type (e.g., e2-medium)"
            ),
            "zone": FieldDefinition(
                name="zone",
                constraint=TypeConstraint(CustomType("string")),
                description="GCP zone (e.g., us-central1-a)"
            ),
            "network_interfaces": FieldDefinition(
                name="network_interfaces",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[{
                    "network": "default",
                    "subnetwork": "",
                    "access_configs": [{"type": "ONE_TO_ONE_NAT"}]
                }],
                description="List of network interfaces"
            ),
            "disks": FieldDefinition(
                name="disks",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[{
                    "boot": True,
                    "auto_delete": True,
                    "initialize_params": {
                        "source_image": "projects/debian-cloud/global/images/family/debian-10"
                    }
                }],
                description="List of attached disks"
            ),
            "metadata": FieldDefinition(
                name="metadata",
                constraint=TypeConstraint(CustomType("map")),
                default_value={},
                description="Instance metadata"
            )
        }
    ))
    
    # Instance Template Type
    type_registry.register_type(TypeDefinition(
        name="GcpInstanceTemplate",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Instance template name"
            ),
            "machine_type": FieldDefinition(
                name="machine_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="e2-medium",
                description="Machine type"
            ),
            "region": FieldDefinition(
                name="region",
                constraint=TypeConstraint(CustomType("string")),
                description="GCP region (e.g., us-central1)"
            ),
            "properties": FieldDefinition(
                name="properties",
                constraint=TypeConstraint(CustomType("map")),
                description="Instance properties"
            )
        }
    ))
    
    # Instance Group Type
    type_registry.register_type(TypeDefinition(
        name="GcpInstanceGroup",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Instance group name"
            ),
            "zone": FieldDefinition(
                name="zone",
                constraint=TypeConstraint(CustomType("string")),
                description="GCP zone"
            ),
            "instance_template": FieldDefinition(
                name="instance_template",
                constraint=TypeConstraint(CustomType("string")),
                description="Instance template URL"
            ),
            "target_size": FieldDefinition(
                name="target_size",
                constraint=TypeConstraint(CustomType("number")),
                default_value=1,
                description="Target size of the instance group"
            ),
            "named_ports": FieldDefinition(
                name="named_ports",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[],
                description="List of named ports"
            )
        }
    ))
    
    # Cloud Function Type
    type_registry.register_type(TypeDefinition(
        name="GcpCloudFunction",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Cloud Function name"
            ),
            "runtime": FieldDefinition(
                name="runtime",
                constraint=TypeConstraint(CustomType("string")),
                default_value="python39",
                description="Runtime environment (e.g., python39)"
            ),
            "entry_point": FieldDefinition(
                name="entry_point",
                constraint=TypeConstraint(CustomType("string")),
                description="Function entry point"
            ),
            "source_archive_bucket": FieldDefinition(
                name="source_archive_bucket",
                constraint=TypeConstraint(CustomType("string")),
                description="GCS bucket containing the source code"
            ),
            "source_archive_object": FieldDefinition(
                name="source_archive_object",
                constraint=TypeConstraint(CustomType("string")),
                description="GCS object containing the source code"
            ),
            "trigger_http": FieldDefinition(
                name="trigger_http",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=False,
                description="Trigger function via HTTP"
            ),
            "available_memory_mb": FieldDefinition(
                name="available_memory_mb",
                constraint=TypeConstraint(CustomType("number")),
                default_value=256,
                description="Available memory in MB"
            ),
            "timeout": FieldDefinition(
                name="timeout",
                constraint=TypeConstraint(CustomType("number")),
                default_value=60,
                description="Function timeout in seconds"
            )
        }
    ))
    
    # Cloud Run Service Type
    type_registry.register_type(TypeDefinition(
        name="GcpCloudRunService",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Cloud Run service name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="GCP region (e.g., us-central1)"
            ),
            "image": FieldDefinition(
                name="image",
                constraint=TypeConstraint(CustomType("string")),
                description="Container image URL"
            ),
            "ports": FieldDefinition(
                name="ports",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[{"container_port": 8080}],
                description="List of ports to expose"
            ),
            "ingress": FieldDefinition(
                name="ingress",
                constraint=TypeConstraint(CustomType("string")),
                default_value="all",
                description="Ingress settings (e.g., all, internal)"
            ),
            "memory": FieldDefinition(
                name="memory",
                constraint=TypeConstraint(CustomType("string")),
                default_value="256Mi",
                description="Memory allocation (e.g., 256Mi)"
            ),
            "timeout_seconds": FieldDefinition(
                name="timeout_seconds",
                constraint=TypeConstraint(CustomType("number")),
                default_value=300,
                description="Request timeout in seconds"
            )
        }
    ))
    
    # ----------------------------------
    # Networking Types
    # ----------------------------------

    # VPC Network Type
    type_registry.register_type(TypeDefinition(
        name="GcpVpcNetwork",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="VPC network name"
            ),
            "auto_create_subnetworks": FieldDefinition(
                name="auto_create_subnetworks",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=False,
                description="Whether to auto-create subnetworks"
            ),
            "routing_mode": FieldDefinition(
                name="routing_mode",
                constraint=TypeConstraint(CustomType("string")),
                default_value="GLOBAL",
                description="Routing mode (e.g., GLOBAL, REGIONAL)"
            )
        }
    ))
    
    # Subnet Type
    type_registry.register_type(TypeDefinition(
        name="GcpSubnet",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Subnet name"
            ),
            "network": FieldDefinition(
                name="network",
                constraint=TypeConstraint(CustomType("string")),
                description="VPC network name"
            ),
            "ip_cidr_range": FieldDefinition(
                name="ip_cidr_range",
                constraint=TypeConstraint(CustomType("string")),
                description="IP CIDR range (e.g., 10.0.1.0/24)"
            ),
            "region": FieldDefinition(
                name="region",
                constraint=TypeConstraint(CustomType("string")),
                description="GCP region (e.g., us-central1)"
            ),
            "private_ip_google_access": FieldDefinition(
                name="private_ip_google_access",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=False,
                description="Enable private IP access to Google APIs"
            )
        }
    ))
    
    # Firewall Rule Type
    type_registry.register_type(TypeDefinition(
        name="GcpFirewallRule",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Firewall rule name"
            ),
            "network": FieldDefinition(
                name="network",
                constraint=TypeConstraint(CustomType("string")),
                description="VPC network name"
            ),
            "direction": FieldDefinition(
                name="direction",
                constraint=TypeConstraint(CustomType("string")),
                default_value="INGRESS",
                description="Direction of traffic (INGRESS or EGRESS)"
            ),
            "priority": FieldDefinition(
                name="priority",
                constraint=TypeConstraint(CustomType("number")),
                default_value=1000,
                description="Priority of the firewall rule"
            ),
            "allowed": FieldDefinition(
                name="allowed",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[{"IPProtocol": "tcp", "ports": ["22", "80", "443"]}],
                description="Allowed protocols and ports"
            ),
            "source_ranges": FieldDefinition(
                name="source_ranges",
                constraint=TypeConstraint(CustomType("list")),
                default_value=["0.0.0.0/0"],
                description="Source IP ranges"
            )
        }
    ))
    
    # Load Balancer Type
    type_registry.register_type(TypeDefinition(
        name="GcpLoadBalancer",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Load balancer name"
            ),
            "type": FieldDefinition(
                name="type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="HTTP",
                description="Type of load balancer (e.g., HTTP, TCP)"
            ),
            "region": FieldDefinition(
                name="region",
                constraint=TypeConstraint(CustomType("string")),
                description="GCP region (e.g., us-central1)"
            ),
            "backend_service": FieldDefinition(
                name="backend_service",
                constraint=TypeConstraint(CustomType("string")),
                description="Backend service name or URL"
            ),
            "frontend_configuration": FieldDefinition(
                name="frontend_configuration",
                constraint=TypeConstraint(CustomType("map")),
                description="Frontend configuration settings"
            )
        }
    ))
    
    # Cloud DNS Record Type
    type_registry.register_type(TypeDefinition(
        name="GcpCloudDnsRecord",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="DNS record name"
            ),
            "type": FieldDefinition(
                name="type",
                constraint=TypeConstraint(CustomType("string")),
                description="DNS record type (e.g., A, CNAME)"
            ),
            "ttl": FieldDefinition(
                name="ttl",
                constraint=TypeConstraint(CustomType("number")),
                default_value=300,
                description="Time to live for the DNS record"
            ),
            "rrdatas": FieldDefinition(
                name="rrdatas",
                constraint=TypeConstraint(CustomType("list")),
                description="Resource records data"
            ),
            "zone": FieldDefinition(
                name="zone",
                constraint=TypeConstraint(CustomType("string")),
                description="DNS zone name"
            )
        }
    ))
    
    # ----------------------------------
    # Storage Types
    # ----------------------------------

    # Cloud Storage Bucket Type
    type_registry.register_type(TypeDefinition(
        name="GcpStorageBucket",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Cloud Storage bucket name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                default_value="US",
                description="Bucket location (e.g., US, EU)"
            ),
            "storage_class": FieldDefinition(
                name="storage_class",
                constraint=TypeConstraint(CustomType("string")),
                default_value="STANDARD",
                description="Storage class (e.g., STANDARD, NEARLINE)"
            ),
            "versioning": FieldDefinition(
                name="versioning",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=False,
                description="Enable object versioning"
            ),
            "uniform_bucket_level_access": FieldDefinition(
                name="uniform_bucket_level_access",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=False,
                description="Enable uniform bucket-level access"
            )
        }
    ))
    
    # Persistent Disk Type
    type_registry.register_type(TypeDefinition(
        name="GcpPersistentDisk",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Persistent disk name"
            ),
            "zone": FieldDefinition(
                name="zone",
                constraint=TypeConstraint(CustomType("string")),
                description="GCP zone"
            ),
            "size_gb": FieldDefinition(
                name="size_gb",
                constraint=TypeConstraint(CustomType("number")),
                default_value=50,
                description="Disk size in GB"
            ),
            "type": FieldDefinition(
                name="type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="pd-standard",
                description="Disk type (e.g., pd-standard, pd-ssd)"
            ),
            "labels": FieldDefinition(
                name="labels",
                constraint=TypeConstraint(CustomType("map")),
                default_value={"managed_by": "terraform"},
                description="Disk labels"
            )
        }
    ))
    
    # Cloud SQL Instance Type
    type_registry.register_type(TypeDefinition(
        name="GcpCloudSqlInstance",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Cloud SQL instance name"
            ),
            "database_version": FieldDefinition(
                name="database_version",
                constraint=TypeConstraint(CustomType("string")),
                default_value="MYSQL_8_0",
                description="Database version (e.g., MYSQL_8_0)"
            ),
            "region": FieldDefinition(
                name="region",
                constraint=TypeConstraint(CustomType("string")),
                description="GCP region"
            ),
            "tier": FieldDefinition(
                name="tier",
                constraint=TypeConstraint(CustomType("string")),
                default_value="db-f1-micro",
                description="Machine type (e.g., db-f1-micro)"
            ),
            "storage_auto_resize": FieldDefinition(
                name="storage_auto_resize",
                constraint=TypeConstraint(CustomType("bool")),
                default_value=True,
                description="Enable automatic storage increase"
            ),
            "storage_size": FieldDefinition(
                name="storage_size",
                constraint=TypeConstraint(CustomType("number")),
                default_value=10,
                description="Initial storage size in GB"
            ),
            "storage_type": FieldDefinition(
                name="storage_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="PD_SSD",
                description="Storage type (e.g., PD_SSD, PD_HDD)"
            ),
            "root_password": FieldDefinition(
                name="root_password",
                constraint=TypeConstraint(CustomType("string")),
                description="Root password for the database"
            )
        }
    ))
    
    # Cloud Firestore Type
    type_registry.register_type(TypeDefinition(
        name="GcpCloudFirestore",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Firestore database name"
            ),
            "location_id": FieldDefinition(
                name="location_id",
                constraint=TypeConstraint(CustomType("string")),
                description="GCP location ID (e.g., us-central)"
            ),
            "database_id": FieldDefinition(
                name="database_id",
                constraint=TypeConstraint(CustomType("string")),
                description="Firestore database ID"
            ),
            "type": FieldDefinition(
                name="type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="FIRESTORE_NATIVE",
                description="Database type (e.g., FIRESTORE_NATIVE)"
            ),
            "concurrency_mode": FieldDefinition(
                name="concurrency_mode",
                constraint=TypeConstraint(CustomType("string")),
                default_value="OPTIMISTIC",
                description="Concurrency mode (e.g., OPTIMISTIC)"
            )
        }
    ))
    
    # ----------------------------------
    # Security/IAM Types
    # ----------------------------------

    # Service Account Type
    type_registry.register_type(TypeDefinition(
        name="GcpServiceAccount",
        base_type="GcpTaggable",
        fields={
            "account_id": FieldDefinition(
                name="account_id",
                constraint=TypeConstraint(CustomType("string")),
                description="Service account ID"
            ),
            "display_name": FieldDefinition(
                name="display_name",
                constraint=TypeConstraint(CustomType("string")),
                description="Display name for the service account"
            ),
            "description": FieldDefinition(
                name="description",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Managed by Terraform",
                description="Service account description"
            )
        }
    ))
    
    # IAM Policy Type
    type_registry.register_type(TypeDefinition(
        name="GcpIamPolicy",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="IAM policy name"
            ),
            "policy_data": FieldDefinition(
                name="policy_data",
                constraint=TypeConstraint(CustomType("string")),
                description="JSON policy document"
            ),
            "description": FieldDefinition(
                name="description",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Managed by Terraform",
                description="IAM policy description"
            )
        }
    ))
    
    # IAM Role Type
    type_registry.register_type(TypeDefinition(
        name="GcpIamRole",
        base_type="GcpTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="IAM role name"
            ),
            "title": FieldDefinition(
                name="title",
                constraint=TypeConstraint(CustomType("string")),
                description="Title of the IAM role"
            ),
            "description": FieldDefinition(
                name="description",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Managed by Terraform",
                description="IAM role description"
            ),
            "permissions": FieldDefinition(
                name="permissions",
                constraint=TypeConstraint(CustomType("list")),
                description="List of permissions"
            ),
            "stage": FieldDefinition(
                name="stage",
                constraint=TypeConstraint(CustomType("string")),
                default_value="GA",
                description="Stage of the IAM role (e.g., GA, BETA)"
            )
        }
    ))

    # Base Types for Azure
    type_registry.register_type(TypeDefinition(
        name="AzureTaggable",
        fields={
            "tags": FieldDefinition(
                name="tags",
                constraint=TypeConstraint(CustomType("map")),
                default_value={"managed_by": "terraform"},
                description="Resource tags"
            )
        }
    ))

    type_registry.register_type(TypeDefinition(
        name="AzureNameable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Resource name"
            ),
            "name_prefix": FieldDefinition(
                name="name_prefix",
                constraint=TypeConstraint(CustomType("string")),
                description="Resource name prefix",
                default_value=""
            )
        }
    ))
    
    # ----------------------------------
    # Azure Compute Types
    # ----------------------------------

    # Virtual Machine Type
    type_registry.register_type(TypeDefinition(
        name="AzureVirtualMachine",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Virtual Machine name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "vm_size": FieldDefinition(
                name="vm_size",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Standard_DS1_v2",
                description="VM size (e.g., Standard_DS1_v2)"
            ),
            "network_interface_ids": FieldDefinition(
                name="network_interface_ids",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[],
                description="List of Network Interface IDs"
            ),
            "storage_profile": FieldDefinition(
                name="storage_profile",
                constraint=TypeConstraint(CustomType("map")),
                description="Storage profile configuration"
            ),
            "os_profile": FieldDefinition(
                name="os_profile",
                constraint=TypeConstraint(CustomType("map")),
                description="OS profile configuration"
            ),
            "admin_username": FieldDefinition(
                name="admin_username",
                constraint=TypeConstraint(CustomType("string")),
                description="Administrator username"
            ),
            "admin_password": FieldDefinition(
                name="admin_password",
                constraint=TypeConstraint(CustomType("string")),
                description="Administrator password"
            )
        }
    ))
    
    # VM Scale Set Type
    type_registry.register_type(TypeDefinition(
        name="AzureVmScaleSet",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="VM Scale Set name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "sku": FieldDefinition(
                name="sku",
                constraint=TypeConstraint(CustomType("map")),
                description="SKU information for the scale set"
            ),
            "upgrade_policy": FieldDefinition(
                name="upgrade_policy",
                constraint=TypeConstraint(CustomType("map")),
                description="Upgrade policy configuration"
            ),
            "virtual_machine_profile": FieldDefinition(
                name="virtual_machine_profile",
                constraint=TypeConstraint(CustomType("map")),
                description="Virtual machine profile configuration"
            )
        }
    ))
    
    # Function App Type
    type_registry.register_type(TypeDefinition(
        name="AzureFunctionApp",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Function App name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "app_service_plan_id": FieldDefinition(
                name="app_service_plan_id",
                constraint=TypeConstraint(CustomType("string")),
                description="App Service Plan ID"
            ),
            "storage_account_name": FieldDefinition(
                name="storage_account_name",
                constraint=TypeConstraint(CustomType("string")),
                description="Storage Account name"
            ),
            "runtime_stack": FieldDefinition(
                name="runtime_stack",
                constraint=TypeConstraint(CustomType("string")),
                default_value="python|3.9",
                description="Runtime stack (e.g., python|3.9)"
            )
        }
    ))
    
    # App Service Type
    type_registry.register_type(TypeDefinition(
        name="AzureAppService",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="App Service name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "app_service_plan_id": FieldDefinition(
                name="app_service_plan_id",
                constraint=TypeConstraint(CustomType("string")),
                description="App Service Plan ID"
            ),
            "runtime_stack": FieldDefinition(
                name="runtime_stack",
                constraint=TypeConstraint(CustomType("string")),
                default_value="DOTNETCORE|3.1",
                description="Runtime stack (e.g., DOTNETCORE|3.1)"
            ),
            "site_config": FieldDefinition(
                name="site_config",
                constraint=TypeConstraint(CustomType("map")),
                description="Site configuration settings"
            )
        }
    ))
    
    # Container Instance Type
    type_registry.register_type(TypeDefinition(
        name="AzureContainerInstance",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Container Instance name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "container_group_name": FieldDefinition(
                name="container_group_name",
                constraint=TypeConstraint(CustomType("string")),
                description="Container Group name"
            ),
            "os_type": FieldDefinition(
                name="os_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Linux",
                description="Operating system type (e.g., Linux, Windows)"
            ),
            "containers": FieldDefinition(
                name="containers",
                constraint=TypeConstraint(CustomType("list")),
                description="List of containers within the instance"
            ),
            "ip_address_type": FieldDefinition(
                name="ip_address_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Public",
                description="IP address type (e.g., Public, Private)"
            ),
            "ports": FieldDefinition(
                name="ports",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[80],
                description="List of ports to expose"
            )
        }
    ))
    
    # ----------------------------------
    # Azure Networking Types
    # ----------------------------------
    
    # Virtual Network Type
    type_registry.register_type(TypeDefinition(
        name="AzureVirtualNetwork",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Virtual Network name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "address_space": FieldDefinition(
                name="address_space",
                constraint=TypeConstraint(CustomType("list")),
                description="List of address spaces (e.g., ['10.0.0.0/16'])"
            ),
            "subnets": FieldDefinition(
                name="subnets",
                constraint=TypeConstraint(CustomType("list")),
                description="List of subnets within the virtual network"
            )
        }
    ))
    
    # Subnet Type
    type_registry.register_type(TypeDefinition(
        name="AzureSubnet",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Subnet name"
            ),
            "virtual_network_name": FieldDefinition(
                name="virtual_network_name",
                constraint=TypeConstraint(CustomType("string")),
                description="Parent Virtual Network name"
            ),
            "address_prefix": FieldDefinition(
                name="address_prefix",
                constraint=TypeConstraint(CustomType("string")),
                description="Address prefix (e.g., 10.0.1.0/24)"
            ),
            "network_security_group_id": FieldDefinition(
                name="network_security_group_id",
                constraint=TypeConstraint(CustomType("string")),
                description="Network Security Group ID"
            )
        }
    ))
    
    # Network Security Group Type
    type_registry.register_type(TypeDefinition(
        name="AzureNetworkSecurityGroup",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Network Security Group name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "security_rules": FieldDefinition(
                name="security_rules",
                constraint=TypeConstraint(CustomType("list")),
                description="List of security rules"
            )
        }
    ))
    
    # Application Gateway Type
    type_registry.register_type(TypeDefinition(
        name="AzureApplicationGateway",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Application Gateway name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "sku": FieldDefinition(
                name="sku",
                constraint=TypeConstraint(CustomType("map")),
                description="SKU information for the Application Gateway"
            ),
            "gateway_ip_configurations": FieldDefinition(
                name="gateway_ip_configurations",
                constraint=TypeConstraint(CustomType("list")),
                description="List of IP configurations"
            ),
            "frontend_ip_configurations": FieldDefinition(
                name="frontend_ip_configurations",
                constraint=TypeConstraint(CustomType("list")),
                description="List of frontend IP configurations"
            ),
            "frontend_ports": FieldDefinition(
                name="frontend_ports",
                constraint=TypeConstraint(CustomType("list")),
                description="List of frontend ports"
            ),
            "backend_address_pools": FieldDefinition(
                name="backend_address_pools",
                constraint=TypeConstraint(CustomType("list")),
                description="List of backend address pools"
            ),
            "backend_http_settings_collection": FieldDefinition(
                name="backend_http_settings_collection",
                constraint=TypeConstraint(CustomType("list")),
                description="Collection of backend HTTP settings"
            ),
            "http_listeners": FieldDefinition(
                name="http_listeners",
                constraint=TypeConstraint(CustomType("list")),
                description="List of HTTP listeners"
            ),
            "request_routing_rules": FieldDefinition(
                name="request_routing_rules",
                constraint=TypeConstraint(CustomType("list")),
                description="List of request routing rules"
            )
        }
    ))
    
    # Load Balancer Type
    type_registry.register_type(TypeDefinition(
        name="AzureLoadBalancer",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Load Balancer name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "frontend_ip_configurations": FieldDefinition(
                name="frontend_ip_configurations",
                constraint=TypeConstraint(CustomType("list")),
                description="List of frontend IP configurations"
            ),
            "backend_address_pools": FieldDefinition(
                name="backend_address_pools",
                constraint=TypeConstraint(CustomType("list")),
                description="List of backend address pools"
            ),
            "load_balancing_rules": FieldDefinition(
                name="load_balancing_rules",
                constraint=TypeConstraint(CustomType("list")),
                description="List of load balancing rules"
            ),
            "probes": FieldDefinition(
                name="probes",
                constraint=TypeConstraint(CustomType("list")),
                description="List of probes"
            )
        }
    ))
    
    # DNS Zone Type
    type_registry.register_type(TypeDefinition(
        name="AzureDnsZone",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="DNS Zone name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                default_value="global",
                description="Azure location (usually 'global')"
            ),
            "zone_type": FieldDefinition(
                name="zone_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Public",
                description="DNS zone type (Public or Private)"
            ),
            "registration_virtual_networks": FieldDefinition(
                name="registration_virtual_networks",
                constraint=TypeConstraint(CustomType("list")),
                default_value=[],
                description="List of virtual networks for private DNS zones"
            )
        }
    ))
    
    # ----------------------------------
    # Azure Storage Types
    # ----------------------------------
    
    # Storage Account Type
    type_registry.register_type(TypeDefinition(
        name="AzureStorageAccount",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Storage Account name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "account_tier": FieldDefinition(
                name="account_tier",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Standard",
                description="Storage account tier (e.g., Standard, Premium)"
            ),
            "account_replication_type": FieldDefinition(
                name="account_replication_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="LRS",
                description="Replication type (e.g., LRS, GRS)"
            ),
            "access_tier": FieldDefinition(
                name="access_tier",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Hot",
                description="Access tier (e.g., Hot, Cool)"
            )
        }
    ))
    
    # Managed Disk Type
    type_registry.register_type(TypeDefinition(
        name="AzureManagedDisk",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Managed Disk name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "disk_size_gb": FieldDefinition(
                name="disk_size_gb",
                constraint=TypeConstraint(CustomType("number")),
                default_value=128,
                description="Disk size in GB"
            ),
            "disk_publisher": FieldDefinition(
                name="disk_publisher",
                constraint=TypeConstraint(CustomType("string")),
                default_value="MicrosoftWindowsServer",
                description="Disk publisher (e.g., MicrosoftWindowsServer)"
            ),
            "disk_offer": FieldDefinition(
                name="disk_offer",
                constraint=TypeConstraint(CustomType("string")),
                default_value="WindowsServer",
                description="Disk offer (e.g., WindowsServer)"
            ),
            "disk_sku": FieldDefinition(
                name="disk_sku",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Standard_LRS",
                description="Disk SKU (e.g., Standard_LRS, Premium_LRS)"
            ),
            "disk_presentation_type": FieldDefinition(
                name="disk_presentation_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="OS",
                description="Disk presentation type (e.g., OS, Data)"
            )
        }
    ))
    
    # SQL Database Type
    type_registry.register_type(TypeDefinition(
        name="AzureSqlDatabase",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="SQL Database name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "server_name": FieldDefinition(
                name="server_name",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure SQL Server name"
            ),
            "edition": FieldDefinition(
                name="edition",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Basic",
                description="SQL Database edition (e.g., Basic, Standard, Premium)"
            ),
            "max_size_bytes": FieldDefinition(
                name="max_size_bytes",
                constraint=TypeConstraint(CustomType("number")),
                default_value=1073741824,  # 1 GB
                description="Maximum size in bytes"
            ),
            "requested_service_objective_name": FieldDefinition(
                name="requested_service_objective_name",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Basic",
                description="Service objective name (e.g., Basic, S0, P1)"
            )
        }
    ))
    
    # CosmosDB Account Type
    type_registry.register_type(TypeDefinition(
        name="AzureCosmosDbAccount",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Cosmos DB Account name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "offer_type": FieldDefinition(
                name="offer_type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="Standard",
                description="Offer type (e.g., Standard, LowLatency)"
            ),
            "kind": FieldDefinition(
                name="kind",
                constraint=TypeConstraint(CustomType("string")),
                default_value="GlobalDocumentDB",
                description="Kind of Cosmos DB account (e.g., GlobalDocumentDB, MongoDB)"
            ),
            "consistency_policy": FieldDefinition(
                name="consistency_policy",
                constraint=TypeConstraint(CustomType("map")),
                description="Consistency policy settings"
            ),
            "geo_locations": FieldDefinition(
                name="geo_locations",
                constraint=TypeConstraint(CustomType("list")),
                description="List of geographic locations for replication"
            )
        }
    ))
    
    # ----------------------------------
    # Azure Security/IAM Types
    # ----------------------------------
    
    # Azure AD Application Type
    type_registry.register_type(TypeDefinition(
        name="AzureAdApplication",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure AD Application name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "homepage": FieldDefinition(
                name="homepage",
                constraint=TypeConstraint(CustomType("string")),
                description="Homepage URL of the application"
            ),
            "identifier_uris": FieldDefinition(
                name="identifier_uris",
                constraint=TypeConstraint(CustomType("list")),
                description="List of identifier URIs"
            ),
            "reply_urls": FieldDefinition(
                name="reply_urls",
                constraint=TypeConstraint(CustomType("list")),
                description="List of reply URLs"
            ),
            "required_resource_access": FieldDefinition(
                name="required_resource_access",
                constraint=TypeConstraint(CustomType("list")),
                description="List of required resource access"
            )
        }
    ))
    
    # Role Assignment Type
    type_registry.register_type(TypeDefinition(
        name="AzureRoleAssignment",
        base_type="AzureTaggable",
        fields={
            "role_definition_id": FieldDefinition(
                name="role_definition_id",
                constraint=TypeConstraint(CustomType("string")),
                description="Role Definition ID"
            ),
            "principal_id": FieldDefinition(
                name="principal_id",
                constraint=TypeConstraint(CustomType("string")),
                description="Principal ID (e.g., User, Group, Service Principal)"
            ),
            "scope": FieldDefinition(
                name="scope",
                constraint=TypeConstraint(CustomType("string")),
                description="Scope of the role assignment (e.g., subscription, resource group)"
            )
        }
    ))
    
    # Key Vault Type
    type_registry.register_type(TypeDefinition(
        name="AzureKeyVault",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Key Vault name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "sku_name": FieldDefinition(
                name="sku_name",
                constraint=TypeConstraint(CustomType("string")),
                default_value="standard",
                description="SKU name (e.g., standard, premium)"
            ),
            "tenant_id": FieldDefinition(
                name="tenant_id",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Active Directory tenant ID"
            ),
            "access_policies": FieldDefinition(
                name="access_policies",
                constraint=TypeConstraint(CustomType("list")),
                description="List of access policies"
            )
        }
    ))
    
    # Managed Identity Type
    type_registry.register_type(TypeDefinition(
        name="AzureManagedIdentity",
        base_type="AzureTaggable",
        fields={
            "name": FieldDefinition(
                name="name",
                constraint=TypeConstraint(CustomType("string")),
                description="Managed Identity name"
            ),
            "resource_group": FieldDefinition(
                name="resource_group",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure Resource Group name"
            ),
            "location": FieldDefinition(
                name="location",
                constraint=TypeConstraint(CustomType("string")),
                description="Azure location (e.g., eastus)"
            ),
            "type": FieldDefinition(
                name="type",
                constraint=TypeConstraint(CustomType("string")),
                default_value="SystemAssigned",
                description="Type of Managed Identity (SystemAssigned or UserAssigned)"
            ),
            "principal_id": FieldDefinition(
                name="principal_id",
                constraint=TypeConstraint(CustomType("string")),
                description="Principal ID of the Managed Identity"
            )
        }
    ))