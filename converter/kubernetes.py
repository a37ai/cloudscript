from .data_and_types import IaCGenerator, Service, ContainerSpec
from typing import List, Dict
import yaml
from .data_and_types import *
import json

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