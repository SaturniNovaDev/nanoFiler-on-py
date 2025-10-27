from pathlib import Path
from setuptools import setup, find_packages

# setup.py - minimal, editable metadata for packaging with setuptools
# Edit fields below (name, version, author, install_requires, entry_points, etc.)


HERE = Path(__file__).parent
README = (
    (HERE / "README.md").read_text(encoding="utf-8")
    if (HERE / "README.md").exists()
    else ""
)

setup(
    name="nanoFiler-on-py",
    version="0.4.0",
    description="File manager and explorer built on python with performance and optimisation in mind.",
    long_description=README,
    long_description_content_type="text/markdown",
    author="Peter Knows",
    author_email="peterknows24@protonmail.com",
    url="https://github.com/SaturniNovaDev/nanoFiler-on-py",
    packages=find_packages(exclude=("tests", "docs")),
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=[
        # "requests>=2.25.1",
    ],
    extras_require={
        "dev": [
            "pytest>=6.2.4",
            "flake8>=3.9.2",
        ],
    },
    entry_points={
        # create console script: `nano-filer` -> nano_filer.cli:main
        "console_scripts": [
            "nano-filer=nano_filer.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GPLv3 License",
        "Operating System :: Windows",
        "Programming Language :: Python :: 3.8",
    ],
    project_urls={
        "Source": "https://github.com/SaturniNovaDev/nanoFiler-on-py",
        "Tracker": "https://github.com/SaturniNovaDev/nanoFiler-on-py/issues",
    },
)
