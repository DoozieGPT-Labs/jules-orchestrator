#!/usr/bin/env python3
"""
Setup script for Jules Orchestrator
"""

from setuptools import setup, find_packages
import os

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "SKILL.md"), "r") as f:
    long_description = f.read()

setup(
    name="jules-orchestrator",
    version="3.0.0",
    description="Async AI software factory with background tracking for Google Jules",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Claude Code Team",
    python_requires=">=3.8",
    packages=find_packages(),
    scripts=["bin/jules-agent"],
    entry_points={
        "console_scripts": [
            "jules-agent=jules_orchestrator.cli:main",
        ],
    },
    install_requires=[
        # No external dependencies - uses standard library
    ],
    extras_require={
        "dev": ["pytest", "black", "flake8"],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Build Tools",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="jules github automation ai software-factory",
    project_urls={
        "Bug Reports": "https://github.com/DoozieGPT-Labs/jules-orchestrator/issues",
        "Source": "https://github.com/DoozieGPT-Labs/jules-orchestrator",
    },
)
