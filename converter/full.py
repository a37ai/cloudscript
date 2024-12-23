from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
import hcl2
import yaml
import json
from abc import ABC, abstractmethod
import os
from enum import Enum
import re
import fnmatch

class TerraformBlockType(Enum):
    TERRAFORM = "terraform"
    PROVIDER = "provider"
    RESOURCE = "resource"
    DATA = "data"
    MODULE = "module"
    VARIABLE = "variable"
    OUTPUT = "output"
    LOCALS = "locals"

@dataclass
class TerraformBlock:
    block_type: TerraformBlockType
    labels: List[str]
    attributes: Dict[str, Any]
    blocks: List['TerraformBlock'] = field(default_factory=list)

@dataclass
class TerraformConfig:
    required_providers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    providers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    resources: Dict[str, Dict[str, Dict[str, Any]]] = field(default_factory=dict)
    data_sources: Dict[str, Dict[str, Dict[str, Any]]] = field(default_factory=dict)
    modules: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    variables: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    outputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    locals: Dict[str, Any] = field(default_factory=dict)
    backend: Optional[Dict[str, Any]] = None
    workspace: Optional[str] = None

@dataclass
class InfrastructureComponent:
    name: str
    component_type: str
    attributes: Dict[str, Any]
    provider: Optional[str] = None
    resource_type: Optional[str] = None
    count: Optional[int] = None
    for_each: Optional[Union[List[Any], Dict[str, Any]]] = None
    depends_on: List[str] = field(default_factory=list)
    lifecycle: Optional[Dict[str, Any]] = None
    provisioners: Optional[List[Dict[str, Any]]] = None
    package_manager: Optional[str] = None
    data_source: Optional[bool] = False
    module: Optional[bool] = False

@dataclass
class ContainerSpec:
    name: str
    image: str
    ports: List[Dict[str, Any]]
    environment: Dict[str, str] = field(default_factory=dict)
    replicas: int = 1
    type: str = "Deployment"
    
    command: Optional[List[str]] = None
    args: Optional[List[str]] = None
    working_dir: Optional[str] = None
    
    health_check: Optional[Dict[str, Any]] = None
    readiness_probe: Optional[Dict[str, Any]] = None
    liveness_probe: Optional[Dict[str, Any]] = None
    startup_probe: Optional[Dict[str, Any]] = None
    
    resources: Optional[Dict[str, Any]] = None
    volumes: Optional[List[Dict[str, Any]]] = None
    volume_mounts: Optional[List[Dict[str, Any]]] = None
    empty_dir_volumes: Optional[List[Dict[str, Any]]] = None
    host_path_volumes: Optional[List[Dict[str, Any]]] = None
    
    auto_scaling: Optional[Dict[str, Any]] = None
    namespace: Optional[str] = None
    service: Optional[Dict[str, Any]] = None
    node_selector: Optional[Dict[str, str]] = None
    
    config_maps: Optional[List[Dict[str, Any]]] = None
    secrets: Optional[List[Dict[str, Any]]] = None
    persistent_volume_claims: Optional[List[Dict[str, Any]]] = None
    ingress: Optional[Dict[str, Any]] = None
    network_policies: Optional[List[Dict[str, Any]]] = None
    service_account: Optional[str] = None
    init_containers: Optional[List[Dict[str, Any]]] = None
    
    pod_disruption_budget: Optional[Dict[str, Any]] = None
    pod_anti_affinity: Optional[Dict[str, Any]] = None
    pod_affinity: Optional[Dict[str, Any]] = None
    node_affinity: Optional[Dict[str, Any]] = None
    
    custom_resources: Optional[List[Dict[str, Any]]] = None
    pod_security_policy: Optional[Dict[str, Any]] = None
    vertical_pod_autoscaling: Optional[Dict[str, Any]] = None

    attributes: Dict[str, Any] = field(default_factory=dict)

class ConfigurationSpec:
    def __init__(self, name: str, packages: List[str], files: Dict[str, Any], 
                 services: Dict[str, Any], variables: Dict[str, Any], 
                 tasks: List[Dict[str, Any]], commands: List[Dict[str, Any]], 
                 verifications: List[Dict[str, Any]], blocks: List[Dict[str, Any]], 
                 handlers: List[Dict[str, Any]], include_vars: Optional[Dict[str, Any]],
                 task_order: List[str], configuration: List[Dict[str, Any]] = None):
        self.name = name
        self.packages = packages
        self.files = files
        self.services = services
        self.variables = variables
        self.tasks = tasks
        self.commands = commands
        self.verifications = verifications
        self.blocks = blocks
        self.handlers = handlers
        self.include_vars = include_vars
        self.task_order = task_order
        self.configuration = configuration or []

@dataclass
class Service:
    name: str
    deployment_order: List[str]  # Changed from order
    backend: Optional[Dict[str, Any]] = None
    workspace: Optional[str] = None
    infrastructure: List['InfrastructureComponent'] = field(default_factory=list)
    configuration: Optional['ConfigurationSpec'] = None
    containers: List['ContainerSpec'] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    deployment: Optional[Dict[str, Any]] = None
    provider: Optional[str] = None

@dataclass
class AnsibleTask:
    name: str
    module: str  # e.g., 'package', 'service', 'command'
    args: Dict[str, Any]
    when: Optional[str] = None
    tags: Optional[List[str]] = None
    delegate_to: Optional[str] = None
    run_once: Optional[bool] = None
    retries: Optional[int] = None
    delay: Optional[int] = None
    timeout: Optional[int] = None
    notify: Optional[List[str]] = None
    loop: Optional[List[Any]] = None
    register: Optional[str] = None
    failed_when: Optional[str] = None
    changed_when: Optional[str] = None
    environment: Optional[Dict[str, str]] = None

@dataclass
class AnsibleBlock:
    name: str
    tasks: List[AnsibleTask]
    rescue: Optional[List[AnsibleTask]] = None
    always: Optional[List[AnsibleTask]] = None
    when: Optional[str] = None
    tags: Optional[List[str]] = None

@dataclass
class AnsibleHandler:
    name: str
    module: str
    args: Dict[str, Any]
    listen: Optional[List[str]] = None

@dataclass
class AnsibleIncludeVars:
    file: str
    when: Optional[str] = None

@dataclass
class ResourceDefaults:
    """Container for resource-specific defaults"""
    api_version: str
    spec_defaults: Dict[str, Any]
    metadata_defaults: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata_defaults is None:
            self.metadata_defaults = {}

@dataclass
class TransformRule:
    """Rule for transforming a specific field"""
    path: str  # dot-notation path to field
    transformer: Callable[[Any], Any]
    condition: Optional[Callable[[Dict], bool]] = None

@dataclass
class ValidationRule:
    """Rule for validating a specific field"""
    path: str
    validator: Callable[[Any], bool]
    error_message: str
    condition: Optional[Callable[[Dict], bool]] = None

class IaCGenerator(ABC):
    @abstractmethod
    def generate(self, services: List[Service]) -> str:
        pass

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

