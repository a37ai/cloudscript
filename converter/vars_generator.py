import json
import os
import hcl2

def create_empty_vars(terraform_file_path):
    if not os.path.isfile(terraform_file_path):
        print(f"Error: The file {terraform_file_path} does not exist.")
        return

    # Check for .tf.json or .tf specifically
    if terraform_file_path.endswith('.tf.json'):
        file_type = 'tf.json'
    elif terraform_file_path.endswith('.tf'):
        file_type = 'tf'
    else:
        print("Error: Unsupported file format. Please provide a .tf or .tf.json file.")
        return

    try:
        if file_type == 'tf.json':
            with open(terraform_file_path, 'r') as tf_file:
                terraform_data = json.load(tf_file)
        elif file_type == 'tf':
            if hcl2 is None:
                print("Error: hcl2 library is not installed. Install it using 'pip install python-hcl2'.")
                return
            with open(terraform_file_path, 'r') as tf_file:
                terraform_data = hcl2.load(tf_file)
    except Exception as e:
        print(f"Error parsing the Terraform file: {e}")
        return

    variables = terraform_data.get('variable', {})
    if not variables:
        print("No variables found in the Terraform file.")
        return

    vars_dict = {var_name: "" for var_name in variables.keys()}

    vars_json_path = os.path.join(os.path.dirname(terraform_file_path), 'vars.json')

    try:
        with open(vars_json_path, 'w') as vars_file:
            json.dump(vars_dict, vars_file, indent=2)
        print(f"vars.json successfully created at {vars_json_path}")
    except Exception as e:
        print(f"Error writing vars.json: {e}")


# create_empty_vars("IaC/main.tf.json")
