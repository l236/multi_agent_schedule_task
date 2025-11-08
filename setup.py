#!/usr/bin/env python3
"""
Setup script for creating distribution packages.
"""

from setuptools import setup, find_packages

# Read requirements
def read_requirements():
    with open('requirements.txt', 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

# Read README
def read_readme():
    with open('README.md', 'r') as f:
        return f.read()

setup(
    name="multi-agent-schedule-task",
    version="1.0.0",
    description="Lightweight Agent Task Scheduling System",
    long_description=read_readme(),
    long_description_content_type="text/markdown",
    packages=find_packages(),
    include_package_data=True,
    install_requires=read_requirements(),
    python_requires=">=3.8",
)