class AnsibleGenerator(IaCGenerator):
    def generate(self, services: List[Service]) -> str:
        """
        Generates a single comprehensive Ansible playbook with tasks grouped in blocks.
        """
        playbook = []
        inventory = {'all': {'hosts': {}}}

        for service in services:
            play = self._create_play(service)
            if play['tasks'] or play.get('pre_tasks') or play.get('post_tasks'):
                playbook.append(play)

            # Update inventory
            self._update_inventory(service, inventory)

        self._remove_group_keys(playbook)

        # Write inventory file
        with open('IaCnew/inventory.yml', 'w') as f:
            yaml.dump(inventory, f, sort_keys=False)

        return yaml.dump(playbook, sort_keys=False)

    # def generate(self, services: List[Service]) -> str:
    #     """
    #     Generates a single comprehensive Ansible playbook with tasks grouped in blocks.
    #     Writes a hard-coded inventory.yml file.
    #     """
    #     playbook = []

    #     for service in services:
    #         play = self._create_play(service)
    #         if play['tasks'] or play.get('pre_tasks') or play.get('post_tasks'):
    #             playbook.append(play)

    #     self._remove_group_keys(playbook)

    #     # Write hardcoded inventory file
    #     hardcoded_inventory = {
    #         'all': {
    #             'children': {
    #                 'web_servers': {
    #                     'hosts': {
    #                         'web_server_hosts': {
    #                             'ansible_host': '{{ host_ip }}',
    #                             'ansible_ssh_common_args': '-o StrictHostKeyChecking=no',
    #                             'ansible_ssh_private_key_file': '{{ ssh_key_path }}',
    #                             'ansible_user': 'ubuntu'
    #                         }
    #                     }
    #                 }
    #             },
    #             'hosts': {}
    #         }
    #     }

    #     with open('IaC/inventory.yml', 'w') as f:
    #         yaml.dump(hardcoded_inventory, f, sort_keys=False)

    #     return yaml.dump(playbook, sort_keys=False)

    def _create_play(self, service: Service) -> Dict[str, Any]:
        """Creates a play for a service with tasks organized in blocks."""
        play = {
            'name': f"Configure {service.name}",
            'hosts': "{{ target_servers | default('all') }}",
            'become': True,
            'tasks': [],
            'handlers': [],
            'vars': {
                'target_web_servers': "web_servers",
                'target_db_servers': "db_servers"
            }
        }

        if service.configuration:
            # Merge with existing vars if any
            if service.configuration.variables:
                play['vars'].update(service.configuration.variables)

            tasks, handlers = self._process_configuration_tasks(service.configuration)
            ordered_tasks = self._order_tasks(tasks, service.configuration.task_order)
            play['tasks'].extend(ordered_tasks)
            play['handlers'].extend(handlers)

        return play
    
    def _order_tasks(self, tasks: List[Tuple[str, Dict[str, Any]]], task_order: List[str]) -> List[Dict[str, Any]]:
        grouped_tasks = {group: [] for group in task_order}
        other_tasks = []

        for group, task in tasks:
            if group in grouped_tasks:
                grouped_tasks[group].append(task)
            else:
                other_tasks.append(task)

        ordered_tasks = []
        for group in task_order:
            if grouped_tasks[group]:
                block = {
                    'name': f"{group.replace('_', ' ').capitalize()} tasks",
                    'block': grouped_tasks[group]
                }
                ordered_tasks.append(block)

        if other_tasks:
            block = {
                'name': 'Other tasks',
                'block': other_tasks
            }
            ordered_tasks.append(block)

        return ordered_tasks

    def _process_configuration_tasks(self, config: ConfigurationSpec) -> List[Tuple[str, Dict[str, Any]]]:
        """Process all tasks and retain their groups."""
        tasks = []
        handlers = []

        # Add package installation task
        if config.packages:
            package_task = {
                'name': 'Install required packages',
                'package': {
                    'name': '{{ item }}',
                    'state': 'present',
                    'update_cache': True
                },
                'loop': config.packages,
                'check_mode': False
            }
            tasks.append(('packages', package_task))

        # Process files
        for file_path, content in config.files.items():
            file_task = self._create_file_task(file_path, content)
            group = file_task.get('group', 'other')
            tasks.append((group, file_task))

            # Collect handlers if notify is present
            if 'notify' in file_task:
                for handler_name in file_task['notify']:
                    handler_task = {
                        'name': handler_name,
                        'service': {
                            'name': handler_name.split()[-1],
                            'state': 'restarted'
                        },
                        'listen': handler_name
                    }
                    handlers.append(handler_task)

        # Process services
        for service_name, actions in config.services.items():
            service_tasks = self._create_service_tasks(service_name, actions)
            for task in service_tasks:
                group = task.get('group', 'other')
                tasks.append((group, task))

        # Process tasks
        for task in config.tasks:
            processed_task = self._process_task(task)
            group = processed_task.get('group', 'other')
            tasks.append((group, processed_task))

        # Process verifications
        for verification in config.verifications:
            verify_tasks = self._create_verification_tasks(verification)
            for verify_task in verify_tasks:
                group = verify_task.get('group', 'other')
                tasks.append((group, verify_task))

        # Process commands
        for command in config.commands:
            command_task = self._create_command_task(command)
            group = command_task.get('group', 'other')
            tasks.append((group, command_task))

        # print(f"Adding task '{task['name']}' to group '{group}'")
        # tasks.append((group, task))
        return tasks, handlers
   
    def _process_block(self, block: Dict[str, Any]) -> Dict[str, Any]:
        """Process block structures properly."""
        processed_block = {
            'name': block['name']
        }
        
        if 'tasks' in block:
            processed_block['block'] = [self._process_task(task) for task in block['tasks']]
        
        if 'rescue' in block:
            processed_block['rescue'] = [self._process_task(task) for task in block['rescue']]
        
        if 'always' in block:
            processed_block['always'] = [self._process_task(task) for task in block['always']]
            
        return processed_block
    
    def _process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single task."""
        processed_task = {
            'name': task.get('name', 'Execute task')
        }

        # Handle module and args
        for key, value in task.items():
            if key != 'name':
                processed_task[key] = value

        return processed_task

    def _process_blocks(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process block structures with error handling."""
        processed_blocks = []
        
        for block in blocks:
            processed_block = {
                'name': block['name'],
                'block': [],
                'rescue': [],
                'always': []
            }

            # Process main tasks
            if 'tasks' in block:
                for task in block['tasks']:
                    processed_task = self._process_task(task)
                    # Add block-specific conditions for database tasks
                    if 'mysql' in str(task).lower():
                        processed_task['when'] = ["inventory_hostname in groups['db_servers']"]
                    processed_block['block'].append(processed_task)

            # Process rescue tasks
            if 'rescue' in block:
                for task in block['rescue']:
                    processed_task = self._process_task(task)
                    processed_block['rescue'].append(processed_task)

            # Process always tasks
            if 'always' in block:
                for task in block['always']:
                    processed_task = self._process_task(task)
                    processed_block['always'].append(processed_task)

            processed_blocks.append(processed_block)

        return processed_blocks

    def _process_handlers(self, handlers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process handlers with listen directives."""
        processed_handlers = []
        
        for handler in handlers:
            processed_handler = self._process_task(handler)
            if 'listen' in handler:
                processed_handler['listen'] = handler['listen']
            processed_handlers.append(processed_handler)

        return processed_handlers

    def _process_include_vars(self, include_vars: Dict[str, Any]) -> Dict[str, Any]:
        """Process dynamic variable inclusion."""
        return {
            'name': 'Include variables',
            'include_vars': include_vars['file'],
            'when': include_vars.get('when')
        }

    def _create_file_task(self, file_path: str, content: Any) -> Dict[str, Any]:
        """Create a file task without hard-coded values."""
        task = {
            'name': f'Create/modify {file_path}',
            'copy': {
                'dest': file_path
            }
        }
        if isinstance(content, dict):
            copy_params = task['copy']
            for key in ['content', 'template']:
                if key in content:
                    copy_params[key] = content[key]
            for param in ['mode', 'owner', 'group']:
                if param in content:
                    copy_params[param] = content[param]
            if 'notify' in content:
                task['notify'] = content['notify']
            if 'when' in content:
                task['when'] = content['when']
            if 'task_group' in content:
                task['group'] = content['task_group']
        else:
            task['copy']['content'] = str(content)
        return task

    def _create_service_tasks(self, service_name: str, actions: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Create Ansible service tasks based on the service actions defined in the HCL input.

        Args:
            service_name (str): The name of the service to configure.
            actions (Dict[str, Any]): A dictionary containing actions and attributes for the service.

        Returns:
            List[Dict[str, Any]]: A list of Ansible task dictionaries.
        """
        tasks = []

        # Extract the task group for grouping tasks in Ansible playbook
        group = actions.get('task_group', 'other')

        # Extract any conditional 'when' statements
        when = actions.get('when')

        # Extract the 'state' list which defines desired states for the service
        state_list = actions.get('state', [])

        # Normalize state_list to be a list
        if isinstance(state_list, str):
            state_list = [state_list]
        elif not isinstance(state_list, list):
            state_list = []

        # Handle 'enabled' and 'disabled' states separately
        enabled = None
        if 'enabled' in state_list:
            enabled = 'yes'
            state_list.remove('enabled')
        elif 'disabled' in state_list:
            enabled = 'no'
            state_list.remove('disabled')

        # Create tasks for each state in state_list
        for state in state_list:
            register_name = f"{service_name}_{state}_result"
            task = {
                'name': f"Ensure {service_name} is {state}",
                'service': {
                    'name': service_name,
                    'state': state
                },
                'register': register_name,
                'retries': 3,
                'delay': 5,
                'failed_when': f"{register_name} is failed",
                'changed_when': f"{register_name} is changed",
            }

            # Add 'enabled' parameter if applicable
            if enabled is not None:
                task['service']['enabled'] = enabled

            # Add 'when' condition if specified
            if when:
                task['when'] = when

            # Assign the group for task ordering
            task['group'] = group

            # Append the task to the tasks list
            tasks.append(task)

        # If only 'enabled' or 'disabled' is specified without any state
        if enabled is not None and not state_list:
            register_name = f"{service_name}_enabled_result"
            task = {
                'name': f"Ensure {service_name} is {'enabled' if enabled == 'yes' else 'disabled'}",
                'service': {
                    'name': service_name,
                    'enabled': enabled
                },
                'register': register_name,
                'retries': 3,
                'delay': 5,
                'failed_when': f"{register_name} is failed",
                'changed_when': f"{register_name} is changed",
            }

            # Add 'when' condition if specified
            if when:
                task['when'] = when

            # Assign the group for task ordering
            task['group'] = group

            # Append the task to the tasks list
            tasks.append(task)

        return tasks

    def _create_command_task(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Create a command task with better error handling."""
        task = {
            'name': command.get('name', 'Run command'),
            'command': command['command'],
            'register': 'command_result',
            'changed_when': command.get('changed_when', False),  # Most commands don't change state
            'failed_when': command.get('failed_when', 'command_result.rc != 0'),
            'ignore_errors': command.get('ignore_errors', False)
        }
        
        if 'environment' in command:
            task['environment'] = command['environment']
        if 'when' in command:
            task['when'] = command['when']
        if 'retries' in command:
            task.update({
                'retries': command['retries'],
                'delay': command.get('delay', 5),
                'until': command.get('until', 'command_result.rc == 0')
            })
        
        return task

    def _create_verification_tasks(self, verification: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Create verification tasks."""
        tasks = []
        name = verification.get('name', 'Verify something').replace('Check ', '')

        # Determine register_name
        if 'register' in verification:
            register_name = verification['register']
        else:
            # Try to extract variable name from 'until' condition
            until = verification.get('until', '')
            # Simple parsing to extract variable name before '.'
            if until:
                until_variable = until.split('.')[0]
                register_name = until_variable
            else:
                # Default register name
                register_name = f"{name.lower().replace(' ', '_').replace('-', '_').replace('.', '_')}_result"

        module_name = verification.get('module', 'command')
        module_params = {}
        # Exclude keys that are not module parameters
        exclude_keys = ['name', 'module', 'retries', 'delay', 'until', 'group', 'failed_when', 'changed_when', 'register']
        for key, value in verification.items():
            if key not in exclude_keys:
                module_params[key] = value

        verification_task = {
            'name': f"Verify {name}",
            module_name: module_params,
            'register': register_name,
            'failed_when': verification.get('failed_when'),
            'changed_when': verification.get('changed_when', False),
            'retries': verification.get('retries', 1),
            'delay': verification.get('delay', 5),
            'until': verification.get('until'),
        }

        # Remove None values from the task
        verification_task = {k: v for k, v in verification_task.items() if v is not None}

        # Assign group
        group = verification.get('group', 'other')
        verification_task['group'] = group

        tasks.append(verification_task)
        return tasks

    def _update_inventory(self, service: Service, inventory: Dict[str, Any]):
        """Update inventory with service hosts and proper grouping."""
        if 'children' not in inventory['all']:
            inventory['all']['children'] = {}

        for component in service.infrastructure:
            if component.component_type == "compute":
                host_group = f"{component.name}_hosts"
                
                # Determine server type and create appropriate group
                server_type = 'web_servers' if 'web' in component.name else 'db_servers'
                if server_type not in inventory['all']['children']:
                    inventory['all']['children'][server_type] = {'hosts': {}}
                
                # Add host to appropriate group
                inventory['all']['children'][server_type]['hosts'][host_group] = {
                    'ansible_host': component.attributes.get('public_ip', '127.0.0.1'),
                    'ansible_user': component.attributes.get('ssh_user', 'ubuntu'),
                    'ansible_ssh_private_key_file': component.attributes.get('ssh_key_file', ''),
                    'ansible_ssh_common_args': '-o StrictHostKeyChecking=no'
                }

    def _create_retried_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create a task with retry logic and consistent register names."""
        register_name = f"{task['name'].lower().replace(' ', '_')}_result"
        
        processed_task = {
            'name': task['name'],
            'command': task['command'],
            'register': register_name
        }
        
        if 'retries' in task:
            processed_task.update({
                'retries': task['retries'],
                'delay': task.get('delay', 5),
                'until': f"{register_name} is success"
            })
        
        # Add other task attributes
        for key in ['when', 'delegate_to', 'run_once', 'environment']:
            if key in task:
                processed_task[key] = task[key]
                
        return processed_task
    
    def _create_mysql_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Create MySQL-related tasks with proper conditions."""
        processed_task = {
            'name': task['name'],
            'mysql_db': task.get('mysql_db', {}),
            'when': "inventory_hostname in groups['db_servers']"
        }
        
        if 'state' in task.get('mysql_db', {}):
            if task['mysql_db']['state'] == 'dump':
                processed_task['delegate_to'] = task.get('delegate_to', 'localhost')
                processed_task['register'] = 'mysql_backup_result'
                processed_task['failed_when'] = 'mysql_backup_result.failed'
        
        return processed_task
    
    def _remove_group_keys(self, playbook: List[Dict[str, Any]]) -> None:
        """Recursively remove 'group' keys from tasks in the playbook."""
        for play in playbook:
            self._remove_group_keys_from_tasks(play.get('tasks', []))
            self._remove_group_keys_from_tasks(play.get('pre_tasks', []))
            self._remove_group_keys_from_tasks(play.get('post_tasks', []))
            self._remove_group_keys_from_tasks(play.get('handlers', []))

    def _remove_group_keys_from_tasks(self, tasks: List[Dict[str, Any]]) -> None:
        """Helper function to remove 'group' keys from a list of tasks."""
        for task in tasks:
            if 'group' in task:
                del task['group']
            # Recursively remove 'group' from nested tasks in blocks
            if 'block' in task:
                self._remove_group_keys_from_tasks(task['block'])
            if 'rescue' in task:
                self._remove_group_keys_from_tasks(task['rescue'])
            if 'always' in task:
                self._remove_group_keys_from_tasks(task['always'])

class NewAnsibleGenerator(IaCGenerator):
    def generate(self, services: List[Any]) -> str:
        playbook = []
        print("Starting playbook generation...")

        for service_index, service in enumerate(services):
            print(f"\nProcessing service {service_index + 1}/{len(services)}: {service}")
            
            if not service.configuration:
                print("  - No configuration found for this service. Skipping.")
                continue

            config_data = getattr(service.configuration, 'configuration', [])
            print(f"  - Retrieved configuration data: {config_data}")
            
            if not config_data:
                print("  - Configuration data is empty. Skipping.")
                continue

            for config_block_index, config_block in enumerate(config_data):
                print(f"  - Processing config block {config_block_index + 1}/{len(config_data)}: {config_block}")
                
                if 'play' not in config_block:
                    print("    - 'play' key not found in config block. Skipping.")
                    continue

                for play_block_index, play_block in enumerate(config_block['play']):
                    print(f"    - Processing play block {play_block_index + 1}/{len(config_block['play'])}: {play_block}")
                    
                    for play_id, play_config in play_block.items():
                        print(f"      - Processing play '{play_id}': {play_config}")
                        
                        play = self._process_play(play_config)
                        if play:
                            print(f"        - Generated play: {play}")
                            playbook.append(play)
                        else:
                            print("        - Play processing returned None. Skipping.")

        print("\nPlaybook generation completed.")
        self._format_file_references(playbook)
        print("Generated playbook structure:")
        print(yaml.dump(playbook, sort_keys=False, indent=2, default_flow_style=False))

        playbook_yaml = yaml.dump(playbook, sort_keys=False, indent=2, default_flow_style=False)

        inventory_generator = InventoryFromPlaybook()
        inventory = inventory_generator.generate_inventory(playbook)

        with open('IaC/inventory.yml', 'w') as f:
            yaml.dump(inventory, f, sort_keys=False)
        
        return playbook_yaml

    def _process_play(self, play_config: Dict[str, Any]) -> Dict[str, Any]:
        print(f"    Processing play configuration: {play_config}")
        
        play = {
            'name': play_config.get('name', 'Unnamed play'),
            'hosts': play_config.get('hosts', 'all'),
            'become': play_config.get('become', False)
        }
        print(f"      - Initialized play with name='{play['name']}', hosts='{play['hosts']}', become={play['become']}")

        # Process vars
        if 'vars' in play_config:
            play['vars'] = play_config['vars']
            print(f"      - Added vars: {play['vars']}")

        # Process tasks sections
        tasks = []
        for section in ['pre_task', 'task', 'post_task']:
            print(f"      - Processing section: {section}")
            section_tasks = self._process_tasks_section(play_config.get(section, []))
            print(f"        - Tasks in section '{section}': {section_tasks}")
            if section_tasks:
                if section == 'task':
                    tasks.extend(section_tasks)
                    print(f"        - Extended 'tasks' with section '{section}' tasks.")
                else:
                    play[f'{section}s'] = section_tasks
                    print(f"        - Added '{section}s' to play: {section_tasks}")

        # Process handlers
        handlers = self._process_handlers(play_config.get('handler', []))
        print(f"      - Processed handlers: {handlers}")
        if handlers:
            play['handlers'] = handlers
            print("        - Added handlers to play.")

        if tasks:
            play['tasks'] = tasks
            print("        - Added tasks to play.")

        print(f"      - Final play structure: {play}")
        return play

    def _process_tasks_section(self, tasks_config: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print(f"        Processing tasks section: {tasks_config}")
        processed_tasks = []
        for task_index, task_dict in enumerate(tasks_config):
            print(f"          - Processing task {task_index + 1}/{len(tasks_config)}: {task_dict}")
            
            if 'block' in task_dict:
                print("            - Task contains a 'block'. Processing block.")
                block = self._process_block(task_dict)
                if block:
                    print(f"              - Processed block: {block}")
                    processed_tasks.append(block)
                else:
                    print("              - Block processing returned None. Skipping.")
            else:
                print("            - Task does not contain a 'block'. Processing single task.")
                task = self._process_task(task_dict)
                if task:
                    print(f"              - Processed task: {task}")
                    processed_tasks.append(task)
                else:
                    print("              - Task processing returned None. Skipping.")
        print(f"        Completed processing tasks section. Processed tasks: {processed_tasks}")
        return processed_tasks

    def _process_task(self, task_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        print(f"              Processing single task: {task_config}")
        
        if not task_config:
            print("                - Empty task configuration. Returning None.")
            return None

        task = {'name': task_config.get('name', 'Unnamed task')}
        print(f"                - Initialized task with name='{task['name']}'")

        # Process module and parameters
        for key, value in task_config.items():
            if key not in ['name', 'when', 'register', 'notify', 'ignore_errors', 
                          'changed_when', 'failed_when', 'retries', 'delay', 'loop']:
                print(f"                - Processing module/key: {key} with value: {value}")
                # Handle cases where the module is represented as a list
                if isinstance(value, list):
                    if len(value) == 1 and isinstance(value[0], dict):
                        task[key] = value[0]
                        print(f"                  - Assigned module '{key}' as a single dictionary.")
                    else:
                        task[key] = value
                        print(f"                  - Assigned module '{key}' as a list.")
                else:
                    task[key] = value

        # Add task attributes
        for attr in ['when', 'register', 'notify', 'ignore_errors', 'changed_when', 
                     'failed_when', 'retries', 'delay', 'loop']:
            if attr in task_config:
                print(f"                - Adding attribute '{attr}' with value: {task_config[attr]}")
                task[attr] = task_config[attr]

        print(f"                - Final task structure: {task}")
        return task

    def _process_block(self, block_config: Dict[str, Any]) -> Dict[str, Any]:
        print(f"              Processing block: {block_config}")
        
        block = {'name': block_config.get('name', 'Unnamed block')}
        print(f"                - Initialized block with name='{block['name']}'")

        # Correctly process 'block' within the block
        if 'block' in block_config:
            print("                - Processing 'block' within the block.")
            # Assuming block_config['block'] is a list of dicts with 'task' keys
            tasks_in_block = []
            for blk in block_config['block']:
                if 'task' in blk:
                    print(f"                  - Extracting tasks from: {blk['task']}")
                    tasks_in_block.extend(blk['task'])
            print(f"                - Extracted tasks from 'block': {tasks_in_block}")
            block['block'] = self._process_tasks_section(tasks_in_block)
            print(f"                - Added 'block' to block: {block['block']}")

        # Process rescue and always sections if present
        for section in ['rescue', 'always']:
            if section in block_config:
                print(f"                - Processing section '{section}' within the block.")
                section_tasks = self._process_tasks_section(block_config[section])
                block[section] = section_tasks
                print(f"                - Added '{section}' to block: {section_tasks}")

        print(f"                - Final block structure: {block}")
        return block

    def _process_handlers(self, handlers_config: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        print(f"      - Processing handlers: {handlers_config}")
        processed_handlers = []
        for handler_index, handler_dict in enumerate(handlers_config):
            print(f"        - Processing handler {handler_index + 1}/{len(handlers_config)}: {handler_dict}")
            
            handler = self._process_task(handler_dict)
            if handler:
                print(f"          - Processed handler: {handler}")
                # Add 'listen' key without removing the 'name'
                handler['listen'] = handler['name']
                print(f"            - Added 'listen': {handler['listen']}")
                processed_handlers.append(handler)
            else:
                print("          - Handler processing returned None. Skipping.")
        
        print(f"      - Completed processing handlers. Processed handlers: {processed_handlers}")
        return processed_handlers
    
    def _format_file_references(self, data):
        """Recursively format file() references in the playbook."""
        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str) and "file(" in value:
                    # Replace file("something") with "${file(\"something\")}"
                    file_match = re.search(r'file\("([^"]+)"\)', value)
                    if file_match:
                        # Format without extra quotes - YAML dumper will add the outer quotes
                        data[key] = '${file("nginx.conf")}'
                else:
                    self._format_file_references(value)
        elif isinstance(data, list):
            for item in data:
                self._format_file_references(item)

class InventoryFromPlaybook:
    def generate_inventory(self, playbook: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate inventory structure based on playbook analysis"""
        inventory = {
            'all': {
                'hosts': {},
                'children': {}
            }
        }
        groups = set()
        # Analyze playbook to find all group references
        for play in playbook:
            self._analyze_play(play, groups)
            
        # Create the groups and add default host configurations
        for group in groups:
            if 'web' in group.lower():
                inventory['all']['children'][group] = {
                    'hosts': {
                        f"{group.lower().replace('_servers', '')}_server_hosts": {
                            'ansible_host': '{{ host_ip }}',
                            'ansible_user': 'ubuntu',
                            'ansible_ssh_common_args': '-o StrictHostKeyChecking=no',
                            'ansible_ssh_private_key_file': '{{ ssh_key_path }}'
                        }
                    }
                }
        return inventory

    def _analyze_play(self, play: Dict[str, Any], groups: set):
        """Analyze a play for group references"""
        # Check vars for group references
        for var_name, var_value in play.get('vars', {}).items():
            if 'servers' in var_name:
                group = var_value if isinstance(var_value, str) else str(var_value)
                groups.add(group)

        # Check tasks for group references
        for task in play.get('tasks', []):
            if isinstance(task, dict):
                when_condition = task.get('when', '')
                if isinstance(when_condition, str) and 'groups[' in when_condition:
                    group = self._extract_group_from_condition(when_condition)
                    if group:
                        groups.add(group)

    def _extract_group_from_condition(self, condition: str) -> Optional[str]:
        """Extract group name from a when condition"""
        if "groups['" in condition:
            start = condition.find("groups['") + 8
            end = condition.find("']", start)
            if start > 7 and end != -1:
                return condition[start:end]
        return None

    def _extract_group_name(self, condition: str) -> Optional[str]:
        """Extract group name from conditions like 'inventory_hostname in groups['web_servers']'"""
        if 'groups[' in condition:
            start = condition.find("groups['") + 7
            end = condition.find("']", start)
            if start > 6 and end > start:
                return condition[start:end]
        return None

    def _extract_group_from_var(self, var_name: str) -> Optional[str]:
        """Extract group name from variable names like 'target_web_servers'"""
        if 'servers' in var_name:
            parts = var_name.split('_')
            if len(parts) >= 2:
                return f"{parts[-2]}_{parts[-1]}"
        return None

    def _ensure_group_exists(self, inventory: Dict[str, Any], group_name: str):
        """Ensure a group exists in the inventory structure"""
        if group_name not in inventory['all']['children']:
            inventory['all']['children'][group_name] = {
                'hosts': {}
            }

    def assign_hosts_to_groups(self, inventory: Dict[str, Any], host_mappings: Dict[str, Dict[str, str]]):
        """Assign actual hosts to the discovered groups"""
        for group_name, hosts in host_mappings.items():
            if group_name in inventory['all']['children']:
                inventory['all']['children'][group_name]['hosts'].update(hosts)

class DynamicProcessor:
    """Handles dynamic processing of unknown resource types"""
    
    def __init__(self):
        self._transform_registry: Dict[str, List[TransformRule]] = {}
        self._validation_registry: Dict[str, List[ValidationRule]] = {}
        self._defaults_registry: Dict[str, ResourceDefaults] = {}
        
    def process_resource(self, resource_type: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Process a resource dynamically"""
        # Get defaults or use empty defaults
        defaults = self._defaults_registry.get(resource_type, ResourceDefaults(
            api_version="apps/v1",
            spec_defaults={},
            metadata_defaults={}
        ))
        
        name = spec.get("name", "").replace("_", "-")
        
        # Robust namespace defaulting
        namespace = spec.get("namespace")
        if not namespace:
            namespace = "default"
        
        # Create basic resource structure
        resource = {
            "apiVersion": defaults.api_version,
            "kind": resource_type,
            "metadata": {
                "name": name,
                "namespace": namespace,
                **defaults.metadata_defaults
            },
            "spec": {**defaults.spec_defaults}
        }
        
        # Transform spec
        transformed_spec = self._transform_spec(resource_type, spec)
        resource["spec"].update(transformed_spec)
        
        return resource
    
    def _transform_spec(self, resource_type: str, spec: Dict[str, Any]) -> Dict[str, Any]:
        """Transform a spec according to registered rules"""
        transformed = {}

        for key, value in spec.items():
            if key in ["name", "namespace", "type"]:
                continue  # Skip these as they are handled separately

            camel_key = self._to_camel_case(key)

            if isinstance(value, dict):
                # Recursively transform nested dictionaries
                transformed[camel_key] = self._transform_spec(resource_type, value)
            elif isinstance(value, list):
                # Recursively transform lists
                transformed[camel_key] = [self._transform_spec(resource_type, item) if isinstance(item, dict) else item for item in value]
            else:
                # Directly assign scalar values
                transformed[camel_key] = value

        return transformed
    
    def _apply_transform(self, target: Dict[str, Any], path: List[str], 
                        transformer: Callable, spec: Dict[str, Any]):
        """Apply a transformation to a specific path in the spec"""
        current = target
        for part in path[:-1]:
            if part not in current:
                current[part] = {}
            current = current[part]
        
        value = self._get_nested_value(spec, path)
        if value is not None:
            current[path[-1]] = transformer(value)
    
    def _get_nested_value(self, d: Dict[str, Any], path: List[str]) -> Any:
        """Get a value from a nested dictionary using a path"""
        current = d
        for part in path:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current
    
    @staticmethod
    def _to_camel_case(snake_str: str) -> str:
        """Convert snake_case to camelCase"""
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])
    
    @staticmethod
    def _transform_value(value: Any) -> Any:
        """Transform a value recursively"""
        if isinstance(value, dict):
            return {DynamicProcessor._to_camel_case(k): DynamicProcessor._transform_value(v) 
                    for k, v in value.items()}
        elif isinstance(value, list):
            return [DynamicProcessor._transform_value(item) for item in value]
        return value

    def register_defaults(self, resource_type: str, defaults: ResourceDefaults):
        """Register defaults for a resource type"""
        self._defaults_registry[resource_type] = defaults

class KubernetesGenerator(IaCGenerator):
    def __init__(self):
        self.dynamic_processor = DynamicProcessor()

    def generate(self, services: List[Service]) -> str:
        """Generate Kubernetes manifests."""
        print("\nStarting Kubernetes manifest generation...")
        k8s_resources = []
        
        # Define known resource types that have explicit handlers
        KNOWN_RESOURCE_TYPES = {
            "Deployment": self._create_deployment,
            "StatefulSet": self._create_statefulset,
            "CronJob": self._create_cronjob,
            "DaemonSet": self._create_daemonset,
            "Job": self._create_job,
            "Service": self._create_service,
            "Ingress": self._create_ingress,
            "NetworkPolicy": self._create_network_policy,
            "HorizontalPodAutoscaler": self._create_horizontal_pod_autoscaler,
            "VerticalPodAutoscaler": self._create_vertical_pod_autoscaler,
            "PodDisruptionBudget": self._create_pod_disruption_budget,
            "ConfigMap": self._create_config_map,
            "Secret": self._create_secret,
            "ServiceAccount": self._create_service_account,
            "Namespace": self._create_namespace
        }
        
        for service in services:
            if not service.containers:
                continue

            for container in service.containers:
                # Check if we have an explicit handler for this resource type
                if container.type in KNOWN_RESOURCE_TYPES:
                    workload = KNOWN_RESOURCE_TYPES[container.type](container)
                else:
                    # Extract container-specific fields
                    container_spec = {
                        "name": container.name.replace("_", "-"),
                        "image": container.image,
                    }
                    
                    if hasattr(container, 'command'):
                        container_spec["command"] = container.command
                    if hasattr(container, 'args'):
                        container_spec["args"] = container.args
                    if hasattr(container, 'working_dir'):
                        container_spec["workingDir"] = container.working_dir
                    if hasattr(container, 'ports'):
                        container_spec["ports"] = [
                            {"containerPort": p["container_port"]}
                            for p in container.ports
                        ]
                    if hasattr(container, 'resources'):
                        container_spec["resources"] = container.resources
                    if hasattr(container, 'volume_mounts'):
                        container_spec["volumeMounts"] = container.volume_mounts
                    if hasattr(container, 'readiness_probe'):
                        container_spec["readinessProbe"] = container.readiness_probe
                    
                    # Remove None values
                    container_spec = {k: v for k, v in container_spec.items() if v is not None}
                    
                    # Create pod template spec
                    pod_template_spec = self._create_pod_template_spec(container)
                    
                    # Build container_dict without container-specific fields
                    container_dict = {
                        "name": container.name.replace("_", "-"),
                        "type": container.type,
                        "replicas": container.replicas,
                        "template": {
                            "metadata": {
                                "labels": {
                                    "app": container.name.replace("_", "-")
                                }
                            },
                            "spec": pod_template_spec
                        },
                        "namespace": container.namespace or "default"
                    }
                    
                    # Assign the containers within the pod template spec
                    container_dict["template"]["spec"]["containers"] = [container_spec]
                    
                    # Process the resource dynamically
                    workload = self.dynamic_processor.process_resource(
                        container.type,
                        container_dict
                    )
                
                k8s_resources.append(workload)

                if container.service:
                    service = self._create_service(container)
                    k8s_resources.append(service)

                if container.auto_scaling:
                    hpa = self._create_horizontal_pod_autoscaler(container)
                    k8s_resources.append(hpa)

                if container.pod_disruption_budget:
                    pdb = self._create_pod_disruption_budget(container)
                    k8s_resources.append(pdb)

        return yaml.dump_all(k8s_resources, explicit_start=True)

    def _create_workload_resource(self, container: ContainerSpec) -> Dict:
        """Create the appropriate workload resource."""
        name = container.name.replace("_", "-")
        
        workload = {
            "apiVersion": "apps/v1",
            "kind": container.type,
            "metadata": {
                "name": name,
                "namespace": "default"
            },
            "spec": {
                "replicas": container.replicas,
                "selector": {
                    "matchLabels": {
                        "app": name
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": name
                        }
                    },
                    "spec": self._create_pod_template_spec(container)
                }
            }
        }

        # Add volumeClaimTemplates for StatefulSet
        if container.type == "StatefulSet" and container.persistent_volume_claims:
            workload["spec"]["volumeClaimTemplates"] = [
                {
                    "metadata": {
                        "name": pvc["name"]
                    },
                    "spec": {
                        "accessModes": pvc["access_modes"],
                        "storageClassName": pvc.get("storage_class", "standard"),
                        "resources": {
                            "requests": {
                                "storage": pvc["storage"]
                            }
                        }
                    }
                }
                for pvc in container.persistent_volume_claims
            ]

        return workload
    
    def _create_pod_template_spec(self, container: ContainerSpec) -> Dict:
        """Create a pod template spec that can be reused across different workload types."""
        print(f"\nCreating pod template spec for container: {container.name}")
        
        container_spec = {
            "name": container.name.replace("_", "-"),
            "image": container.image,
        }

        # Add optional container configurations
        if container.command:
            container_spec["command"] = container.command
        if container.args:
            container_spec["args"] = container.args
        if container.working_dir:
            container_spec["workingDir"] = container.working_dir

        # Add ports
        if container.ports:
            container_spec["ports"] = [{"containerPort": port["container_port"]} for port in container.ports]

        # Add probes
        if container.readiness_probe:
            container_spec["readinessProbe"] = self._convert_probe(container.readiness_probe)
        if container.liveness_probe:
            container_spec["livenessProbe"] = self._convert_probe(container.liveness_probe)
        if container.startup_probe:
            container_spec["startupProbe"] = self._convert_probe(container.startup_probe)

        # Add resources
        if container.resources:
            container_spec["resources"] = container.resources

        # Add volume mounts
        if container.volume_mounts:
            container_spec["volumeMounts"] = container.volume_mounts

        # Create pod spec
        pod_spec = {
            "containers": [container_spec]
        }

        # Add init containers
        if container.init_containers:
            pod_spec["initContainers"] = container.init_containers

        # Add node selector
        if container.node_selector:
            pod_spec["nodeSelector"] = container.node_selector

        # Add pod anti affinity
        if container.pod_anti_affinity:
            pod_spec["affinity"] = {
                "podAntiAffinity": container.pod_anti_affinity
            }

        # Add volumes
        volumes = []
        
        # Add emptyDir volumes
        if container.empty_dir_volumes:
            volumes.extend([
                {
                    "name": vol["name"],
                    "emptyDir": {"sizeLimit": vol["size_limit"]} if "size_limit" in vol else {}
                }
                for vol in container.empty_dir_volumes
            ])

        # Add hostPath volumes
        if container.host_path_volumes:
            volumes.extend([
                {
                    "name": vol["name"],
                    "hostPath": {
                        "path": vol["path"],
                        "type": vol.get("type")
                    }
                }
                for vol in container.host_path_volumes
            ])

        if volumes:
            pod_spec["volumes"] = volumes

        return pod_spec
    
    def _convert_probe(self, probe: Dict) -> Dict:
        """Convert probe configuration to Kubernetes format."""
        converted = {}
        
        if "http_get" in probe:
            converted["httpGet"] = {
                "path": probe["http_get"]["path"],
                "port": probe["http_get"]["port"]
            }
        elif "tcp_socket" in probe:
            converted["tcpSocket"] = {
                "port": probe["tcp_socket"]["port"]
            }

        # Convert snake_case to camelCase
        for k, v in probe.items():
            if k not in ["http_get", "tcp_socket"]:
                converted[self._to_camel_case(k)] = v

        return converted
    
    def _create_deployment(self, container: ContainerSpec) -> Dict:
        """Create a Deployment resource."""
        name = container.name.replace("_", "-")
        
        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": name,
                "namespace": container.namespace or "default"
            },
            "spec": {
                "replicas": container.replicas,
                "selector": {
                    "matchLabels": {
                        "app": name
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": name
                        }
                    },
                    "spec": self._create_pod_template_spec(container)
                }
            }
        }

        return deployment

    def _create_statefulset(self, container: ContainerSpec) -> Dict:
        """Create a StatefulSet resource."""
        name = container.name.replace("_", "-")
        
        statefulset = {
            "apiVersion": "apps/v1",
            "kind": "StatefulSet",
            "metadata": {
                "name": name,
                "namespace": container.namespace or "default"
            },
            "spec": {
                "serviceName": name,
                "replicas": container.replicas,
                "selector": {
                    "matchLabels": {
                        "app": name
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": name
                        }
                    },
                    "spec": self._create_pod_template_spec(container)
                }
            }
        }

        if container.persistent_volume_claims:
            statefulset["spec"]["volumeClaimTemplates"] = container.persistent_volume_claims

        return statefulset

    def _create_service(self, container: ContainerSpec) -> Dict:
        """Create Service resource."""
        print("\nDEBUG: Service Creation")
        print(f"Container name: {container.name}")
        print(f"Container ports: {container.ports}")
        print(f"Container service config: {container.service}")
        
        name = container.name.replace("_", "-")
        
        service = {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": {
                "name": name,
                "namespace": container.namespace or "default"
            }
        }

        if container.service:
            # Handle case where service is a list
            service_config = container.service[0] if isinstance(container.service, list) else container.service
            print(f"Service config after processing: {service_config}")
            
            if "annotations" in service_config:
                service["metadata"]["annotations"] = service_config["annotations"]
            
            # Process ports from container.ports
            ports = []
            if container.ports:
                print("Processing container ports:")
                for port in container.ports:
                    print(f"Processing port: {port}")
                    port_config = {
                        "port": port.get("service_port", port.get("container_port")),
                        "targetPort": port.get("container_port"),
                        "protocol": port.get("protocol", "TCP")
                    }
                    print(f"Created port config: {port_config}")
                    ports.append(port_config)
            
            service["spec"] = {
                "selector": {"app": name},
                "ports": ports,
                "type": service_config.get("type", "ClusterIP")
            }
            
            print(f"Final service configuration: {json.dumps(service, indent=2)}")

        return service

    def _create_ingress(self, container: ContainerSpec) -> Dict:
        """Create an Ingress resource."""
        name = container.name.replace("_", "-")
        
        ingress = {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "Ingress",
            "metadata": {
                "name": f"{name}-ingress",
                "namespace": container.namespace or "default"
            },
            "spec": container.ingress
        }

        return ingress

    def _create_network_policy(self, container: ContainerSpec, policy: Dict) -> Dict:
        """Create a NetworkPolicy resource."""
        return {
            "apiVersion": "networking.k8s.io/v1",
            "kind": "NetworkPolicy",
            "metadata": {
                "name": f"{container.name}-network-policy",
                "namespace": container.namespace or "default"
            },
            "spec": policy
        }

    def _create_horizontal_pod_autoscaler(self, container: ContainerSpec) -> Dict:
        """Create HorizontalPodAutoscaler resource."""
        name = container.name.replace("_", "-")
        
        # Handle case where auto_scaling is a list
        auto_scaling_config = container.auto_scaling[0] if isinstance(container.auto_scaling, list) else container.auto_scaling
        
        return {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": f"{name}-hpa",
                "namespace": container.namespace or "default"
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": container.type,
                    "name": name
                },
                "minReplicas": auto_scaling_config.get("min_replicas", 1),
                "maxReplicas": auto_scaling_config.get("max_replicas", 10),
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": auto_scaling_config.get("target_cpu_utilization_percentage", 80)
                            }
                        }
                    }
                ]
            }
        }

    def _create_vertical_pod_autoscaler(self, container: ContainerSpec) -> Dict:
        """Create a VerticalPodAutoscaler resource."""
        name = container.name.replace("_", "-")
        
        return {
            "apiVersion": "autoscaling.k8s.io/v1",
            "kind": "VerticalPodAutoscaler",
            "metadata": {
                "name": f"{name}-vpa",
                "namespace": container.namespace or "default"
            },
            "spec": container.vertical_pod_autoscaling
        }

    def _create_pod_disruption_budget(self, container: ContainerSpec) -> Dict:
        """Create PodDisruptionBudget resource."""
        name = container.name.replace("_", "-")
        
        return {
            "apiVersion": "policy/v1",
            "kind": "PodDisruptionBudget",
            "metadata": {
                "name": f"{name}-pdb",
                "namespace": container.namespace or "default"
            },
            "spec": {
                "selector": {
                    "matchLabels": {
                        "app": name
                    }
                },
                **container.pod_disruption_budget
            }
        }

    def _create_cronjob(self, container: ContainerSpec) -> Dict:
        """Create a CronJob resource."""
        name = container.name.replace("_", "-")
        
        cronjob = {
            "apiVersion": "batch/v1",
            "kind": "CronJob",
            "metadata": {
                "name": name,
                "namespace": container.namespace or "default"
            },
            "spec": {
                "schedule": container.attributes.get("schedule", "* * * * *"),  # Get schedule from attributes
                "jobTemplate": {
                    "spec": {
                        "template": {
                            "metadata": {
                                "labels": {
                                    "app": name
                                }
                            },
                            "spec": {
                                **self._create_pod_template_spec(container),
                                "restartPolicy": container.attributes.get("restartPolicy", "OnFailure")
                            }
                        }
                    }
                }
            }
        }
        
        return cronjob

    def _create_daemonset(self, container: ContainerSpec) -> Dict:
        """Create a DaemonSet resource."""
        name = container.name.replace("_", "-")
        
        return {
            "apiVersion": "apps/v1",
            "kind": "DaemonSet",
            "metadata": {
                "name": name,
                "namespace": container.namespace or "default"
            },
            "spec": {
                "selector": {
                    "matchLabels": {
                        "app": name
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": name
                        }
                    },
                    "spec": self._create_pod_template_spec(container)
                }
            }
        }
    def _create_job(self, container: ContainerSpec) -> Dict:
        """Create a Job resource."""
        name = container.name.replace("_", "-")
        
        return {
            "apiVersion": "batch/v1",
            "kind": "Job",
            "metadata": {
                "name": name,
                "namespace": container.namespace or "default"
            },
            "spec": {
                "template": {
                    "metadata": {
                        "labels": {
                            "app": name
                        }
                    },
                    "spec": self._create_pod_template_spec(container)
                },
                "backoffLimit": container.attributes.get("backoff_limit", 6),
                "completions": container.attributes.get("completions", 1),
                "parallelism": container.attributes.get("parallelism", 1)
            }
        }

    def _create_config_map(self, container: ContainerSpec) -> Dict:
        """Create a ConfigMap resource."""
        name = container.name.replace("_", "-")
        
        return {
            "apiVersion": "v1",
            "kind": "ConfigMap",
            "metadata": {
                "name": name,
                "namespace": container.namespace or "default"
            },
            "data": container.attributes.get("data", {})
        }

    def _create_secret(self, secret: Dict[str, Any], container: ContainerSpec) -> Dict:
        """Create a Secret resource."""
        return {
            "apiVersion": "v1",
            "kind": "Secret",
            "metadata": {
                "name": secret["name"],
                "namespace": container.namespace or "default"
            },
            "type": secret.get("type", "Opaque"),
            "data": secret.get("data", {}),
            "stringData": secret.get("string_data", {})
        }

    def _create_service_account(self, container: ContainerSpec) -> Dict:
        """Create a ServiceAccount resource."""
        return {
            "apiVersion": "v1",
            "kind": "ServiceAccount",
            "metadata": {
                "name": container.service_account,
                "namespace": container.namespace or "default"
            }
        }

    def _create_namespace(self, namespace: str) -> Dict:
        """Create a Namespace resource."""
        return {
            "apiVersion": "v1",
            "kind": "Namespace",
            "metadata": {
                "name": namespace
            }
        }
    
    def register_resource_defaults(self, resource_type: str, api_version: str, 
                                 spec_defaults: Dict[str, Any], 
                                 metadata_defaults: Dict[str, Any] = None):
        """Helper method to register new resource types"""
        self.dynamic_processor.register_defaults(
            resource_type,
            ResourceDefaults(
                api_version=api_version,
                spec_defaults=spec_defaults,
                metadata_defaults=metadata_defaults
            )
        )
    
    @staticmethod
    def _to_camel_case(snake_str: str) -> str:
        """Convert snake_case to camelCase."""
        components = snake_str.split('_')
        return components[0] + ''.join(x.title() for x in components[1:])

