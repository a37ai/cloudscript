from .data_and_types import IaCGenerator, TerraformConfig, TerraformBlock, TerraformBlockType, Service, InfrastructureComponent
from typing import List, Dict, Any, Optional, Union
from enum import Enum
import json
import re
import fnmatch

class TerraformGenerator(IaCGenerator):
    PROVIDER_SOURCE_MAPPING = {
        'aws': 'hashicorp/aws',
        'google': 'hashicorp/google',
        'azure': 'hashicorp/azurerm',
        'oci': 'hashicorp/oci',
        'alicloud': 'hashicorp/alicloud',
        'kubernetes': 'hashicorp/kubernetes',
        'openstack': 'terraform-provider-openstack/openstack',
    }
    def __init__(self, providers: Dict[str, Dict[str, Any]]):
        self.providers = providers
        self.resource_addresses = {}

    def generate(self, services: List['Service']) -> str:
        tf_config = TerraformConfig()

        # First pass: Collect resource addresses
        for service in services:
            for component in service.infrastructure:
                resource_type = component.resource_type
                if not resource_type:
                    continue
                resource_address = f"{resource_type}.{component.name}"
                self.resource_addresses[component.name] = resource_address

        # Second pass: Process components and resolve references
        for service in services:
            print(f"Processing service: {service.name}")

            # Process workspace configuration
            if service.workspace:
                tf_config.workspace = service.workspace

            # Process backend configuration
            if service.backend:
                tf_config.backend = service.backend

            # Process infrastructure components
            for component in service.infrastructure:
                self._process_infrastructure_component(component, service, tf_config)

            # Process deployment dependencies and patterns
            if service.deployment:
                self._process_deployment(service, tf_config)

            # Add service-specific outputs
            self._add_service_outputs(service, tf_config)

        # Add providers with versions
        self._add_required_providers(tf_config, services)

        # Add variables with validations
        self._add_variables(tf_config, self._collect_variables(services))

        print("Resources before serialization:")
        print(json.dumps(tf_config.resources, indent=2))

        print("Locals before serialization:")
        print(json.dumps(tf_config.locals, indent=2))

        # Convert to Terraform JSON format
        return self._to_json(tf_config)

    def _add_required_providers(self, tf_config: TerraformConfig, services: List[Service]):
        required_providers = {}
        provider_configs = {}

        for provider_alias, provider_info in self.providers.items():
            provider_type = provider_info['type']
            provider_attrs = provider_info['config']
            source = self.PROVIDER_SOURCE_MAPPING.get(provider_type, f"hashicorp/{provider_type}")
            version = provider_info.get('version')
            required_providers[provider_type] = {"source": source}
            if version:
                required_providers[provider_type]["version"] = version

            # Remove 'source' and 'version' from provider attributes
            config = provider_attrs.copy()
            # Set alias if necessary
            if provider_alias != provider_type:
                config['alias'] = provider_alias
                provider_key = f"{provider_type}.{provider_alias}"
            else:
                provider_key = provider_type

            provider_configs[provider_key] = config

        tf_config.required_providers = required_providers
        tf_config.providers = provider_configs

    def _collect_variables(self, services: List['Service']) -> Dict[str, Any]:
        variables = {}
        for service in services:
            if service.configuration and service.configuration.variables:
                for var_name, var_attrs in service.configuration.variables.items():
                    variables[var_name] = var_attrs
        return variables

    def _add_variables(self, tf_config: TerraformConfig, variables: Dict[str, Any]):
        for var_name, var_attrs in variables.items():
            var_entry = {
                "type": var_attrs.get("type", "string"),
                "description": var_attrs.get("description", ""),
            }
            if "default" in var_attrs:
                var_entry["default"] = var_attrs["default"]
            if "validation" in var_attrs:
                var_entry["validation"] = var_attrs["validation"]
            tf_config.variables[var_name] = var_entry

    def _process_infrastructure_component(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig):
        # Determine the provider for the component
        provider = component.provider or service.provider
        component.provider = provider  # Ensure the component has the provider set

        # Use the resource_type specified in the component
        resource_type = component.resource_type
        if not resource_type:
            # If resource_type is not specified, we cannot proceed
            print(f"No resource_type specified for component '{component.name}'. Skipping.")
            return

        print(f"Processing component '{component.name}' with resource type '{resource_type}' and provider '{provider}'")

        # Handle data sources
        if component.data_source:
            self._process_data_source(component, service, tf_config, component.count, component.for_each, component.lifecycle, component.provisioners)
            return

        # Handle modules
        if component.module:
            self._process_module(component, service, tf_config, component.count, component.for_each, component.lifecycle, component.provisioners)
            return

        # Process the resource generically
        self._process_generic_component(component, service, tf_config)

    def _process_data_source(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig,
                             count: Optional[int], for_each: Optional[Union[List[Any], Dict[str, Any]]],
                             lifecycle: Optional[Dict[str, Any]], provisioners: Optional[List[Dict[str, Any]]]):
        print(f"Processing data source component: {component.name}")

        data_source_type = component.resource_type
        if not data_source_type:
            print(f"No data_source_type specified for data source '{component.name}'. Skipping.")
            return

        data_source_attrs = component.attributes.copy()

        # Handle dynamic blocks if any
        if "dynamic_blocks" in data_source_attrs:
            data_source_attrs["dynamic"] = data_source_attrs.pop("dynamic_blocks")

        # Handle count and for_each
        if count is not None:
            data_source_attrs["count"] = count
        if for_each is not None:
            data_source_attrs["for_each"] = for_each

        # Handle lifecycle and provisioners
        if lifecycle:
            data_source_attrs["lifecycle"] = lifecycle
        if provisioners:
            data_source_attrs["provisioner"] = provisioners

        tf_config.data_sources.setdefault(data_source_type, {})[component.name] = data_source_attrs

    def _process_module(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig,
                       count: Optional[int], for_each: Optional[Union[List[Any], Dict[str, Any]]],
                       lifecycle: Optional[Dict[str, Any]], provisioners: Optional[List[Dict[str, Any]]]):
        print(f"Processing module component: {component.name}")

        source = component.attributes.get("source")
        if not source:
            print(f"No source specified for module '{component.name}'. Skipping.")
            return

        module_attrs = component.attributes.copy()
        module_attrs.pop("source", None)

        # Handle dynamic blocks if any
        if "dynamic_blocks" in module_attrs:
            module_attrs["dynamic"] = module_attrs.pop("dynamic_blocks")

        # Handle count and for_each
        if count is not None:
            module_attrs["count"] = count
        if for_each is not None:
            module_attrs["for_each"] = for_each

        # Handle lifecycle and provisioners
        if lifecycle:
            module_attrs["lifecycle"] = lifecycle
        if provisioners:
            module_attrs["provisioner"] = provisioners

        tf_config.modules[component.name] = {
            "source": source,
            **module_attrs
        }

    def _process_network(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig,
                        count: Optional[int], for_each: Optional[Union[List[Any], Dict[str, Any]]],
                        lifecycle: Optional[Dict[str, Any]], provisioners: Optional[List[Dict[str, Any]]]):
        """
        Processes a network component in a provider-agnostic manner by utilizing the resource_type,
        provider, and attributes specified in the HCL input.

        Args:
            component (InfrastructureComponent): The network component to process.
            service (Service): The service to which this component belongs.
            tf_config (TerraformConfig): The Terraform configuration being built.
            count (Optional[int]): Terraform count meta-argument.
            for_each (Optional[Union[List[Any], Dict[str, Any]]]): Terraform for_each meta-argument.
            lifecycle (Optional[Dict[str, Any]]): Terraform lifecycle meta-argument.
            provisioners (Optional[List[Dict[str, Any]]]): Terraform provisioners.
        """
        print(f"Processing network component: {component.name} with provider: {component.provider}")

        provider = component.provider or service.provider
        if not provider:
            print(f"No provider specified for network component '{component.name}'. Skipping.")
            return

        resource_type = component.resource_type
        if not resource_type:
            print(f"No resource_type specified for network component '{component.name}'. Skipping.")
            return

        # Initialize the resource attributes from the component
        resource_attributes = component.attributes.copy()

        # Merge common tags with resource-specific tags
        if 'tags' in resource_attributes:
            resource_attributes['tags'] = self._merge_tags(resource_attributes.get("tags", {}), service.name)

        # Handle Terraform meta-arguments
        if count is not None:
            resource_attributes['count'] = count
        if for_each is not None:
            resource_attributes['for_each'] = for_each
        if lifecycle:
            resource_attributes['lifecycle'] = lifecycle
        if provisioners:
            resource_attributes['provisioner'] = provisioners

        # Handle provider specification
        if component.provider:
            provider_info = self.providers.get(component.provider)
            if provider_info:
                provider_type = provider_info['type']
                provider_alias = provider_info.get('alias', provider_type)
                if provider_alias != provider_type:
                    resource_attributes['provider'] = f"{provider_type}.{provider_alias}"
                else:
                    resource_attributes['provider'] = provider_type
            else:
                print(f"Provider '{component.provider}' not found for component '{component.name}'. Skipping.")
                return
        else:
            if len(self.providers) > 1:
                print(f"Component '{component.name}' must specify a provider since multiple providers are defined.")
                return
            # If only one provider is defined, it will be implicitly used

        # Add the resource to the Terraform configuration
        tf_config.resources.setdefault(resource_type, {})[component.name] = resource_attributes

        # Optionally handle outputs or additional configurations if needed
        # For example, you might want to add an output for the network's ID
        tf_config.outputs.setdefault(f"{service.name}_{component.name}_id", {
            "value": f"${{{resource_type}.{component.name}.id}}",
            "description": f"ID of {component.name} in service {service.name}"
        })

        print(f"Network component '{component.name}' processed successfully as '{resource_type}.{component.name}'.")

    def _process_compute(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig,
                        count: Optional[int], for_each: Optional[Union[List[Any], Dict[str, Any]]],
                        lifecycle: Optional[Dict[str, Any]], provisioners: Optional[List[Dict[str, Any]]]):
        print(f"Processing compute component: {component.name}")

        resource_type = component.resource_type
        compute_attrs = component.attributes

        # Get subnet_id and resolve reference
        subnet_id = compute_attrs.get("subnet_id") or compute_attrs.get("subnet")
        if subnet_id:
            subnet_id = self._resolve_reference(subnet_id)
        else:
            # Default to the first public subnet if not specified
            vpc_name = self._find_vpc_name(service)
            if vpc_name:
                subnet_id = f"${{local.{vpc_name}_public_subnets[0]}}"
            else:
                subnet_id = ""

        tf_resource = {
            "ami": compute_attrs.get("ami"),
            "instance_type": compute_attrs.get("instance_type", "t2.micro"),
            "subnet_id": subnet_id,
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
        self._create_security_group(component, service, tf_config, count, for_each, lifecycle, provisioners)
        tf_resource["vpc_security_group_ids"] = [f"${{aws_security_group.{security_group_name}.id}}"]

        # Handle dependencies
        if component.depends_on:
            tf_resource["depends_on"] = component.depends_on

        # Handle count and for_each
        if count is not None:
            tf_resource['count'] = count
        if for_each is not None:
            tf_resource['for_each'] = for_each

        # Handle lifecycle and provisioners
        if lifecycle:
            tf_resource['lifecycle'] = lifecycle
        if provisioners:
            tf_resource['provisioner'] = provisioners

        # Handle dynamic blocks
        if "dynamic_blocks" in component.attributes:
            for dynamic_block in component.attributes["dynamic_blocks"]:
                block_name = dynamic_block.get("name")
                iterator = dynamic_block.get("iterator", "item")
                content = dynamic_block.get("content", {})
                tf_resource[f"dynamic_{block_name}"] = {
                    "for_each": dynamic_block.get("for_each"),
                    "content": content
                }

        # Handle subnet reference fallback
        if "subnet" not in compute_attrs:
            # Default to the first public subnet if not specified
            vpc_name = self._find_vpc_name(service)
            if vpc_name:
                tf_resource["subnet_id"] = f"${{local.{vpc_name}_public_subnets[0]}}"
            else:
                tf_resource["subnet_id"] = ""

        tf_config.resources.setdefault(resource_type, {})[component.name] = tf_resource

    def _create_security_group(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig,
                               count: Optional[int], for_each: Optional[Union[List[Any], Dict[str, Any]]],
                               lifecycle: Optional[Dict[str, Any]], provisioners: Optional[List[Dict[str, Any]]]):
        print(f"Creating security group for component: {component.name}")

        security_group_name = f"{component.name}_sg"
        security_rules = component.attributes.get("security_rules", {})
        ingress_rules = security_rules.get("inbound", [])
        egress_rules = security_rules.get("outbound", [])

        tf_resource = {
            "name": security_group_name,
            "description": f"Security group for {service.name}",
            "vpc_id": f"${{aws_vpc.{self._find_vpc_name(service)}.id}}",
            "ingress": [],
            "egress": [],
            "tags": self._merge_tags({}, service.name)
        }

        # Add ingress rules
        for rule in ingress_rules:
            ingress_rule = {
                "from_port": rule.get("port"),
                "to_port": rule.get("port"),
                "protocol": rule.get("protocol"),
                "cidr_blocks": [rule.get("cidr")],
                "description": rule.get("description", "")
            }
            tf_resource["ingress"].append(ingress_rule)

        # Add egress rules
        for rule in egress_rules:
            egress_rule = {
                "from_port": rule.get("port"),
                "to_port": rule.get("port"),
                "protocol": rule.get("protocol"),
                "cidr_blocks": [rule.get("cidr")],
                "description": rule.get("description", "")
            }
            tf_resource["egress"].append(egress_rule)

        # Handle count and for_each
        if count is not None:
            tf_resource['count'] = count
        if for_each is not None:
            tf_resource['for_each'] = for_each

        # Handle lifecycle and provisioners
        if lifecycle:
            tf_resource['lifecycle'] = lifecycle
        if provisioners:
            tf_resource['provisioner'] = provisioners

        # Handle dynamic blocks
        if "dynamic_blocks" in component.attributes:
            for dynamic_block in component.attributes["dynamic_blocks"]:
                block_name = dynamic_block.get("name")
                iterator = dynamic_block.get("iterator", "item")
                content = dynamic_block.get("content", {})
                tf_resource[f"dynamic_{block_name}"] = {
                    "for_each": dynamic_block.get("for_each"),
                    "content": content
                }

        tf_config.resources.setdefault("aws_security_group", {})[security_group_name] = tf_resource

    def _process_kubernetes(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig,
                            count: Optional[int], for_each: Optional[Union[List[Any], Dict[str, Any]]],
                            lifecycle: Optional[Dict[str, Any]], provisioners: Optional[List[Dict[str, Any]]]):
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

        # Handle count and for_each
        if count is not None:
            cluster_role_resource['count'] = count
        if for_each is not None:
            cluster_role_resource['for_each'] = for_each

        # Handle lifecycle and provisioners
        if lifecycle:
            cluster_role_resource['lifecycle'] = lifecycle
        if provisioners:
            cluster_role_resource['provisioner'] = provisioners

        # Handle dynamic blocks
        if "dynamic_blocks" in component.attributes:
            for dynamic_block in component.attributes["dynamic_blocks"]:
                block_name = dynamic_block.get("name")
                iterator = dynamic_block.get("iterator", "item")
                content = dynamic_block.get("content", {})
                cluster_role_resource[f"dynamic_{block_name}"] = {
                    "for_each": dynamic_block.get("for_each"),
                    "content": content
                }

        tf_config.resources.setdefault("aws_iam_role", {})[cluster_role_name] = cluster_role_resource

        # Attach policies to the cluster role
        tf_config.resources.setdefault("aws_iam_role_policy_attachment", {})[f"{cluster_role_name}_policy"] = {
            "role": f"${{aws_iam_role.{cluster_role_name}.name}}",
            "policy_arn": "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
        }

        # Handle count and for_each for policy attachment
        if count is not None:
            tf_config.resources["aws_iam_role_policy_attachment"][f"{cluster_role_name}_policy"]['count'] = count
        if for_each is not None:
            tf_config.resources["aws_iam_role_policy_attachment"][f"{cluster_role_name}_policy"]['for_each'] = for_each

        # Handle lifecycle and provisioners for policy attachment
        if lifecycle:
            tf_config.resources["aws_iam_role_policy_attachment"][f"{cluster_role_name}_policy"]['lifecycle'] = lifecycle
        if provisioners:
            tf_config.resources["aws_iam_role_policy_attachment"][f"{cluster_role_name}_policy"]['provisioner'] = provisioners

        # Get subnet IDs from the VPC public subnets
        vpc_name = self._find_vpc_name(service)
        if vpc_name:
            subnet_ids = f"${{local.{vpc_name}_public_subnets}}"
        else:
            subnet_ids = ""

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

        # Handle count and for_each
        if count is not None:
            cluster_resource['count'] = count
        if for_each is not None:
            cluster_resource['for_each'] = for_each

        # Handle lifecycle and provisioners
        if lifecycle:
            cluster_resource['lifecycle'] = lifecycle
        if provisioners:
            cluster_resource['provisioner'] = provisioners

        # Handle dynamic blocks
        if "dynamic_blocks" in component.attributes:
            for dynamic_block in component.attributes["dynamic_blocks"]:
                block_name = dynamic_block.get("name")
                iterator = dynamic_block.get("iterator", "item")
                content = dynamic_block.get("content", {})
                cluster_resource[f"dynamic_{block_name}"] = {
                    "for_each": dynamic_block.get("for_each"),
                    "content": content
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

        # Handle count and for_each
        if count is not None:
            node_role_resource['count'] = count
        if for_each is not None:
            node_role_resource['for_each'] = for_each

        # Handle lifecycle and provisioners
        if lifecycle:
            node_role_resource['lifecycle'] = lifecycle
        if provisioners:
            node_role_resource['provisioner'] = provisioners

        # Handle dynamic blocks
        if "dynamic_blocks" in component.attributes:
            for dynamic_block in component.attributes["dynamic_blocks"]:
                block_name = dynamic_block.get("name")
                iterator = dynamic_block.get("iterator", "item")
                content = dynamic_block.get("content", {})
                node_role_resource[f"dynamic_{block_name}"] = {
                    "for_each": dynamic_block.get("for_each"),
                    "content": content
                }

        tf_config.resources.setdefault("aws_iam_role", {})[node_role_name] = node_role_resource

        # Attach policies to the node role
        node_policies = [
            ("AmazonEKSWorkerNodePolicy", f"{node_role_name}_policy1"),
            ("AmazonEC2ContainerRegistryReadOnly", f"{node_role_name}_policy2"),
            ("AmazonEKS_CNI_Policy", f"{node_role_name}_policy3")
        ]

        for policy_arn_suffix, attachment_key in node_policies:
            policy_arn = f"arn:aws:iam::aws:policy/{policy_arn_suffix}"
            tf_config.resources.setdefault("aws_iam_role_policy_attachment", {})[attachment_key] = {
                "role": f"${{aws_iam_role.{node_role_name}.name}}",
                "policy_arn": policy_arn
            }

            # Handle count and for_each for policy attachments
            if count is not None:
                tf_config.resources["aws_iam_role_policy_attachment"][attachment_key]['count'] = count
            if for_each is not None:
                tf_config.resources["aws_iam_role_policy_attachment"][attachment_key]['for_each'] = for_each

            # Handle lifecycle and provisioners for policy attachments
            if lifecycle:
                tf_config.resources["aws_iam_role_policy_attachment"][attachment_key]['lifecycle'] = lifecycle
            if provisioners:
                tf_config.resources["aws_iam_role_policy_attachment"][attachment_key]['provisioner'] = provisioners

        # Create Node Group resources
        node_pools = k8s_attrs.get("node_pools", [])
        for idx, node_pool in enumerate(node_pools):
            node_group_name = f"{cluster_resource_name}_node_group_{idx + 1}"
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

            # Handle count and for_each
            if count is not None:
                node_group_resource['count'] = count
            if for_each is not None:
                node_group_resource['for_each'] = for_each

            # Handle lifecycle and provisioners
            if lifecycle:
                node_group_resource['lifecycle'] = lifecycle
            if provisioners:
                node_group_resource['provisioner'] = provisioners

            # Handle dynamic blocks
            if "dynamic_blocks" in component.attributes:
                for dynamic_block in component.attributes["dynamic_blocks"]:
                    block_name = dynamic_block.get("name")
                    iterator = dynamic_block.get("iterator", "item")
                    content = dynamic_block.get("content", {})
                    node_group_resource[f"dynamic_{block_name}"] = {
                        "for_each": dynamic_block.get("for_each"),
                        "content": content
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
            source_parts = source.split(".")
            target_parts = target.split(".")

            # Assuming the source is a resource and the target is a configuration to apply
            # For example, apply configurations from 'configuration.server_setup.base' to 'compute.web_server'
            if len(source_parts) >= 2 and len(target_parts) >= 2:
                resource_type = source_parts[0]
                resource_name = source_parts[1]
                config_type = target_parts[0]
                config_name = target_parts[1]

                # Directly use the resource_type from the source
                resource = tf_config.resources.get(resource_type, {}).get(resource_name)
                if resource:
                    depends_on_resource = f"null_resource.{config_name}"
                    if "depends_on" in resource:
                        resource["depends_on"].append(depends_on_resource)
                    else:
                        resource["depends_on"] = [depends_on_resource]
                else:
                    print(f"Resource {resource_type}.{resource_name} not found in tf_config.")

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

        # Implement pattern-based application
        # For simplicity, we'll check if the resource matches the pattern and condition, then apply the configuration
        for resource_type, resources in tf_config.resources.items():
            for resource_name, resource_attrs in resources.items():
                if self._resource_matches_pattern(resource_type, resource_name, resources_pattern):
                    if self._resource_matches_condition(resource_attrs, condition):
                        # Apply the configuration
                        config_parts = apply.split(".")
                        if len(config_parts) >= 2:
                            config_type = config_parts[0]
                            config_name = config_parts[1]
                            # For now, we can add a depends_on or any other logic as needed
                            resource_attrs.setdefault("depends_on", []).append(f"null_resource.{config_name}")
                        else:
                            print(f"Invalid apply target: {apply}")

    def _add_service_outputs(self, service: 'Service', tf_config: TerraformConfig):
        print(f"Adding outputs for service: {service.name}")

        for component in service.infrastructure:
            if component.resource_type:
                output_name = f"{service.name}_{component.name}_id"
                tf_config.outputs[output_name] = {
                    "value": f"${{{component.resource_type}.{component.name}.id}}",
                    "description": f"ID of {component.name} in service {service.name}"
                }

    def _merge_tags(self, resource_tags: Dict[str, str], service_name: str) -> Dict[str, str]:
        """Return the resource tags as is."""
        return resource_tags

    def _resolve_reference(self, reference: str) -> str:
        """Resolve references in the custom syntax to Terraform references."""
        if not reference:
            return ""

        # If already a Terraform reference, return as is
        if reference.startswith("${") and reference.endswith("}"):
            return reference

        # Return the reference wrapped in ${}
        return f"${{{reference}}}"

    def _to_json(self, tf_config: TerraformConfig) -> str:
        """Convert the TerraformConfig dataclass to JSON format."""
        config_dict = {}

        # Terraform block with required providers
        config_dict["terraform"] = {
            "required_providers": tf_config.required_providers
        }

        if tf_config.backend:
            config_dict["terraform"]["backend"] = tf_config.backend

        if tf_config.workspace:
            config_dict["terraform"]["workspaces"] = {
                "name": tf_config.workspace
            }

        # Providers
        if tf_config.providers:
            config_dict["provider"] = tf_config.providers

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
                if isinstance(v, str) and v.startswith("${") and v.endswith("}"):
                    new_obj[k] = v  # Already a Terraform reference
                else:
                    new_obj[k] = self._convert_references(v)
            return new_obj
        elif isinstance(obj, list):
            return [self._convert_references(item) for item in obj]
        else:
            return obj

    def _find_vpc_name(self, service: Service) -> Optional[str]:
        for component in service.infrastructure:
            if component.component_type == "network":
                return component.name
        print(f"No VPC component found for service '{service.name}'.")
        return None

    def _resource_matches_pattern(self, resource_type: str, resource_name: str, pattern: str) -> bool:
        # Simple pattern matching implementation
        return fnmatch.fnmatch(f"{resource_type}.{resource_name}", pattern)

    def _resource_matches_condition(self, resource_attrs: Dict[str, Any], condition: str) -> bool:
        # Basic condition evaluation (you can expand this as needed)
        # For now, we'll just check if 'tags.Environment' matches a value
        if condition == "tags.Environment == 'production'":
            tags = resource_attrs.get("tags", {})
            return tags.get("Environment") == "production"
        return False

    def _get_resource_address(self, reference: str) -> str:
        """Convert a custom reference into a Terraform resource address for depends_on."""
        if not reference:
            return ""

        parts = reference.split(".")
        if len(parts) < 3:  # Should have at least infrastructure.type.name
            print(f"Invalid reference format for depends_on: '{reference}'. Expected at least three parts.")
            return ""

        # Get the resource type and name from our resource_addresses mapping
        component_name = parts[-1]
        if component_name in self.resource_addresses:
            return self.resource_addresses[component_name]
        
        print(f"Resource not found for reference: {reference}")
        return ""
    
    def _process_generic_component(self, component: InfrastructureComponent, service: Service, tf_config: TerraformConfig):
        print(f"Processing generic component: {component.name}")

        resource_type = component.resource_type
        if not resource_type:
            print(f"No resource_type specified for component '{component.name}'. Skipping.")
            return

        resource_attrs = component.attributes.copy()

        # Set the provider if necessary
        if component.provider:
            provider_info = self.providers.get(component.provider)
            if provider_info:
                provider_type = provider_info['type']
                provider_alias = provider_info.get('alias', provider_type)
                if provider_alias != provider_type:
                    resource_attrs['provider'] = f"{provider_type}.{provider_alias}"
                else:
                    resource_attrs['provider'] = provider_type
            else:
                print(f"Provider '{component.provider}' not found for component '{component.name}'.")
                return

        # Collect resource address mapping
        resource_address = f"{resource_type}.{component.name}"
        self.resource_addresses[component.name] = resource_address

        # Process resource attributes to resolve references
        resource_attrs = self._resolve_resource_references(resource_attrs)

        # Handle depends_on - convert to proper resource addresses
        if component.depends_on:
            resource_attrs['depends_on'] = [self._get_resource_address(dep) for dep in component.depends_on]

        tf_config.resources.setdefault(resource_type, {})[component.name] = resource_attrs


    def _resolve_resource_references(self, attributes: Any) -> Any:
        if isinstance(attributes, dict):
            new_attributes = {}
            for key, value in attributes.items():
                new_attributes[key] = self._resolve_resource_references(value)
            return new_attributes
        elif isinstance(attributes, list):
            return [self._resolve_resource_references(item) for item in attributes]
        elif isinstance(attributes, str):
            # Use regex to find and replace references
            pattern = re.compile(r'\${(infrastructure\.[^}]+)}|infrastructure\.[^\s]+')
            def replace_reference(match):
                ref = match.group(0)
                # Remove ${} if present
                if ref.startswith('${') and ref.endswith('}'):
                    ref = ref[2:-1]
                resolved_ref = self._resolve_custom_reference(ref)
                return resolved_ref
            new_value = pattern.sub(replace_reference, attributes)
            return new_value
        else:
            return attributes
        
    def _resolve_custom_reference(self, reference: str) -> str:
        """
        Resolve a custom reference like 'infrastructure.network.vpc.id' to a Terraform reference like '${aws_vpc.vpc.id}'
        """
        if not reference:
            return ""

        # Check if reference starts with 'infrastructure.'
        if reference.startswith("infrastructure."):
            parts = reference.split('.')
            if len(parts) >= 3:
                component_name = parts[2]
                attribute = '.'.join(parts[3:]) if len(parts) > 3 else 'id'
                resource_address = self.resource_addresses.get(component_name)
                if resource_address:
                    # Build the Terraform reference
                    return f"${{{resource_address}.{attribute}}}"
                else:
                    print(f"Component '{component_name}' not found in resource_addresses.")
                    return f"${{{reference}}}"  # Return as is, but wrapped in ${...}
            else:
                print(f"Invalid reference format: '{reference}'.")
                return f"${{{reference}}}"  # Return as is, but wrapped in ${...}
        else:
            # For now, return the reference as is, or wrap in ${...}
            return f"${{{reference}}}"

    def _handle_common_resource_attributes(self, component: InfrastructureComponent, resource_attrs: Dict[str, Any]):
        """Handle common resource attributes like count, for_each, lifecycle, provisioners, depends_on, and dynamic blocks."""
        # Handle count and for_each
        if component.count is not None:
            resource_attrs['count'] = component.count
        if component.for_each is not None:
            resource_attrs['for_each'] = component.for_each

        # Handle lifecycle and provisioners
        if component.lifecycle:
            resource_attrs['lifecycle'] = component.lifecycle
        if component.provisioners:
            resource_attrs['provisioner'] = component.provisioners

        # Handle depends_on
        if component.depends_on:
            resource_attrs['depends_on'] = [f"${{{self.resource_addresses.get(dep, dep)}}}" for dep in component.depends_on]

        # Handle dynamic blocks
        if "dynamic_blocks" in component.attributes:
            dynamic_blocks = component.attributes.pop("dynamic_blocks")
            for dynamic_block in dynamic_blocks:
                block_name = dynamic_block.get("name")
                content = dynamic_block.get("content", {})
                resource_attrs[f"dynamic {block_name}"] = {
                    "for_each": dynamic_block.get("for_each"),
                    "content": content
                }