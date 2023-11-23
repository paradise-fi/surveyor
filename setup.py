import setuptools
import versioneer


with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="Surveyor",
    python_requires=">3.7",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    author="Jan Mrázek",
    author_email="email@honzamrazek.cz",
    description="Simple tool for benchmarking in Paradise @ FI MUNI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/paradise-fi/surveyor",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    setup_requires=[
        "versioneer"
    ],
    install_requires=[
        "Flask",
        "Flask-SQLAlchemy",
        "Flask-Migrate",
        "python-dateutil",
        "psycopg2"
    ],
    entry_points = {
        "console_scripts": [
            "surveyor=surveyor.cli:cli",
            "surveyor-runner=surveyor.runner:cli"
        ],
    },
    zip_safe=False
)
