from setuptools import setup, find_packages

with open('requirements.txt') as f:
    required = f.read().splitlines()

setup(
    name='cloudscript-cli',
    version='0.1.0',
    description='Cloudscript combines the functionalities of Terraform, Kubernetes, and Ansible, under one, simple syntax.',
    author='Forge',
    author_email='team@tryforge.ai',
    url='https://github.com/o37-autoforge/cloud',
    packages=find_packages(),
    include_package_data=True,
    install_requires=required,
    entry_points={
        'console_scripts': [
            'cloud=CLI.cloud_cli:cli',
        ],
    },
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
    python_requires='>=3.10',
)