# Parsing Functions

def parse_universal_hcl(hcl_content: str) -> Tuple[List[Service], Dict[str, Dict[str, Any]]]:
    print("Parsing HCL content...")
    parsed_hcl = hcl2.loads(hcl_content)
    print("Parsed HCL:", json.dumps(parsed_hcl, indent=2))
    services: List[Service] = []
    providers = {}

    # Parse providers at the top level
    if 'providers' in parsed_hcl:
        provider_blocks = parsed_hcl['providers']
        if isinstance(provider_blocks, list):
            for provider_block in provider_blocks:
                if isinstance(provider_block, dict):
                    for provider_alias, provider_attrs in provider_block.items():
                        # Handle provider_attrs being a list
                        if isinstance(provider_attrs, list):
                            if len(provider_attrs) == 0:
                                print(f"No attributes found for provider '{provider_alias}'. Skipping.")
                                continue
                            provider_attrs = provider_attrs[0]  # Extract the first dict
                        elif not isinstance(provider_attrs, dict):
                            print(f"Unexpected type for provider '{provider_alias}': {type(provider_attrs)}. Skipping.")
                            continue

                        provider_type = provider_attrs.get('provider', provider_alias)
                        version = provider_attrs.get('version')
                        config = provider_attrs.copy()
                        config.pop('provider', None)
                        config.pop('version', None)
                        providers[provider_alias] = {
                            'type': provider_type,
                            'alias': provider_alias,
                            'version': version,
                            'config': config
                        }
        elif isinstance(provider_blocks, dict):
            for provider_alias, provider_attrs in provider_blocks.items():
                # Handle provider_attrs being a list
                if isinstance(provider_attrs, list):
                    if len(provider_attrs) == 0:
                        print(f"No attributes found for provider '{provider_alias}'. Skipping.")
                        continue
                    provider_attrs = provider_attrs[0]  # Extract the first dict
                elif not isinstance(provider_attrs, dict):
                    print(f"Unexpected type for provider '{provider_alias}': {type(provider_attrs)}. Skipping.")
                    continue

                provider_type = provider_attrs.get('provider', provider_alias)
                version = provider_attrs.get('version')
                config = provider_attrs.copy()
                config.pop('provider', None)
                config.pop('version', None)
                providers[provider_alias] = {
                    'type': provider_type,
                    'alias': provider_alias,
                    'version': version,
                    'config': config
                }

    # Determine default provider if only one is defined
    default_provider_name = None
    if len(providers) == 1:
        default_provider_name = list(providers.keys())[0]

    service_blocks = parsed_hcl.get("service", [])
    if not isinstance(service_blocks, list):
        service_blocks = [service_blocks]

    print(f"Found {len(service_blocks)} service blocks")

    for service_block in service_blocks:
        if not isinstance(service_block, dict):
            continue

        for service_name, service_content in service_block.items():
            print(f"\nProcessing service: {service_name}")

            # Extract provider and other configurations
            provider = service_content.get("provider", default_provider_name)
            deployment_order = service_content.get("deployment_order", [])  # Changed from order
            backend = service_content.get("backend", None)
            workspace = service_content.get("workspace", None)
            dependencies = service_content.get("dependencies", [])

            # Parse infrastructure
            infrastructure_components = []
            if infra_block := service_content.get("infrastructure"):
                print(f"Found infrastructure block for {service_name}:")
                if isinstance(infra_block, list):
                    for infra_item in infra_block:
                        process_infrastructure_block(infra_item, infrastructure_components, default_provider=default_provider_name)
                elif isinstance(infra_block, dict):
                    process_infrastructure_block(infra_block, infrastructure_components, default_provider=default_provider_name)
                else:
                    print(f"Unexpected infrastructure_block type: {type(infra_block)}")

            # Parse configuration
            configuration_spec = None
            if config_block := service_content.get("configuration"):
                print(f"Found configuration block for {service_name}:")
                configuration_spec = process_configuration_block(config_block)

            # Parse containers
            containers = []
            if containers_block := service_content.get("containers"):
                print(f"Found containers block for {service_name}:")
                if isinstance(containers_block, list):
                    for containers_item in containers_block:
                        containers.extend(process_containers_block(containers_item))
                elif isinstance(containers_block, dict):
                    containers.extend(process_containers_block(containers_block))
                else:
                    print(f"Unexpected containers_block type: {type(containers_block)}")
                for container in containers:
                    print(f"Added ContainerSpec: {container.name}")

            # Parse deployment
            deployment = service_content.get("deployment", {})
            if deployment:
                print(f"Found deployment block for {service_name}:")
                if isinstance(deployment, list):
                    if len(deployment) > 0 and isinstance(deployment[0], dict):
                        deployment = deployment[0]
                        print(f"Extracted deployment dict from list for {service_name}.")
                    else:
                        print(f"Unexpected deployment list structure for {service_name}. Skipping deployment handling.")
                        deployment = {}
                elif isinstance(deployment, dict):
                    pass  # Already a dict
                else:
                    print(f"Unexpected deployment type for {service_name}: {type(deployment)}. Skipping deployment handling.")
                    deployment = {}

            # Create the service object
            service = Service(
                name=service_name,
                provider=provider,
                backend=backend,
                workspace=workspace,
                deployment_order=deployment_order,
                infrastructure=infrastructure_components,
                configuration=configuration_spec,
                containers=containers,
                dependencies=dependencies,
                deployment=deployment if isinstance(deployment, dict) else None
            )
            services.append(service)
            print(f"Added Service: {service.name}")
            print(deployment)
            
            if isinstance(deployment, dict) and deployment!={}:
                mappings = deployment["mappings"]
            else:
                mappings = None

    return services, providers, mappings

