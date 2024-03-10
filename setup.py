from setuptools import setup, find_packages

setup(
    name="mlflow-jfrog-plugin",
    version="1.0.1",
    description="Plugin to store MLFlow experiments artifacts on JFrog Artifactory",
    long_description="JFrog MLFlow plugin is a plugin created by JFrog for customers using MLflow product. "
                     "MLflow is an open-source platform for managing the end-to-end machine learning lifecycle. "
                     "The JFrog MLflow plugin extends MLflow functionality by replacing the default artifacts location of MLflow with JFrog Artifactory. "
                     "Once MLflow experiments artifacts are available inside JFrog Artifactory, "
                     "they become an integral part of the company's release lifecycle as any other artifact and are also covered by all the security tools provided through the JFrog platform.",
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
