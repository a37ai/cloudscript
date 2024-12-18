from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union, Callable
from abc import ABC, abstractmethod
from enum import Enum

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