def process_infrastructure_block(infra_block: Any, infrastructure_components: List[InfrastructureComponent], default_provider: Optional[str] = None):
    print("Processing infrastructure block...")
    if isinstance(infra_block, dict):
        for block_type, block_content in infra_block.items():
            if isinstance(block_content, dict):
                for component_name, component_content in block_content.items():
                    # Pass component_type to process_component
                    process_component(component_name, component_content, infrastructure_components, default_provider, component_type=block_type)
            elif isinstance(block_content, list):
                for item in block_content:
                    process_infrastructure_block({block_type: item}, infrastructure_components, default_provider)
            else:
                print(f"Unexpected block content type: {type(block_content)}")
    elif isinstance(infra_block, list):
        for item in infra_block:
            process_infrastructure_block(item, infrastructure_components, default_provider)
    else:
        print(f"Unexpected infra_block type: {type(infra_block)}")

def process_components(component_type: str, components: Any, infrastructure_components: List[InfrastructureComponent]):
    if isinstance(components, list):
        for component in components:
            if isinstance(component, dict):
                for component_name, component_content in component.items():
                    process_component(component_type, component_name, component_content, infrastructure_components)
    elif isinstance(components, dict):
        for component_name, component_content in components.items():
            process_component(component_type, component_name, component_content, infrastructure_components)

