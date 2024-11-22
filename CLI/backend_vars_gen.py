import json
import os

def generate_backend_tf(tf_file_path, vars_file_path, backend_tf_path="IaC/backend.tf"):
    """
    Reads backend configuration variables from vars.json, verifies them against tf.json,
    and creates backend.tf for Terraform.
    
    :param tf_file_path: Path to the Terraform configuration (tf.json) file.
    :param vars_file_path: Path to the vars.json file.
    :param backend_tf_path: Path to the output backend.tf file.
    """
    # Load tf.json to check for required variable definitions
    try:
        with open(tf_file_path, 'r') as tf_file:
            tf_data = json.load(tf_file)
            tf_variables = tf_data.get("variable", {})
    except FileNotFoundError:
        print(f"Error: {tf_file_path} not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: {tf_file_path} contains invalid JSON.")
        return

    # Define required backend variable names
    required_backend_vars = ["terraform_state_bucket", "terraform_state_key", "aws_region", "terraform_lock_table"]

    # Check that required backend variables are defined in tf.json
    missing_in_tf = [var for var in required_backend_vars if var not in tf_variables]
    if missing_in_tf:
        print(f"Error: The following required variables are missing in {tf_file_path}: {', '.join(missing_in_tf)}")
        return

    # Load vars.json to get values for backend configuration
    try:
        with open(vars_file_path, 'r') as vars_file:
            vars_data = json.load(vars_file)
    except FileNotFoundError:
        print(f"Error: {vars_file_path} not found.")
        return
    except json.JSONDecodeError:
        print(f"Error: {vars_file_path} contains invalid JSON.")
        return

    # Check that each required backend variable has a value in vars.json
    backend_vars_values = {var: vars_data.get(var, "") for var in required_backend_vars}
    missing_values = [var for var, value in backend_vars_values.items() if not value]
    if missing_values:
        print(f"Error: Missing values for the following variables in {vars_file_path}: {', '.join(missing_values)}")
        return

    # Generate backend.tf content
    backend_content = f"""
terraform {{
  backend "s3" {{
    bucket         = "{backend_vars_values['terraform_state_bucket']}"
    key            = "{backend_vars_values['terraform_state_key']}"
    region         = "{backend_vars_values['aws_region']}"
    encrypt        = true
    dynamodb_table = "{backend_vars_values['terraform_lock_table']}"
  }}
}}
"""

    # Write to backend.tf
    try:
        with open(backend_tf_path, 'w') as backend_file:
            backend_file.write(backend_content.strip())
        print(f"{backend_tf_path} successfully created.")
    except Exception as e:
        print(f"Error writing to {backend_tf_path}: {e}")

# Usage
generate_backend_tf("IaC/main.tf.json", "IaC/vars.json")
