from .utils import parse_universal_hcl
from .terraform import TerraformGenerator
from .ansible import NewAnsibleGenerator
from .kubernetes import KubernetesGenerator
from .vars_generator import create_empty_vars
import os

def ensure_directory():
    """Create IaC directory if it doesn't exist."""
    os.makedirs('IaC', exist_ok=True)

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