def process_component(component_name: str, component_content: Dict[str, Any],
                      infrastructure_components: List[InfrastructureComponent],
                      default_provider: Optional[str] = None, component_type: Optional[str] = None):
    print(f"Processing component: '{component_name}' of type '{component_type}'")

    attributes = component_content.copy()
    count = attributes.pop("count", None)
    for_each = attributes.pop("for_each", None)
    depends_on = attributes.pop("depends_on", [])
    lifecycle = attributes.pop("lifecycle", None)
    provisioners = attributes.pop("provisioners", None)
    provider = attributes.pop("provider", attributes.pop("providers", default_provider))
    resource_type = attributes.pop("resource_type", None)
    data_source = attributes.pop("data_source", False)
    module = attributes.pop("module", False)

    # Set component_type if not provided
    if not component_type:
        component_type = attributes.pop("component_type", None)

    # Infer package manager based on OS (optional)
    os_type = attributes.get("os", "").lower()
    if os_type in ["ubuntu", "debian"]:
        package_manager = "apt"
    elif os_type in ["amazon-linux", "centos", "redhat", "fedora"]:
        package_manager = "yum"
    else:
        package_manager = "apt"  # Default to apt if unknown

    infra_component = InfrastructureComponent(
        name=component_name,
        component_type=component_type,
        attributes=attributes,
        provider=provider,
        resource_type=resource_type,
        count=count,
        for_each=for_each,
        depends_on=depends_on,
        lifecycle=lifecycle,
        provisioners=provisioners,
        package_manager=package_manager,
        data_source=data_source,
        module=module
    )

    infrastructure_components.append(infra_component)
    print(f"Added component {infra_component.name} to infrastructure components")

