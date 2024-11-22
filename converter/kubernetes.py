from .data_and_types import IaCGenerator, Service, ContainerSpec
from typing import List, Dict
import yaml

class KubernetesGenerator(IaCGenerator):
    def generate(self, services: List[Service]) -> str:
        k8s_resources = []
        config_maps = set()  # Track created ConfigMaps
        namespaces = set()

        for service in services:
            if not service.containers:
                continue

            for container in service.containers:
                namespace = container.namespace if container.namespace else "default"

                # Create Namespace if not default and not already created
                if namespace != 'default' and namespace not in namespaces:
                    k8s_resources.append({
                        "apiVersion": "v1",
                        "kind": "Namespace",
                        "metadata": {
                            "name": namespace
                        }
                    })
                    namespaces.add(namespace)

                deployment = self._create_k8s_deployment(container)
                service_resource = self._create_k8s_service(container)

                k8s_resources.extend([deployment, service_resource])

                if container.auto_scaling:
                    hpa = self._create_horizontal_pod_autoscaler(container)
                    k8s_resources.append(hpa)

                if container.volumes:
                    for volume in container.volumes:
                        if 'config_map' in volume:
                            config_map_name = volume['config_map']['name']
                            if config_map_name not in config_maps:
                                config_maps.add(config_map_name)
                                k8s_resources.append({
                                    "apiVersion": "v1",
                                    "kind": "ConfigMap",
                                    "metadata": {
                                        "name": config_map_name,
                                        "namespace": namespace
                                    },
                                    "data": {
                                        # Placeholder data; in real scenarios, populate accordingly
                                        "config.yaml": "key: value"
                                    }
                                })

        return yaml.dump_all(k8s_resources, explicit_start=True)

    def _create_k8s_deployment(self, container: ContainerSpec) -> Dict:
        deployment_name = container.name.replace("_", "-")
        namespace = container.namespace if container.namespace else "default"

        deployment = {
            "apiVersion": "apps/v1",
            "kind": "Deployment",
            "metadata": {
                "name": deployment_name,
                "namespace": namespace
            },
            "spec": {
                "replicas": container.replicas,
                "selector": {
                    "matchLabels": {
                        "app": deployment_name
                    }
                },
                "template": {
                    "metadata": {
                        "labels": {
                            "app": deployment_name
                        }
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": deployment_name,
                                "image": container.image,
                                "ports": [{"containerPort": port["container_port"]} for port in container.ports],
                                "env": [
                                    {"name": key, "value": str(value)}
                                    for key, value in container.environment.items()
                                ]
                            }
                        ]
                    }
                }
            }
        }

        if container.health_check:
            health_check = container.health_check.copy()
            if 'http_get' in health_check:
                health_check['httpGet'] = health_check.pop('http_get')
            # Convert snake_case to camelCase for probe fields
            probe_fields = {
                'initial_delay_seconds': 'initialDelaySeconds',
                'period_seconds': 'periodSeconds',
                'timeout_seconds': 'timeoutSeconds',
                'success_threshold': 'successThreshold',
                'failure_threshold': 'failureThreshold'
            }
            for key, camel_key in probe_fields.items():
                if key in health_check:
                    health_check[camel_key] = health_check.pop(key)
            deployment["spec"]["template"]["spec"]["containers"][0]["readinessProbe"] = health_check

        if container.resources:
            deployment["spec"]["template"]["spec"]["containers"][0]["resources"] = container.resources

        if container.volumes:
            deployment["spec"]["template"]["spec"]["volumes"] = []
            for volume in container.volumes:
                vol = volume.copy()
                if "config_map" in vol:
                    vol["configMap"] = vol.pop("config_map")
                deployment["spec"]["template"]["spec"]["volumes"].append(vol)

        # Handle service annotations
        if container.service:
            deployment["metadata"]["annotations"] = container.service.get("annotations", {})

        return deployment

    def _create_k8s_service(self, container: ContainerSpec) -> Dict:
        service_name = container.name.replace("_", "-")
        namespace = container.namespace if container.namespace else "default"

        service_type = container.service.get("type", "ClusterIP") if container.service else "ClusterIP"

        service_metadata = {
            "name": service_name,
            "namespace": namespace,
        }
        if container.service and "annotations" in container.service:
            service_metadata["annotations"] = container.service.get("annotations", {})

        return {
            "apiVersion": "v1",
            "kind": "Service",
            "metadata": service_metadata,
            "spec": {
                "selector": {
                    "app": service_name
                },
                "ports": [
                    {"port": port["service_port"], "targetPort": port["container_port"]}
                    for port in container.ports
                ],
                "type": service_type
            }
        }

    def _create_horizontal_pod_autoscaler(self, container: ContainerSpec) -> Dict:
        service_name = container.name.replace("_", "-")
        namespace = container.namespace if container.namespace else "default"

        return {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": f"{service_name}-hpa",
                "namespace": namespace
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": service_name
                },
                "minReplicas": container.auto_scaling.get("min", 1),
                "maxReplicas": container.auto_scaling.get("max", 10),
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": container.auto_scaling.get("cpu_threshold", 80)
                            }
                        }
                    }
                ]
            }
        }