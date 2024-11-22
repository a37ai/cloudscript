from .data_and_types import IaCGenerator, TerraformConfig, TerraformBlock, TerraformBlockType, Service, InfrastructureComponent
from typing import List, Dict, Any, Optional
from enum import Enum
import json

class TerraformGenerator(IaCGenerator):
    def __init__(self):
        self.resource_type_mapping = {
            "network": {
                "aws": "aws_vpc",
                "gcp": "google_compute_network",
                "azure": "azurerm_virtual_network"
            },
            "compute": {
                "aws": "aws_instance",
                "gcp": "google_compute_instance",
                "azure": "azurerm_virtual_machine"
            },
            "security_group": {
                "aws": "aws_security_group",
                "gcp": "google_compute_firewall",
                "azure": "azurerm_network_security_group"
            },
            "kubernetes": {
                "aws": "aws_eks_cluster",
                "gcp": "google_container_cluster",
                "azure": "azurerm_kubernetes_cluster"
            },
            "database": {
                "aws": "aws_db_instance",
                "gcp": "google_sql_database_instance",
                "azure": "azurerm_sql_database"
            },
            "storage": {
                "aws": "aws_s3_bucket",
                "gcp": "google_storage_bucket",
                "azure": "azurerm_storage_account"
            },
            "load_balancer": {
                "aws": "aws_lb",
                "gcp": "google_compute_forwarding_rule",
                "azure": "azurerm_lb"
            },
            "iam_role": {
                "aws": "aws_iam_role",
                "gcp": "google_service_account",
                "azure": "azurerm_role_definition"
            },
            "iam_policy": {
                "aws": "aws_iam_policy",
                "gcp": "google_iam_policy",
                "azure": "azurerm_role_assignment"
            },
            "dns": {
                "aws": "aws_route53_zone",
                "gcp": "google_dns_managed_zone",
                "azure": "azurerm_dns_zone"
            },
            "vpn": {
                "aws": "aws_vpn_connection",
                "gcp": "google_compute_vpn_gateway",
                "azure": "azurerm_virtual_network_gateway"
            },
            "autoscaling": {
                "aws": "aws_autoscaling_group",
                "gcp": "google_compute_autoscaler",
                "azure": "azurerm_virtual_machine_scale_set"
            },
            "monitoring": {
                "aws": "aws_cloudwatch_alarm",
                "gcp": "google_monitoring_alert_policy",
                "azure": "azurerm_monitor_metric_alert"
            },
            "function": {
                "aws": "aws_lambda_function",
                "gcp": "google_cloudfunctions_function",
                "azure": "azurerm_function_app"
            },
            "queue": {
                "aws": "aws_sqs_queue",
                "gcp": "google_pubsub_topic",
                "azure": "azurerm_storage_queue"
            },
            "container_registry": {
                "aws": "aws_ecr_repository",
                "gcp": "google_container_registry",
                "azure": "azurerm_container_registry"
            },
            "cache": {
                "aws": "aws_elasticache_cluster",
                "gcp": "google_redis_instance",
                "azure": "azurerm_redis_cache"
            },
            "eventbridge": {
                "aws": "aws_cloudwatch_event_rule",
                "gcp": "google_cloud_scheduler_job",
                "azure": "azurerm_eventgrid_event_subscription"
            },
            "secret": {
                "aws": "aws_secretsmanager_secret",
                "gcp": "google_secret_manager_secret",
                "azure": "azurerm_key_vault_secret"
            }
            # Add more mappings as needed
        }

    def generate(self, services: List['Service']) -> str:
        tf_config = TerraformConfig()

        # Add default provider configurations
        self._add_default_providers(tf_config)

        # Process all services based on the defined order
        for service in services:
            print(f"Processing service: {service.name}")

            # Process infrastructure components
            for component in service.infrastructure:
                self._process_infrastructure_component(component, service, tf_config)

            # Process deployment dependencies and patterns
            if service.deployment:
                self._process_deployment(service, tf_config)

            # Add service-specific outputs
            self._add_service_outputs(service, tf_config)

        print("Resources before serialization:")
        print(json.dumps(tf_config.resources, indent=2))

        print("Locals before serialization:")
        print(json.dumps(tf_config.locals, indent=2))

        # Convert to Terraform JSON format
        return self._to_json(tf_config)

    def _add_default_providers(self, tf_config: TerraformConfig):
        # Example: Add AWS provider with common configuration
        tf_config.providers["aws"] = {
            "region": {"reference": "var.aws_region"},
            "assume_role": {
                "role_arn": {"reference": "var.assume_role_arn"}
            }
        }

        # Add corresponding variables
        tf_config.variables["aws_region"] = {
            "type": "string",
            "description": "AWS region to deploy resources"
        }
        tf_config.variables["assume_role_arn"] = {
            "type": "string",
            "description": "ARN of the role to assume",
            "default": None
        }

    def _process_infrastructure_component(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig):
        provider = component.provider or service.provider or "aws"
        resource_type = self._get_resource_type(component, provider)

        if not resource_type:
            print(f"Unsupported provider '{provider}' or component type '{component.component_type}' for component '{component.name}'. Skipping.")
            return

        component.resource_type = resource_type

        # Handle dependencies
        if component.depends_on:
            component.depends_on = [self._get_resource_address(dep) for dep in component.depends_on]

        if component.component_type == "network":
            self._process_network(component, service, tf_config)
        elif component.component_type == "compute":
            self._process_compute(component, service, tf_config)
        elif component.component_type == "security_group":
            self._process_security_group(component, service, tf_config)
        elif component.component_type == "kubernetes":
            self._process_kubernetes(component, service, tf_config)
        # Add more component types as needed

    def _process_network(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig):
        print(f"Processing network component: {component.name}")

        provider = component.provider or service.provider or "aws"
        resource_type = component.resource_type

        vpc_name = component.name
        vpc_resource_name = vpc_name  # Use component name directly

        # Create VPC resource
        vpc_resource = {
            "cidr_block": component.attributes.get("vpc_cidr", "10.0.0.0/16"),
            "enable_dns_support": True,
            "enable_dns_hostnames": True,
            "tags": self._merge_tags(component.attributes.get("tags", {}), service.name)
        }

        tf_config.resources.setdefault(resource_type, {})[vpc_resource_name] = vpc_resource

        # Create subnets
        if "availability_zones" in component.attributes and "subnet_cidrs" in component.attributes:
            azs = component.attributes["availability_zones"]
            subnet_cidrs = component.attributes["subnet_cidrs"]
            public_subnets = []

            for idx, (az, cidr) in enumerate(zip(azs, subnet_cidrs)):
                subnet_name = f"{vpc_name}_subnet_{idx + 1}"
                subnet_resource = {
                    "vpc_id": f"${{aws_vpc.{vpc_resource_name}.id}}",
                    "cidr_block": cidr,
                    "availability_zone": az,
                    "map_public_ip_on_launch": component.attributes.get("enable_public_ip", True),
                    "tags": self._merge_tags({"Name": subnet_name}, service.name)
                }
                tf_config.resources.setdefault("aws_subnet", {})[subnet_name] = subnet_resource
                public_subnets.append(f"${{aws_subnet.{subnet_name}.id}}")

            # Create Internet Gateway
            igw_name = f"{vpc_name}_igw"
            igw_resource = {
                "vpc_id": f"${{aws_vpc.{vpc_resource_name}.id}}",
                "tags": self._merge_tags({"Name": igw_name}, service.name)
            }
            tf_config.resources.setdefault("aws_internet_gateway", {})[igw_name] = igw_resource

            # Create Route Table
            route_table_name = f"{vpc_name}_route_table"
            route_table_resource = {
                "vpc_id": f"${{aws_vpc.{vpc_resource_name}.id}}",
                "route": [
                    {
                        "cidr_block": "0.0.0.0/0",
                        "gateway_id": f"${{aws_internet_gateway.{igw_name}.id}}",
                        # Include all required attributes set to null
                        "carrier_gateway_id": None,
                        "core_network_arn": None,
                        "destination_prefix_list_id": None,
                        "egress_only_gateway_id": None,
                        "ipv6_cidr_block": None,
                        "local_gateway_id": None,
                        "nat_gateway_id": None,
                        "network_interface_id": None,
                        "transit_gateway_id": None,
                        "vpc_endpoint_id": None,
                        "vpc_peering_connection_id": None
                    }
                ],
                "tags": self._merge_tags({"Name": route_table_name}, service.name)
            }
            tf_config.resources.setdefault("aws_route_table", {})[route_table_name] = route_table_resource

            # Associate subnets with route table
            for idx in range(len(public_subnets)):
                route_table_assoc_name = f"{vpc_name}_route_table_assoc_{idx + 1}"
                route_table_assoc_resource = {
                    "subnet_id": public_subnets[idx],
                    "route_table_id": f"${{aws_route_table.{route_table_name}.id}}"
                }
                tf_config.resources.setdefault("aws_route_table_association", {})[route_table_assoc_name] = route_table_assoc_resource

            # Store public subnets in locals for easy reference
            tf_config.locals[f"{vpc_name}_public_subnets"] = public_subnets

        # Store VPC ID as output
        tf_config.outputs[f"{component.name}_vpc_id"] = {
            "value": f"${{aws_vpc.{vpc_resource_name}.id}}",
            "description": f"ID of VPC {component.name}"
        }

    def _process_compute(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig):
        print(f"Processing compute component: {component.name}")

        resource_type = component.resource_type
        compute_attrs = component.attributes

        tf_resource = {
            "ami": compute_attrs.get("ami"),
            "instance_type": compute_attrs.get("instance_type", "t2.micro"),
            "subnet_id": self._resolve_reference(compute_attrs.get("subnet")),
            "tags": self._merge_tags(compute_attrs.get("tags", {}), service.name),
        }

        # Handle user_data
        if "user_data" in compute_attrs:
            tf_resource["user_data"] = compute_attrs.get("user_data")

        # Handle key_name
        if "key_name" in compute_attrs:
            tf_resource["key_name"] = compute_attrs.get("key_name")

        # Handle iam_instance_profile
        if "iam_instance_profile" in compute_attrs:
            tf_resource["iam_instance_profile"] = compute_attrs.get("iam_instance_profile")

        # Handle associate_public_ip_address
        if "associate_public_ip_address" in compute_attrs:
            tf_resource["associate_public_ip_address"] = compute_attrs.get("associate_public_ip_address")

        # Handle root_block_device
        if "root_block_device" in compute_attrs:
            tf_resource["root_block_device"] = compute_attrs.get("root_block_device")

        # Handle security group
        security_group_name = f"{component.name}_sg"
        self._create_security_group(security_group_name, compute_attrs.get("security_rules", {}), component, service, tf_config)
        tf_resource["vpc_security_group_ids"] = [f"${{aws_security_group.{security_group_name}.id}}"]

        # Handle dependencies
        if component.depends_on:
            tf_resource["depends_on"] = component.depends_on
        
        if "subnet" in compute_attrs:
            tf_resource["subnet_id"] = self._resolve_reference(compute_attrs.get("subnet"))
        else:
            # Default to the first public subnet if not specified
            vpc_name = self._find_vpc_name(service)
            tf_resource["subnet_id"] = f"${{local.{vpc_name}_public_subnets[0]}}"

        tf_config.resources.setdefault(resource_type, {})[component.name] = tf_resource

    def _find_vpc_name(self, service: Service) -> Optional[str]:
        for component in service.infrastructure:
            if component.component_type == "network":
                return component.name
        print(f"No VPC component found for service '{service.name}'.")
        return None
    
    def _create_security_group(self, sg_name: str, security_rules: Dict[str, Any], component: InfrastructureComponent, service: Service, tf_config: TerraformConfig):
        print(f"Creating security group: {sg_name}")

        vpc_resource_name = self._find_vpc_name(service)
        if not vpc_resource_name:
            print(f"Cannot create security group '{sg_name}' as no VPC was found for service '{service.name}'.")
            return

        sg_resource = {
            "name": sg_name,
            "description": f"Security group for {component.name}",
            "vpc_id": f"${{aws_vpc.{vpc_resource_name}.id}}",
            "ingress": [],
            "egress": [],
            "tags": self._merge_tags(component.attributes.get("tags", {}), service.name)
        }

        # Default values for required attributes
        default_ingress_egress_attrs = {
            "ipv6_cidr_blocks": [],
            "prefix_list_ids": [],
            "security_groups": [],
            "self": False
        }

        for rule in security_rules.get("inbound", []):
            ingress_rule = {
                "from_port": rule["port"],
                "to_port": rule["port"],
                "protocol": rule["protocol"],
                "cidr_blocks": [rule["cidr"]],
                "description": rule.get("description", "")
            }
            # Include required attributes with default values
            ingress_rule.update(default_ingress_egress_attrs)
            sg_resource["ingress"].append(ingress_rule)

        for rule in security_rules.get("outbound", []):
            egress_rule = {
                "from_port": rule["port"],
                "to_port": rule["port"],
                "protocol": rule["protocol"],
                "cidr_blocks": [rule["cidr"]],
                "description": rule.get("description", "")
            }
            # Include required attributes with default values
            egress_rule.update(default_ingress_egress_attrs)
            sg_resource["egress"].append(egress_rule)

        tf_config.resources.setdefault("aws_security_group", {})[sg_name] = sg_resource
        print(f"Security group '{sg_name}' created with VPC ID reference '${{{self.resource_type_mapping['network']['aws']}.{vpc_resource_name}.id}}'.")
    def _process_security_group(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig):
        print(f"Processing security group component: {component.name}")

        resource_type = component.resource_type
        sg_attrs = component.attributes

        ingress_rules = sg_attrs.get("ingress", [])
        egress_rules = sg_attrs.get("egress", [])

        tf_resource = {
            "name": f"{service.name}-sg",
            "description": sg_attrs.get("description", f"Security group for {service.name}"),
            "vpc_id": self._resolve_reference(sg_attrs.get("vpc_id")),
            "ingress": [],
            "egress": [],
            "tags": self._merge_tags(sg_attrs.get("tags", {}), service.name)
        }

        for rule in ingress_rules:
            tf_resource["ingress"].append({
                "from_port": rule["port"],
                "to_port": rule["port"],
                "protocol": rule["protocol"],
                "cidr_blocks": [rule["cidr"]],
                "description": rule.get("description", "")
            })

        for rule in egress_rules:
            tf_resource["egress"].append({
                "from_port": rule["port"],
                "to_port": rule["port"],
                "protocol": rule["protocol"],
                "cidr_blocks": [rule["cidr"]],
                "description": rule.get("description", "")
            })

        tf_config.resources.setdefault(resource_type, {})[component.name] = tf_resource

    def _process_kubernetes(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig):
        print(f"Processing Kubernetes component: {component.name}")

        resource_type = component.resource_type
        k8s_attrs = component.attributes

        cluster_name = k8s_attrs.get("name", f"{service.name}-cluster")
        cluster_resource_name = component.name

        # Create IAM role for EKS cluster
        cluster_role_name = f"{cluster_resource_name}_role"
        cluster_role_resource = {
            "name": cluster_role_name,
            "assume_role_policy": json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "eks.amazonaws.com"
                    }
                }]
            }),
            "tags": self._merge_tags({}, service.name)
        }
        tf_config.resources.setdefault("aws_iam_role", {})[cluster_role_name] = cluster_role_resource

        # Attach policies to the cluster role
        tf_config.resources.setdefault("aws_iam_role_policy_attachment", {})[f"{cluster_role_name}_policy"] = {
            "role": f"${{aws_iam_role.{cluster_role_name}.name}}",
            "policy_arn": "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
        }

        # Get subnet IDs from the VPC public subnets
        vpc_name = self._find_vpc_name(service)
        subnet_ids = f"${{local.{vpc_name}_public_subnets}}"

        # Create EKS Cluster resource
        cluster_resource = {
            "name": cluster_name,
            "role_arn": f"${{aws_iam_role.{cluster_role_name}.arn}}",
            "vpc_config": {
                "subnet_ids": subnet_ids,
                "endpoint_public_access": True,
            },
            "tags": self._merge_tags(k8s_attrs.get("tags", {}), service.name),
        }

        tf_config.resources.setdefault(resource_type, {})[cluster_resource_name] = cluster_resource

        # Create IAM role for node group
        node_role_name = f"{cluster_resource_name}_node_role"
        node_role_resource = {
            "name": node_role_name,
            "assume_role_policy": json.dumps({
                "Version": "2012-10-17",
                "Statement": [{
                    "Action": "sts:AssumeRole",
                    "Effect": "Allow",
                    "Principal": {
                        "Service": "ec2.amazonaws.com"
                    }
                }]
            }),
            "tags": self._merge_tags({}, service.name)
        }
        tf_config.resources.setdefault("aws_iam_role", {})[node_role_name] = node_role_resource

        # Attach policies to the node role
        tf_config.resources.setdefault("aws_iam_role_policy_attachment", {})[f"{node_role_name}_policy1"] = {
            "role": f"${{aws_iam_role.{node_role_name}.name}}",
            "policy_arn": "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
        }
        tf_config.resources.setdefault("aws_iam_role_policy_attachment", {})[f"{node_role_name}_policy2"] = {
            "role": f"${{aws_iam_role.{node_role_name}.name}}",
            "policy_arn": "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
        }
        tf_config.resources.setdefault("aws_iam_role_policy_attachment", {})[f"{node_role_name}_policy3"] = {
            "role": f"${{aws_iam_role.{node_role_name}.name}}",
            "policy_arn": "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
        }

        # Create Node Group resources
        node_pools = k8s_attrs.get("node_pools", [])
        for idx, node_pool in enumerate(node_pools):
            node_group_name = f"{cluster_resource_name}_node_group_{idx+1}"
            node_group_resource = {
                "cluster_name": f"${{aws_eks_cluster.{cluster_resource_name}.name}}",
                "node_group_name": node_pool.get("name"),
                "node_role_arn": f"${{aws_iam_role.{node_role_name}.arn}}",
                "subnet_ids": subnet_ids,
                "scaling_config": {
                    "desired_size": node_pool.get("desired_size", 2),
                    "max_size": node_pool.get("max_size", 5),
                    "min_size": node_pool.get("min_size", 1),
                },
                "instance_types": [node_pool.get("instance_type", "t3.medium")],
                "tags": self._merge_tags(k8s_attrs.get("tags", {}), service.name),
            }

            tf_config.resources.setdefault("aws_eks_node_group", {})[node_group_name] = node_group_resource

        # Handle dependencies
        if component.depends_on:
            cluster_resource["depends_on"] = component.depends_on

    def _process_deployment(self, service: Service, tf_config: TerraformConfig):
        print(f"Processing deployment for service: {service.name}")

        deployment_info = service.deployment

        if not isinstance(deployment_info, dict):
            print(f"Unexpected deployment_info type: {type(deployment_info)}. Skipping deployment processing.")
            return

        mappings = deployment_info.get("mappings", {})
        pattern = deployment_info.get("pattern", {})

        print(f"Deployment mappings: {mappings}")
        print(f"Deployment pattern: {pattern}")

        # Handle mappings
        for source, target in mappings.items():
            # Existing mapping handling code...
            pass  # Placeholder for your existing mapping logic

        # Handle pattern
        if isinstance(pattern, list):
            if len(pattern) > 0 and isinstance(pattern[0], dict):
                pattern = pattern[0]
                print(f"Extracted first pattern dict from list for service '{service.name}'.")
            else:
                print(f"Unexpected pattern list structure for service '{service.name}'. Skipping pattern handling.")
                pattern = {}
        elif not isinstance(pattern, dict):
            print(f"Unexpected pattern type for service '{service.name}': {type(pattern)}. Skipping pattern handling.")
            pattern = {}

        resources_pattern = pattern.get("resources", "")
        condition = pattern.get("condition", "")
        apply = pattern.get("apply", "")

        # Implement pattern-based application as needed
        print(f"Pattern-based application not implemented. Resources pattern: {resources_pattern}, Condition: {condition}, Apply: {apply}")
    
    def _add_service_outputs(self, service: 'Service', tf_config: TerraformConfig):
        print(f"Adding outputs for service: {service.name}")

        for component in service.infrastructure:
            if component.resource_type:
                output_name = f"{service.name}_{component.name}_id"
                tf_config.outputs[output_name] = {
                    "value": f"${{{component.resource_type}.{component.name}.id}}",
                    "description": f"ID of {component.name} in service {service.name}"
                }

    def _get_resource_type(self, component: InfrastructureComponent, provider: str) -> Optional[str]:
        return self.resource_type_mapping.get(component.component_type, {}).get(provider)

    def _merge_tags(self, resource_tags: Dict[str, str], service_name: str) -> Dict[str, str]:
        """Merge common tags with resource-specific tags."""
        base_tags = {
            "Name": f"{service_name.replace('_', '-')}",
            "Service": service_name.replace("_", "-")
        }
        if resource_tags:
            base_tags.update(resource_tags)
        return base_tags

    def _resolve_reference(self, reference: str) -> str:
        """Resolve references in the custom syntax to Terraform references."""
        if not reference:
            return ""

        parts = reference.split(".")
        skip_parts = {"infrastructure", "configuration", "containers", "app"}

        # Remove any grouping parts
        parts = [part for part in parts if part not in skip_parts]

        if len(parts) < 2:
            print(f"Invalid reference format: '{reference}'. Expected at least two parts after removing grouping parts.")
            return ""

        component_type = parts[0]
        component_name = parts[1]
        attribute_path = parts[2:]  # Remaining parts of the reference

        # Handle special cases like 'public_subnets'
        if component_type == "network" and attribute_path:
            if attribute_path[0].startswith("public_subnets"):
                # Reference to public_subnets local variable
                index = attribute_path[0][len("public_subnets"):]
                terraform_ref = f"local.{component_name}_public_subnets{index}"
            else:
                terraform_ref = f"aws_vpc.{component_name}." + ".".join(attribute_path)
        else:
            terraform_resource_type = self.resource_type_mapping.get(component_type, {}).get("aws")
            if not terraform_resource_type:
                print(f"Unknown component type in reference: '{component_type}'. Reference: '{reference}'")
                return ""

            terraform_ref = f"{terraform_resource_type}.{component_name}"
            for part in attribute_path:
                terraform_ref += f".{part}"

        return f"${{{terraform_ref}}}"

    def _to_json(self, tf_config: TerraformConfig) -> str:
        """Convert the TerraformConfig dataclass to JSON format."""
        config_dict = {}

        # Terraform block with required providers
        config_dict["terraform"] = {
            "required_providers": {
                provider: {"source": f"hashicorp/{provider}"}
                for provider in tf_config.providers.keys()
            }
        }

        if tf_config.backend:
            config_dict["terraform"]["backend"] = self._convert_references(tf_config.backend)

        # Providers
        if tf_config.providers:
            config_dict["provider"] = self._convert_references(tf_config.providers)

        # Variables
        if tf_config.variables:
            config_dict["variable"] = self._convert_references(tf_config.variables)

        # Locals
        if tf_config.locals:
            config_dict["locals"] = self._convert_references(tf_config.locals)

        # Resources
        if tf_config.resources:
            config_dict["resource"] = self._convert_references(tf_config.resources)

        # Data Sources
        if tf_config.data_sources:
            config_dict["data"] = self._convert_references(tf_config.data_sources)

        # Modules
        if tf_config.modules:
            config_dict["module"] = self._convert_references(tf_config.modules)

        # Outputs
        if tf_config.outputs:
            config_dict["output"] = {
                k: {
                    "value": v["value"],
                    "description": v.get("description", "")
                } for k, v in tf_config.outputs.items()
            }

        return json.dumps(config_dict, indent=2)

    def _convert_references(self, obj: Any) -> Any:
        """Recursively convert references in the Terraform configuration."""
        if isinstance(obj, dict):
            new_obj = {}
            for k, v in obj.items():
                if k == "reference" and isinstance(v, str):
                    return f"${{{v}}}"
                else:
                    new_obj[k] = self._convert_references(v)
            return new_obj
        elif isinstance(obj, list):
            return [self._convert_references(item) for item in obj]
        else:
            return obj
        
    def _find_vpc_resource_name(self, service: Service) -> Optional[str]:
        for component in service.infrastructure:
            if component.component_type == "network":
                return f"{component.name}_vpc"
        print(f"No VPC component found for service '{service.name}'.")
        return None
    
    def _get_resource_address(self, reference: str) -> str:
        """Convert a custom reference into a Terraform resource address for depends_on."""
        if not reference:
            return ""
        
        parts = reference.split(".")
        skip_parts = {"infrastructure", "configuration", "containers", "app"}
        
        parts = [part for part in parts if part not in skip_parts]
        
        if len(parts) < 2:
            print(f"Invalid reference format for depends_on: '{reference}'. Expected at least two parts after removing grouping parts.")
            return ""
        
        component_type = parts[0]
        component_name = parts[1]
        
        terraform_resource_type = self.resource_type_mapping.get(component_type, {}).get("aws")
        if not terraform_resource_type:
            print(f"Unknown component type in reference: '{component_type}'. Reference: '{reference}'")
            return ""
        
        resource_address = f"{terraform_resource_type}.{component_name}"
        return resource_address