def process_configuration_block(config_block: Any) -> ConfigurationSpec:
    """Process configuration block with nested structure."""
    print("Processing configuration block...")
    packages = []
    files = {}
    services = {}
    variables = {}
    tasks = []
    commands = []
    verifications = []
    blocks = []
    handlers = []
    include_vars = None
    config_name = ""
    task_order = []
    
    # Store raw configuration data if it's a list
    configuration = config_block if isinstance(config_block, list) else [config_block]

    # Process other configuration items if needed
    if isinstance(config_block, list):
        for config_item in config_block:
            if isinstance(config_item, dict):
                for setup_name, setup_content in config_item.items():
                    if setup_name != 'play' and isinstance(setup_content, list):
                        for setup_item in setup_content:
                            if isinstance(setup_item, dict):
                                for name, content in setup_item.items():
                                    config_name = name
                                    if isinstance(content, dict):
                                        # Extract configuration items
                                        packages.extend(content.get("packages", []))
                                        files.update(content.get("files", {}))
                                        services.update(content.get("services", {}))
                                        variables.update(content.get("variables", {}))
                                        tasks.extend(content.get("tasks", []))
                                        commands.extend(content.get("commands", []))
                                        verifications.extend(content.get("verifications", []))
                                        blocks.extend(content.get("blocks", []))
                                        handlers.extend(content.get("handlers", []))
                                        include_vars = content.get("include_vars")
                                        task_order = content.get("task_order", [])

    configuration_spec = ConfigurationSpec(
        name=config_name,
        packages=packages,
        files=files,
        services=services,
        variables=variables,
        tasks=tasks,
        commands=commands,
        verifications=verifications,
        blocks=blocks,
        handlers=handlers,
        include_vars=include_vars,
        task_order=task_order,
        configuration=configuration  # Pass raw configuration data
    )

    return configuration_spec

def process_containers_block(containers_block: Any) -> List[ContainerSpec]:
    print("\nProcessing containers block...")
    print(f"Container block content: {json.dumps(containers_block, indent=2)}")
    containers = []
    
    if isinstance(containers_block, dict):
        for container_type, container_configs in containers_block.items():
            print(f"Processing container type: {container_type}")
            process_container_configs(container_type, container_configs, containers)
    elif isinstance(containers_block, list):
        for container_item in containers_block:
            if isinstance(container_item, dict):
                print(f"Processing container item: {json.dumps(container_item, indent=2)}")
                for container_type, container_configs in container_item.items():
                    print(f"Processing container type from list: {container_type}")
                    process_container_configs(container_type, container_configs, containers)
    else:
        print(f"Unexpected containers_block type: {type(containers_block)}")
    
    print(f"Processed {len(containers)} containers")
    return containers

def process_container_configs(container_type: str, container_configs: Any, containers: List[ContainerSpec]):
    if isinstance(container_configs, list):
        for container in container_configs:
            if isinstance(container, dict):
                for container_name, container_content in container.items():
                    container_spec = create_container_spec(container_name, container_content)
                    containers.append(container_spec)
    elif isinstance(container_configs, dict):
        for container_name, container_content in container_configs.items():
            container_spec = create_container_spec(container_name, container_content)
            containers.append(container_spec)

def create_container_spec(container_name: str, container_content: Dict[str, Any]) -> ContainerSpec:
    """Create a ContainerSpec from HCL content."""
    print(f"\nCreating ContainerSpec for container: {container_name}")
    print(f"Container content: {json.dumps(container_content, indent=2)}")

    # Handle ConfigMap type containers differently
    if container_content.get("data"):
        return ContainerSpec(
            name=container_name,
            image=None,  # ConfigMaps don't have images
            ports=[],
            environment={},
            replicas=1,
            type="ConfigMap",
            attributes={"data": container_content["data"]}
        )

    # For regular containers, verify required image field
    if "image" not in container_content:
        raise ValueError(f"Container {container_name} is missing required 'image' field")
    
    image = container_content["image"]

    # Debug ports handling
    print("\nDEBUG: Ports handling:")
    ports = container_content.get("ports", [])
    print(f"Initial ports: {ports}")

    # Handle service ports
    if "service" in container_content:
        print(f"Service config: {json.dumps(container_content['service'], indent=2)}")
        if isinstance(container_content["service"], dict):
            service_ports = container_content["service"].get("ports", [])
            print(f"Service ports: {service_ports}")
            if service_ports:
                ports = service_ports
        elif isinstance(container_content["service"], list) and container_content["service"]:
            service_config = container_content["service"][0]
            if isinstance(service_config, dict):
                service_ports = service_config.get("ports", [])
                print(f"Service ports from list: {service_ports}")
                if service_ports:
                    ports = service_ports

    print(f"Final ports configuration: {ports}")

    # Create attributes dictionary with all additional fields
    attributes = {}
    known_fields = {
        "image", "ports", "environment", "replicas", "type", "command",
        "args", "working_dir", "readiness_probe", "liveness_probe",
        "startup_probe", "resources", "volume_mounts", "empty_dir_volumes",
        "host_path_volumes", "service", "auto_scaling", "node_selector",
        "init_containers", "pod_disruption_budget", "pod_anti_affinity",
        "persistent_volume_claims", "data"
    }
    
    for key, value in container_content.items():
        if key not in known_fields:
            attributes[key] = value

    spec = ContainerSpec(
        name=container_name,
        image=image,
        ports=ports,
        environment=container_content.get("environment", {}),
        replicas=container_content.get("replicas", 1),
        type=container_content.get("type", "Deployment"),
        command=container_content.get("command"),
        args=container_content.get("args"),
        working_dir=container_content.get("working_dir"),
        readiness_probe=container_content.get("readiness_probe"),
        liveness_probe=container_content.get("liveness_probe"),
        startup_probe=container_content.get("startup_probe"),
        resources=container_content.get("resources"),
        volume_mounts=container_content.get("volume_mounts"),
        empty_dir_volumes=container_content.get("empty_dir_volumes"),
        host_path_volumes=container_content.get("host_path_volumes"),
        service=container_content.get("service"),
        auto_scaling=container_content.get("auto_scaling"),
        node_selector=container_content.get("node_selector"),
        init_containers=container_content.get("init_containers"),
        pod_disruption_budget=container_content.get("pod_disruption_budget"),
        pod_anti_affinity=container_content.get("pod_anti_affinity"),
        persistent_volume_claims=container_content.get("persistent_volume_claims"),
        attributes=attributes
    )

    print(f"Created ContainerSpec with ports: {spec.ports}")
    return spec

# Utility Functions

def ensure_directory():
    """Create IaC directory if it doesn't exist."""
    os.makedirs('IaC', exist_ok=True)

# Main Conversion Function

def main_convert(hcl_content: str):
    # Create IaC directory first
    ensure_directory()

    # Parse and generate
    services, providers, mapping = parse_universal_hcl(hcl_content)
    # Generate configurations
    tf_gen = TerraformGenerator(providers=providers)
    ansible_gen = NewAnsibleGenerator()
    k8s_gen = KubernetesGenerator()

    # Generate Terraform JSON
    tf_json = tf_gen.generate(services)
    ansible = ansible_gen.generate(services)
    k8s = k8s_gen.generate(services)
    print("TF JSON:\n")
    print(tf_json)
    print("Ansible playbook:\n")
    print(ansible)
    print("Kubernetes manifests:\n")
    print(k8s)

    # Write outputs to the IaC directory
    with open('IaC/main.tf.json', 'w') as f:
        f.write(tf_json)

    with open('IaC/playbook.yml', 'w') as f:
        f.write(ansible)

    with open('IaC/resources.yml', 'w') as f:
        f.write(k8s)
    
    if mapping:
        mapping = str(mapping).replace("'", '"')
        with open('IaC/mappings.json', 'w') as f:
            f.write(str(mapping))

    print("Conversion completed.")

example_hcl = """
providers {
    aws_primary {
        provider = "aws"
        region   = "us-west-2"
        version  = "~> 3.0"
    }
    googlemain {
        provider = "google"
        region   = "us-central1"
        version  = "~> 4.0"
    }
}

service "example_service" {
    infrastructure {
        network "main_network" {
            provider      = "aws_primary"
            resource_type = "aws_vpc"
            cidr_block    = "10.0.0.0/16"
            enable_dns_support    = true
            enable_dns_hostnames  = true
            tags = {
                Name        = "main-network"
                Environment = "production"
            }
        }

        network "public_subnet" {
            provider      = "aws_primary"
            resource_type = "aws_subnet"
            vpc_id        = "main_network"
            cidr_block    = "10.0.1.0/24"
            availability_zone = "us-west-2a"
            map_public_ip_on_launch = true
            tags = {
                Name        = "public-subnet"
                Environment = "production"
            }
        }

        compute "web_server" {
            provider      = "aws_primary"
            resource_type = "aws_instance"
            ami           = "ami-0abcdef1234567890"
            instance_type = "t2.micro"
            subnet_id     = "public_subnet"  # Reference to the subnet
            tags = {
                Name        = "web-server"
                Environment = "production"
            }
        }

        compute "gcp_vm" {
            provider       = "googlemain"
            resource_type  = "google_compute_instance"
            name           = "gcp-vm"
            machine_type   = "e2-medium"
            zone           = "us-central1-a"
            boot_disk = {
                initialize_params = {
                    image = "debian-cloud/debian-10"
                }
            }
            network_interface = {
                network        = "default"
                access_config  = {}
            }
            tags = {
                Name        = "gcp-vm"
                Environment = "production"
            }
        }
    }
}
"""

