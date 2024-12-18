from setuptools import setup, find_packages

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
    name='cloud-cli',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=required,
    entry_points={
        'console_scripts': [
            'cloud=CLI.cloud_cli:cli',
        ],
    },
)