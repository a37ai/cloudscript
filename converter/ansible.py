from .data_and_types import Service, IaCGenerator
from typing import List
import yaml

class AnsibleGenerator(IaCGenerator):
    def generate(self, services: List[Service]) -> str:
        playbook = []

        # Add the preliminary localhost setup task
        playbook.append({
            "hosts": "localhost",
            "connection": "local",
            "gather_facts": False,
            "tasks": [
                {
                    "debug": {
                        "msg": "Setting up localhost"
                    }
                }
            ]
        })

        for service in services:
            if not service.configuration:
                continue

            config_spec = service.configuration

            # Create the play for the service
            play = {
                "name": f"Configure {service.name}",
                "hosts": "localhost",
                "connection": "local",
                "gather_facts": False,
                "become": False,
                "vars": {},
                "tasks": []
            }

            # Add Docker Desktop check and warning
            play["tasks"].extend([
                {
                    "name": "Check if Docker Desktop is installed",
                    "stat": {
                        "path": "/Applications/Docker.app"
                    },
                    "register": "docker_desktop"
                },
                {
                    "name": "Warning about Docker Desktop",
                    "debug": {
                        "msg": "Docker Desktop is not installed. Please install it from https://www.docker.com/products/docker-desktop"
                    },
                    "when": "not docker_desktop.stat.exists"
                }
            ])

            # Add package installation tasks
            play["tasks"].append({
                "name": "Install required packages",
                "community.general.homebrew": {
                    "name": "{{ item }}",
                    "state": "present",
                    "update_homebrew": True
                },
                "loop": config_spec.packages,
                "tags": ["packages"]
            })

            # Add AWS CLI installation
            play["tasks"].append({
                "name": "Install AWS CLI",
                "community.general.homebrew": {
                    "name": "awscli",
                    "state": "present"
                },
                "tags": ["packages"]
            })

            # Add AWS credentials check
            play["tasks"].extend([
                {
                    "name": "Check if AWS credentials exist",
                    "stat": {
                        "path": "{{ lookup('env', 'HOME') }}/.aws/credentials"
                    },
                    "register": "aws_creds"
                },
                {
                    "name": "Warning about AWS credentials",
                    "debug": {
                        "msg": "AWS credentials not found. Please configure AWS CLI with 'aws configure' before running kubectl configuration"
                    },
                    "when": "not aws_creds.stat.exists"
                }
            ])

            # Add kubectl configuration task
            for command in config_spec.commands:
                if command.get("name") == "Configure kubectl":
                    play["tasks"].append({
                        "name": command.get("name", "Configure kubectl"),
                        "shell": command.get("command", ""),
                        "args": {},
                        "environment": command.get("environment", {}),
                        "when": "aws_creds.stat.exists",
                        "tags": ["configuration"]
                    })

            # Add verification tasks
            verifications = config_spec.verifications if config_spec.verifications else []
            for verification in verifications:
                play["tasks"].append({
                    "name": verification.get("name", "Run verification command"),
                    "command": verification.get("command", ""),
                    "register": f"{verification.get('name', 'verification').replace(' ', '_').lower()}",
                    "tags": ["verification"]
                })

            # Add task to display versions
            version_messages = [
                f"{verification.get('name')}: {{ {{ {verification.get('name', 'verification').replace(' ', '_').lower()}.stdout }} }}"
                for verification in verifications
            ]
            play["tasks"].append({
                "name": "Show versions",
                "debug": {
                    "msg": version_messages
                },
                "tags": ["verification"]
            })

            playbook.append(play)

        return yaml.dump(playbook, sort_keys=False)