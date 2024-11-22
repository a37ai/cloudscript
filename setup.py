# setup.py
from setuptools import setup, find_packages

setup(
    name='cloud-cli',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Click',
        'python-hcl2',
        'PyYAML',
    ],
    entry_points={
        'console_scripts': [
            'cloud=CLI.cloud_cli:cli',  # Changed from cli.cloud_cli to CLI.cloud_cli
        ],
    },
)