import hcl2
import yaml
import json
from abc import ABC, abstractmethod
import os
from enum import Enum
from .data_and_types import Service, ConfigurationSpec, ContainerSpec, InfrastructureComponent
from typing import List, Any, Union, Dict


def parse_universal_hcl(hcl_content: str) -> List[Service]:
    print("Parsing HCL content...")
    parsed_hcl = hcl2.loads(hcl_content)
    print("Parsed HCL:", json.dumps(parsed_hcl, indent=2))
    services: List[Service] = []

    service_blocks = parsed_hcl.get("service", [])
    if not isinstance(service_blocks, list):
        service_blocks = [service_blocks]

    print(f"Found {len(service_blocks)} service blocks")

    for service_block in service_blocks:
        if not isinstance(service_block, dict):
            continue

        for service_name, service_content in service_block.items():
            print(f"\nProcessing service: {service_name}")

            # Extract provider and order
            provider = service_content.get("provider", "aws")
            order = service_content.get("order", [])

            # Parse infrastructure
            infrastructure_components = []
            if infra_block := service_content.get("infrastructure"):
                print(f"Found infrastructure block for {service_name}:")
                # If infra_block is a list, process each item
                if isinstance(infra_block, list):
                    for infra_item in infra_block:
                        process_infrastructure_block(infra_item, infrastructure_components)
                elif isinstance(infra_block, dict):
                    process_infrastructure_block(infra_block, infrastructure_components)
                else:
                    print(f"Unexpected infrastructure_block type: {type(infra_block)}")

            # Parse configuration
            configuration_spec = None
            if config_block := service_content.get("configuration"):
                print(f"Found configuration block for {service_name}:")
                configuration_spec = process_configuration_block(config_block)
                print(f"Created ConfigurationSpec for {service_name}")

            # Parse containers
            containers = []
            if containers_block := service_content.get("containers"):
                print(f"Found containers block for {service_name}:")
                # Adjust containers_block if it's a list
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
                # Handle deployment being a list or dict
                if isinstance(deployment, list):
                    if len(deployment) > 0 and isinstance(deployment[0], dict):
                        deployment = deployment[0]
                        print(f"Extracted deployment dict from list for {service_name}")
                    else:
                        print(f"Unexpected deployment list structure for {service_name}")
                        deployment = {}
                elif isinstance(deployment, dict):
                    pass  # Already a dict
                else:
                    print(f"Unexpected deployment type for {service_name}: {type(deployment)}")
                    deployment = {}

            # Create the service object with the components, configuration, containers, and deployment
            service = Service(
                name=service_name,
                provider=provider,
                order=order,
                infrastructure=infrastructure_components,
                configuration=configuration_spec,
                containers=containers,
                dependencies=service_content.get("dependencies", []),
                deployment=deployment if isinstance(deployment, dict) else None
            )
            services.append(service)
            print(f"Added Service: {service.name}")

    return services

def process_infrastructure_block(infra_block: Any, infrastructure_components: List[InfrastructureComponent]):
    print("Processing infrastructure block...")
    if isinstance(infra_block, dict):
        for component_type, components in infra_block.items():
            process_components(component_type, components, infrastructure_components)
    elif isinstance(infra_block, list):
        for block in infra_block:
            process_infrastructure_block(block, infrastructure_components)
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

def process_component(component_type: str, component_name: str, component_content: Dict[str, Any],
                      infrastructure_components: List[InfrastructureComponent]):
    print(f"Processing component: {component_type} '{component_name}'")

    attributes = component_content.copy()
    count = attributes.pop("count", None)
    # Remove the line that pops availability_zones
    # availability_zones = attributes.pop("availability_zones", None)
    depends_on = attributes.pop("depends_on", [])
    lifecycle = attributes.pop("lifecycle", None)
    provisioners = attributes.pop("provisioners", None)
    provider = attributes.pop("provider", None)

    # Infer package manager based on OS
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
        count=count,
        # Remove for_each parameter
        # for_each=availability_zones,
        depends_on=depends_on,
        lifecycle=lifecycle,
        provisioners=provisioners,
        package_manager=package_manager
    )

    infrastructure_components.append(infra_component)
    print(f"Added component {infra_component.name} to infrastructure components")

def process_configuration_block(config_block: Dict[str, Any]) -> ConfigurationSpec:
    print("Processing configuration block...")
    packages = []
    files = {}
    services = {}
    variables = {}
    tasks = []
    commands = []
    verifications = []

    if isinstance(config_block, list):
        config_items = config_block
    else:
        config_items = [config_block]

    for config_item in config_items:
        if isinstance(config_item, dict):
            server_setup_blocks = config_item.get("server_setup", [])
            if not isinstance(server_setup_blocks, list):
                server_setup_blocks = [server_setup_blocks]
            for server_setup in server_setup_blocks:
                for setup_name, setup_content in server_setup.items():
                    print(f"Processing server_setup: {setup_name}")
                    packages.extend(setup_content.get("packages", []))
                    files.update(setup_content.get("files", {}))
                    services = {**services, **setup_content.get("services", {})}
                    variables = {**variables, **setup_content.get("variables", {})}
                    tasks.extend(setup_content.get("tasks", []))
                    commands.extend(setup_content.get("commands", []))
                    verifications.extend(setup_content.get("verifications", []))

    configuration_spec = ConfigurationSpec(
        packages=packages,
        files=files,
        services=services,
        variables=variables,
        tasks=tasks,
        commands=commands,
        verifications=verifications
    )
    return configuration_spec

def process_containers_block(containers_block: Any) -> List[ContainerSpec]:
    print("Processing containers block...")
    containers = []
    if isinstance(containers_block, dict):
        for container_type, container_configs in containers_block.items():
            process_container_configs(container_type, container_configs, containers)
    elif isinstance(containers_block, list):
        for container_item in containers_block:
            if isinstance(container_item, dict):
                containers.extend(process_containers_block(container_item))
    else:
        print(f"Unexpected containers_block type: {type(containers_block)}")
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
    image = container_content.get("image")
    replicas = container_content.get("replicas", 1)
    ports = container_content.get("ports", [])
    environment = container_content.get("env", {})
    health_check = container_content.get("health_check")
    resources = container_content.get("resources")
    volumes = container_content.get("volumes")
    auto_scaling = container_content.get("auto_scaling")
    namespace = container_content.get("namespace")
    service = container_content.get("service")
    return ContainerSpec(
        name=container_name,
        image=image,
        replicas=replicas,
        ports=ports,
        environment=environment,
        health_check=health_check,
        resources=resources,
        volumes=volumes,
        auto_scaling=auto_scaling,
        namespace=namespace,
        service=service
    )