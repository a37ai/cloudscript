import hcl2
import yaml
import json
from abc import ABC, abstractmethod
import os
from enum import Enum
from .data_and_types import Service, ConfigurationSpec, ContainerSpec, InfrastructureComponent
from typing import List, Any, Union, Dict, Tuple, Optional

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