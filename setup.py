from setuptools import setup, find_packages

setup(
    name="mlflow-jfrog-plugin",
    version="1.0.0",
    description="Plugin to store MLFlow experiments artifacts on JFrog Artifactory",
    packages=find_packages(),
    install_requires=["mlflow", "requests>=2.31.0"],
    entry_points={
        # Define a ArtifactRepository plugin for artifact URIs with scheme 'artifactory'
        "mlflow.artifact_repository": "artifactory=plugin.artifactory_repository:JFrogArtifactoryRepository",
    },
    url='https://github.com/jfrog/mlflow-jfrog-plugin',
    author='JFrog',
    author_email='pypi@jfrog.com',
    python_requires='>=3.9',
    license="Apache License 2.0",
)
