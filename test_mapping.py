import json
from hcl2.api import loads

# Read the HCL file
with open('test_mapping.hcl', 'r') as f:
    hcl_content = f.read()

# Parse the HCL and get mappings
result, mappings = loads(hcl_content)

print("Original HCL:")
print("-" * 80)
print(hcl_content)
print("-" * 80)

print("\nParsed JSON:")
print("-" * 80)
print(json.dumps(result, indent=2))
print("-" * 80)

print("\nLine Mappings:")
print("-" * 80)
for mapping in mappings:
    print(f"Original Line {mapping['original_line']}:")
    print(f"  HCL: {mapping['original_content']}")
    print(f"  JSON (Line {mapping['final_line']}): {mapping['final_content']}")
    print()