new = """
service "my_first_webapp" {
    provider = "aws"
    provider_version = "~> 4.0"
    backend = {
        s3 = {
            bucket = "my-terraform-state"
            key    = "state.tfstate"
            region = "us-west-2"
        }
    }
    workspace = "production"
    order = [
        "infrastructure.module.vpc_module",
        "infrastructure.network.main",
        "infrastructure.compute.web_server",
        "infrastructure.compute.latest_ami",
        "infrastructure.kubernetes.main_cluster",
        "configuration.server_setup.base",
        "containers.app.web_frontend"
    ]

    infrastructure {
        module "vpc_module" {
            module = true
            source = "terraform-aws-modules/vpc/aws"
            version = "3.5.0"

            name = "my_vpc"
            cidr = "10.0.0.0/16"

            azs             = ["us-west-2a", "us-west-2b", "us-west-2c"]
            public_subnets  = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
            private_subnets = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

            enable_nat_gateway = true

            depends_on = ["infrastructure.network.main"]
        }

        network "main" {
            region             = "us-west-2"
            availability_zones = ["us-west-2a", "us-west-2b"]
            vpc_cidr           = "10.0.0.0/16"
            subnet_cidrs       = ["10.0.1.0/24", "10.0.2.0/24"]
            enable_public_ip   = true

            dynamic_blocks = [
                {
                    name = "tags"
                    for_each = var.common_tags
                    content = {
                        key   = "tags.key"
                        value = "tags.value"
                    }
                }
            ]

            tags = {
                Name        = "main-network"
                Environment = "production"
                Project     = "FirstWebApp"
            }
        }

        compute "latest_ami" {
            data_source = true
            most_recent = true
            filter = [
                {
                    name   = "name"
                    values = ["amzn2-ami-hvm-*-x86_64-gp2"]
                },
                {
                    name   = "virtualization-type"
                    values = ["hvm"]
                }
            ]
            owners = ["amazon"]
        }

        compute "web_server" {
            ami                  = "${data.aws_ami.latest_ami.id}"
            instance_type        = var.instance_type
            subnet               = "infrastructure.network.main.public_subnets[0]"
            user_data            = "#!/bin/bash\nsudo apt-get update\nsudo apt-get install -y nginx"
            key_name             = "my-key-pair"
            iam_instance_profile = "web_server_role"
            associate_public_ip_address = true
            root_block_device = {
                volume_size           = 20
                volume_type           = "gp2"
                delete_on_termination = true
            }
            security_rules = {
                inbound = [
                    {
                        port        = 80
                        protocol    = "tcp"
                        cidr        = "0.0.0.0/0"
                        description = "Allow HTTP"
                    },
                    {
                        port        = 22
                        protocol    = "tcp"
                        cidr        = "0.0.0.0/0"
                        description = "Allow SSH"
                    }
                ]
                outbound = [
                    {
                        port        = 0
                        protocol    = "-1"
                        cidr        = "0.0.0.0/0"
                        description = "Allow all outbound traffic"
                    }
                ]
            }
            depends_on = ["infrastructure.network.main"]
            count = 2
            lifecycle = {
                create_before_destroy = true
                prevent_destroy = false
            }
            provisioners = [
                {
                    type = "file"
                    source = "scripts/setup.sh"
                    destination = "/tmp/setup.sh"
                },
                {
                    type = "remote-exec"
                    inline = [
                        "chmod +x /tmp/setup.sh",
                        "/tmp/setup.sh"
                    ]
                }
            ]
            tags = {
                Name        = "web-server"
                Environment = "production"
                Project     = "FirstWebApp"
            }
        }

        kubernetes "main_cluster" {
            name    = "my-first-cluster"
            version = "1.27"

            node_pools = [
                {
                    name          = "general"
                    instance_type = "t2.medium"
                    min_size      = 2
                    max_size      = 5
                    desired_size  = 2

                    labels = {
                        role = "worker"
                    }
                    taints = [
                        {
                            key    = "dedicated"
                            value  = "worker"
                            effect = "NoSchedule"
                        }
                    ]
                }
            ]

            tags = {
                Name        = "main-cluster"
                Environment = "production"
                Project     = "FirstWebApp"
            }

            depends_on = ["infrastructure.compute.web_server"]
        }
    }

    configuration {
        server_setup "base" {
            packages = ["docker", "kubectl", "awscli"]

            variables = {
                instance_type = {
                    type        = "string"
                    default     = "t2.micro"
                    description = "EC2 instance type"
                    validation = {
                        condition     = "contains(['t2.micro', 't2.small', 't2.medium'], var.instance_type)"
                        error_message = "The instance_type must be one of t2.micro, t2.small, or t2.medium."
                    }
                }
                common_tags = {
                    type = "map"
                    default = {
                        Environment = "production"
                        Project     = "FirstWebApp"
                    }
                }
            }

            commands = [
                {
                    name        = "Configure kubectl"
                    command     = "aws eks update-kubeconfig --name my-first-cluster --region us-west-2"
                    environment = {
                        AWS_DEFAULT_REGION = "us-west-2"
                    }
                }
            ]

            verifications = [
                {
                    name    = "Verify Docker version"
                    command = "docker --version"
                },
                {
                    name    = "Verify kubectl version"
                    command = "kubectl version --client"
                },
                {
                    name    = "Verify AWS version"
                    command = "aws --version"
                }
            ]

            tags = {
                Name        = "server-setup-base"
                Environment = "production"
                Project     = "FirstWebApp"
            }

            depends_on = ["infrastructure.kubernetes.main_cluster"]
        }
    }

    containers {
        app "web_frontend" {
            image    = "nginx:latest"
            replicas = 2
            ports = [
                {
                    container_port = 80
                    service_port   = 80
                }
            ]

            resources = {
                limits = {
                    cpu    = "500m"
                    memory = "512Mi"
                }
                requests = {
                    cpu    = "250m"
                    memory = "256Mi"
                }
            }

            health_check = {
                http_get = {
                    path = "/"
                    port = 80
                }
                initial_delay_seconds = 10
                period_seconds        = 15
            }

            env = {
                NGINX_HOST = "my-first-web-app.com"
                NGINX_PORT = "80"
            }

            service = {
                type        = "LoadBalancer"
                annotations = {
                    "service.beta.kubernetes.io/aws-load-balancer-type" = "nlb"
                }
            }

            tags = {
                Name        = "web-frontend"
                Environment = "production"
                Project     = "FirstWebApp"
            }

            depends_on = ["infrastructure.kubernetes.main_cluster"]
        }
    }

    deployment {
        mappings = {
            "compute.web_server"          = "configuration.server_setup.base"
            "containers.app.web_frontend" = "infrastructure.kubernetes.main_cluster"
        }
        pattern {
            resources = "compute.*"
            condition = "tags.Environment == 'production'"
            apply     = "configuration.server_setup.base"
        }
    }
}
"""
ansible = """
providers {
  aws_primary {
    provider = "aws"
    region   = "us-west-2"
    version  = "~> 3.0"
  }
}

service "web_application" {
  provider = "aws_primary"
  workspace = "production"

  infrastructure {
    compute "web_server" {
      resource_type = "aws_instance"
      instance_type = "t2.micro"
      ami           = "ami-0123456789"
      tags = {
        Name = "web-server"
        Environment = "production"
      }
    }

    compute "db_server" {
      resource_type = "aws_instance"
      instance_type = "t2.medium"
      ami           = "ami-0123456789"
      tags = {
        Name = "db-server"
        Environment = "production"
      }
    }
  }

  configuration {
    web_setup "base" {
      # Define execution order
      order = [
        "packages",
        "db_setup",
        "db_service",
        "db_operations",
        "web_config",
        "web_service",
        "app_config",
        "verify"
      ]

      include_vars = {
        file = "vars/${environment}.yml"
        when = "environment is defined"
      }

      # Package installation
      packages = [
        "nginx",
        "python3",
        "mysql-client"
      ]

      # File configurations
      files = {
        "/etc/nginx/nginx.conf" = {
          template = "nginx.conf.j2"
          mode = "0644"
          notify = ["restart nginx"]
          when = "ansible_distribution == 'Ubuntu'"
          group = "web_config"
        }
        "/etc/nginx/sites-available/default" = {
          content = "server { listen 80; root /var/www/html; }"
          notify = ["reload nginx"]
          group = "web_config"
        }
      }

      # Service configurations
      services = {
        "nginx" = ["started", "enabled"]
        "mysql" = ["started", "enabled"]
      }

      # Database setup block
      blocks = [
        {
          name = "Database Setup"
          group = "db_setup"
          tasks = [
            {
              name = "Install MySQL"
              package = "mysql-server"
            },
            {
              name = "Start MySQL"
              service = {
                name = "mysql"
                state = "started"
              }
            },
            {
              name = "Create application database"
              mysql_db = {
                name = "myapp"
                state = "present"
              }
            }
          ]
          rescue = [
            {
              name = "Cleanup failed MySQL install"
              package = {
                name = "mysql-server"
                state = "absent"
                purge = true
              }
            }
          ]
          always = [
            {
              name = "Notify team"
              command = "send_notification.sh"
              environment = {
                SLACK_CHANNEL = "#deployments"
              }
            }
          ]
        }
      ]

      # Individual tasks with groups
      tasks = [
        {
          name = "Wait for MySQL to be ready"
          group = "db_service"
          command = "mysqladmin ping -h localhost"
          retries = 5
          delay = 10
          when = "inventory_hostname in groups['db_servers']"
        },
        {
          name = "Create database backup"
          group = "db_operations"
          command = "mysqldump -u root myapp > backup.sql"
          delegate_to = "backup_server"
          run_once = true
        },
        {
          name = "Create application users"
          group = "app_config"
          user = {
            loop = [
              {
                name = "app_user",
                groups = "www-data"
              },
              {
                name = "backup_user",
                groups = "backup"
              }
            ]
          }
        },
        {
          name = "Configure firewall"
          group = "app_config"
          ufw = {
            rule = "allow"
            port = "80"
            proto = "tcp"
          }
          tags = ["security", "firewall"]
        }
      ]

      # Verification tasks
      verifications = [
        {
          name = "Check nginx running"
          group = "verify"
          command = "systemctl is-active nginx"
          retries = 3
          delay = 5
        },
        {
          name = "Check website accessible"
          group = "verify"
          command = "curl -f http://localhost/"
          failed_when = "verify_result.rc != 0"
        }
      ]

      # Database-related commands
      commands = [
        {
          name = "Run database migrations"
          group = "db_operations"
          command = "./migrate.sh"
          environment = {
            DB_HOST = "localhost"
            DB_USER = "root"
            DB_NAME = "myapp"
          }
          when = "inventory_hostname in groups['db_servers']"
        }
      ]

      # Handlers
      handlers = [
        {
          name = "restart nginx"
          service = {
            name = "nginx"
            state = "restarted"
          }
        },
        {
          name = "reload nginx"
          service = {
            name = "nginx"
            state = "reloaded"
          }
        }
      ]
    }
  }
}
"""


