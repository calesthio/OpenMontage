from setuptools import setup, find_packages

setup(
    name="openmontage",
    version="0.1.0",
    description="AI-Orchestrated Video Production Platform",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pyyaml>=6.0",
        "pydantic>=2.0",
        "jsonschema>=4.20",
        "python-dotenv>=1.0",
        "Pillow>=10.0",
        "requests>=2.31",
    ],
)
