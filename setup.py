from deply import __version__
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="deply",
    version=__version__,
    author="Archil Abuladze",
    author_email="armiworker@gmail.com",
    description="A tool to enforce architectural patterns in python projects",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/vashkatsi/deply",
    project_urls={
        "Bug Tracker": "https://github.com/vashkatsi/deply/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.14",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "."},
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "PyYAML>=5.1",
    ],
    entry_points={
        'console_scripts': [
            'deply=deply.main:main',
        ],
    },
    include_package_data=True,
)