full = """
providers {
    aws {
        provider = "aws"
        region   = "us-west-2"
        version  = "~> 4.0"
    }
}

service "webapp" {
    provider = "aws_primary"
    
    # Overall deployment ordering
    deployment_order = [
        "infrastructure.network.vpc",
        "infrastructure.compute.web_server",
        "configuration.webapp_setup.base",
        "containers.app.frontend"
    ]

    infrastructure {
        network "vpc" {
            resource_type = "aws_vpc"
            cidr_block = "10.0.0.0/16"
            tags = {
                Name = "main-vpc"
            }
        }

        compute "web_server" {
            resource_type = "aws_instance"
            instance_type = "t2.micro"
            ami = "ami-005fc0f236362e99f"
            depends_on = ["infrastructure.network.vpc"]
            tags = {
                Name = "main_web_server"
            }
            key_name = "testing"
        }
    }

    configuration {
        webapp_setup "base" {
            # Task-specific ordering
            task_order = [
                "packages",
                "web_config",
                "web_service",
                "verify"
            ]

            packages = ["nginx", "docker"]

            files = {
                "/etc/nginx/nginx.conf" = {
                    content = "events {}\nhttp {\n    server {\n        listen 80;\n        server_name localhost;\n        location / {\n            return 200 'Hello from Ansible!';\n        }\n    }\n}"
                    mode    = "0644"
                    owner   = "root"
                    group   = "root"
                    notify  = ["restart nginx"]
                    when    = "ansible_distribution == 'Ubuntu'"
                    task_group   = "web_config"
                }
            }

            services = {
                "nginx" = {
                    state = ["started", "enabled"]
                    when  = "ansible_distribution == 'Ubuntu'"
                    task_group = "web_service"
                }
            }

            verifications = [
                {
                    name    = "Check nginx"
                    command = "systemctl is-active nginx"
                    group   = "verify"
                }
            ]
        }
    }

    containers {
        app "web_app" {
            image = "nginx:latest"
            type = "Deployment"
            replicas = 3
            
            # Container configuration
            command = ["/bin/sh"]
            args = ["-c", "nginx -g 'daemon off;'"]
            working_dir = "/usr/share/nginx/html"
            
            readiness_probe = {
                http_get = {
                    path = "/healthz"
                    port = 80
                }
                initial_delay_seconds = 5
                period_seconds = 10
            }

            # Resources
            resources = {
                limits = {
                    cpu = "500m"
                    memory = "512Mi"
                }
                requests = {
                    cpu = "250m"
                    memory = "256Mi"
                }
            }

            # Storage
            empty_dir_volumes = [
                {
                    name = "cache"
                    size_limit = "1Gi"
                }
            ]
            
            volume_mounts = [
                {
                    name = "cache"
                    mountPath = "/cache"
                }
            ]

            # Network
            ports = [
                {
                    container_port = 80
                    service_port = 80
                }
            ]

            service = {
                type = "LoadBalancer"
                annotations = {
                    "service.beta.kubernetes.io/aws-load-balancer-type" = "nlb"
                }
            }

            # Scheduling
            node_selector = {
                "kubernetes.io/os" = "linux"
                "node-type" = "web"
            }

            # Auto-scaling
            auto_scaling = {
                min_replicas = 2
                max_replicas = 10
                target_cpu_utilization_percentage = 80
            }
        }
    }

    deployment {
        map ={
            "infrastructure.compute.web_server" = "configuration.webapp_setup.base"
        }
    }
}
"""

kubes = """
providers {
    aws_primary {
        provider = "aws"
        region   = "us-west-2"
        version  = "~> 3.0"
    }
}

service "microservices" {
    provider = "aws_primary"
    workspace = "staging"

    containers {
        app "api_server" {
            image = "api:v1"
            type = "Deployment"
            replicas = 2

            command = ["python"]
            args = ["app.py"]
            working_dir = "/app"

            ports = [
                {
                    container_port = 8000
                    service_port = 80
                }
            ]

            environment = {
                DB_HOST = "postgres"
                DB_PORT = "5432"
                LOG_LEVEL = "info"
            }

            # Multiple probe types
            readiness_probe = {
                http_get = {
                    path = "/health"
                    port = 8000
                }
                initial_delay_seconds = 10
                period_seconds = 15
            }

            liveness_probe = {
                tcp_socket = {
                    port = 8000
                }
                initial_delay_seconds = 15
                period_seconds = 20
            }

            startup_probe = {
                http_get = {
                    path = "/startup"
                    port = 8000
                }
                failure_threshold = 30
                period_seconds = 10
            }

            # Init container for DB check
            init_containers = [
                {
                    name = "wait-for-db"
                    image = "busybox:1.28"
                    command = [
                        "sh",
                        "-c",
                        "until nc -z postgres 5432; do echo waiting for db; sleep 2; done;"
                    ]
                }
            ]

            resources = {
                limits = {
                    cpu = "1000m"
                    memory = "1Gi"
                }
                requests = {
                    cpu = "500m"
                    memory = "512Mi"
                }
            }

            # Multiple volume types
            empty_dir_volumes = [
                {
                    name = "cache"
                    size_limit = "500Mi"
                }
            ]

            host_path_volumes = [
                {
                    name = "logs"
                    path = "/var/log/apps"
                    type = "DirectoryOrCreate"
                }
            ]

            volume_mounts = [
                {
                    name = "cache"
                    mount_path = "/app/cache"
                },
                {
                    name = "logs"
                    mount_path = "/app/logs"
                }
            ]

            service = {
                type = "LoadBalancer"
                annotations = {
                    "service.beta.kubernetes.io/aws-load-balancer-type" = "nlb"
                    "prometheus.io/scrape" = "true"
                    "prometheus.io/port" = "8000"
                }
            }

            node_selector = {
                "kubernetes.io/os" = "linux"
                "node-type" = "app"
                "env" = "staging"
            }

            auto_scaling = {
                min_replicas = 2
                max_replicas = 5
                target_cpu_utilization_percentage = 70
            }
        }

        app "redis_cache" {
            image = "redis:6"
            type = "StatefulSet"
            replicas = 3

            ports = [
                {
                    container_port = 6379
                    service_port = 6379
                }
            ]

            resources = {
                limits = {
                    cpu = "500m"
                    memory = "1Gi"
                }
                requests = {
                    cpu = "250m"
                    memory = "512Mi"
                }
            }

            persistent_volume_claims = [
                {
                    name = "redis-data"
                    access_modes = ["ReadWriteOnce"]
                    storage = "10Gi"
                    storage_class = "standard"
                }
            ]

            volume_mounts = [
                {
                    name = "redis-data"
                    mount_path = "/data"
                }
            ]

            service = {
                type = "ClusterIP"
                annotations = {
                    "prometheus.io/scrape" = "true"
                    "prometheus.io/port" = "6379"
                }
            }

            # Pod disruption budget
            pod_disruption_budget = {
                min_available = 2
            }

            # Pod anti-affinity to spread replicas
            pod_anti_affinity = {
                preferred_during_scheduling_ignored_during_execution = [
                    {
                        weight = 100
                        pod_affinity_term = {
                            topology_key = "kubernetes.io/hostname"
                            label_selector = {
                                match_labels = {
                                    app = "redis_cache"
                                }
                            }
                        }
                    }
                ]
            }
        }
    }
}
"""

yay = """
providers {
  aws {
    provider = "aws"
    region = "us-east-1"
    version = "~> 4.0"
  }
}
service "webapp" {
  provider = "aws"
  infrastructure {
    network "vpc" {
        cidr_block            = "10.0.0.0/16"
        enable_dns_hostnames  = true
        enable_dns_support    = true
        tags = {
        Name = "main-vpc"
        }
        resource_type = "aws_vpc"
    }
    network "subnet1" {
        vpc_id                 = "${infrastructure.network.vpc.id}"
        cidr_block             = "10.0.1.0/24"
        availability_zone      = "us-east-1a"
        resource_type          = "aws_subnet"
    }
    network "subnet2" {
        vpc_id                 = "${infrastructure.network.vpc.id}"
        cidr_block             = "10.0.2.0/24"
        availability_zone      = "us-east-1b"
        resource_type          = "aws_subnet"
    }
    network "internet_gateway" {
        vpc_id        = "${infrastructure.network.vpc.id}"
        tags = {
        Name = "main"
        }
        resource_type = "aws_internet_gateway"
    }
    network "route_table" {
        vpc_id = "${infrastructure.network.vpc.id}"
        route = [
        {
            cidr_block = "0.0.0.0/0"
            gateway_id = "${infrastructure.network.internet_gateway.id}"
        }
        ]
        resource_type = "aws_route_table"
    }
    network "route_table_association_subnet1" {
        subnet_id      = "${infrastructure.network.subnet1.id}"
        route_table_id = "${infrastructure.network.route_table.id}"
        resource_type  = "aws_route_table_association"
    }
    network "route_table_association_subnet2" {
        subnet_id      = "${infrastructure.network.subnet2.id}"
        route_table_id = "${infrastructure.network.route_table.id}"
        resource_type  = "aws_route_table_association"
    }
    iam "eks_cluster" {
        name                = "eks_cluster"
        assume_role_policy  = file(role.json)
        resource_type       = "aws_iam_role"
    }
    iam "eks_cluster_policy_attachment" {
        role       = "${infrastructure.iam.eks_cluster.name}"
        policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
        resource_type = "aws_iam_role_policy_attachment"
    }
    compute "eks_cluster" {
        name       = "main"
        role_arn   = "${infrastructure.iam.eks_cluster.arn}"
        vpc_config = {
        subnet_ids = ["${infrastructure.network.subnet1.id}", "${infrastructure.network.subnet2.id}"]
        }
        depends_on = ["infrastructure.iam.eks_cluster_policy_attachment"]
        resource_type = "aws_eks_cluster"
    }
    compute "web_server" {
        instance_type         = "t2.micro"
        ami                   = "ami-005fc0f236362e99f"
        subnet_id             = "${infrastructure.network.subnet1.id}"
        tags = {
        Name = "main_web_server"
        }
        key_name              = "cloud-cli-key"
        depends_on            = ["infrastructure.network.vpc"]
        resource_type         = "aws_instance"
      }
  }
  configuration {
    play "webapp" {
        name = "Configure webapp"
        hosts = "{{ target_servers | default('all') }}"
        become = true
        vars = {
            target_web_servers = "web_servers"
            target_db_servers = "db_servers"
        }

        # Packages tasks block
        task {
            name = "Packages tasks"
            block {
                task {
                    name = "Install required packages"
                    package {
                        name = "{{ item }}"
                        state = "present"
                        update_cache = true
                    }
                    loop = ["nginx", "docker"]
                }
            }
        }

        # Other tasks block
        task {
            name = "Other tasks"
            block {
                task {
                    name = "Create/modify /etc/nginx/nginx.conf"
                    copy {
                        dest = "/etc/nginx/nginx.conf"
                        content = file(nginx.conf)
                        mode = "0644"
                        owner = "root"
                        group = "root"
                    }
                    notify = ["restart nginx"]
                    when = "ansible_distribution == 'Ubuntu'"
                }

                task {
                    name = "Ensure nginx is started"
                    service {
                        name = "nginx"
                        state = "started"
                        enabled = "yes"
                    }
                    register = "nginx_started_result"
                    retries = 3
                    delay = 5
                    failed_when = "nginx_started_result is failed"
                    changed_when = "nginx_started_result is changed"
                    when = "ansible_distribution == 'Ubuntu'"
                }

                task {
                    name = "Verify nginx"
                    command = "systemctl is-active nginx"
                    register = "verify_nginx"
                    failed_when = "verify_nginx.rc != 0"
                    changed_when = false
                    retries = 1
                    delay = 5
                }
            }
        }

        # Handlers
        handler {
            name = "restart nginx"
            service {
                name = "nginx"
                state = "restarted"
              }
          }
      }
  }

  containers {
    app "web_app" {
      image = "nginx:latest"
      type = "Deployment"
      replicas = 3
      command = ["/bin/sh"]
      args = ["-c", "nginx -g 'daemon off;'"]
      working_dir = "/usr/share/nginx/html"
      readiness_probe = {
        http_get = {
          path = "/healthz"
          port = 80
        }
        initial_delay_seconds = 5
        period_seconds = 10
      }
      resources = {
        limits = {
          cpu = "500m"
          memory = "512Mi"
        }
        requests = {
          cpu = "250m"
          memory = "256Mi"
        }
      }
      empty_dir_volumes = [
        {
          name = "cache"
          size_limit = "1Gi"
        }
      ]
      volume_mounts = [
        {
          name = "cache"
          mountPath = "/cache"
        }
      ]
      ports = [
        {
          container_port = 80
          service_port = 80
        }
      ]
      service = {
        type = "LoadBalancer"
        annotations = {
          "service.beta.kubernetes.io/aws-load-balancer-type" = "nlb"
        }
      }
      node_selector = {
        "kubernetes.io/os" = "linux"
        node-type = "web"
      }
      auto_scaling = {
        min_replicas = 2
        max_replicas = 10
        target_cpu_utilization_percentage = 80
      }
    }
  }
  deployment {
    mappings = {
      "infrastructure.compute.web_server" = "configuration.webapp_setup.base"
    }
  }
}
"""
# main_convert(yay)