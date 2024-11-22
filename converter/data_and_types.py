from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
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
    providers: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    resources: Dict[str, Dict[str, Dict[str, Any]]] = field(default_factory=dict)
    data_sources: Dict[str, Dict[str, Dict[str, Any]]] = field(default_factory=dict)
    modules: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    variables: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    outputs: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    locals: Dict[str, Any] = field(default_factory=dict)
    backend: Optional[Dict[str, Any]] = None

@dataclass
class InfrastructureComponent:
    name: str
    component_type: str
    attributes: Dict[str, Any]
    provider: Optional[str] = None
    count: Optional[int] = None
    for_each: Optional[Union[List[Any], Dict[str, Any]]] = None
    depends_on: List[str] = field(default_factory=list)
    lifecycle: Optional[Dict[str, Any]] = None
    provisioners: Optional[List[Dict[str, Any]]] = None
    resource_type: Optional[str] = None
    package_manager: Optional[str] = None

@dataclass
class ContainerSpec:
    name: str
    image: str
    ports: List[Dict[str, Any]]
    environment: Dict[str, str]
    replicas: int = 1
    health_check: Optional[Dict[str, Any]] = None
    resources: Optional[Dict[str, Any]] = None
    volumes: Optional[List[Dict[str, Any]]] = None
    auto_scaling: Optional[Dict[str, Any]] = None
    namespace: Optional[str] = None
    service: Optional[Dict[str, Any]] = None

@dataclass
class ConfigurationSpec:
    packages: List[str]
    files: Dict[str, Any]
    services: Dict[str, List[str]]
    variables: Dict[str, Any]
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    commands: List[Dict[str, Any]] = field(default_factory=list)
    verifications: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class Service:
    name: str
    provider: str
    order: List[str]
    infrastructure: List[InfrastructureComponent] = field(default_factory=list)
    configuration: Optional[ConfigurationSpec] = None
    containers: List[ContainerSpec] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    deployment: Optional[Dict[str, Any]] = None

class IaCGenerator(ABC):
    @abstractmethod
    def generate(self, services: List[Service]) -> str:
        pass