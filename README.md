# JFrog MLFlow plugin

## Overview
JFrog MLFlow plugin is a plugin created by JFrog for customers using MLflow product.
[MLflow](https://www.mlflow.org/) is an open-source platform for managing the end-to-end machine learning lifecycle. 
The JFrog MLflow plugin extends MLflow functionality by replacing the default artifacts location of MLflow with JFrog Artifactory.
Once MLflow experiments artifacts are available inside JFrog Artifactory, they become an integral part of the company's release lifecycle as any other artifact and are also covered by all the security tools provided through the JFrog platform.    

## Installation
Install the plugin using pip, installation should be done on the mlflow tracking server.
optionally the plugin can be installed on any client that wants to change the default artifacts location for a specific artifactory repository
```bash
pip install mlflow-jfrog-plugin 
```

Set the JFrog Artifactory authentication token, using the ARTIFACTORY_AUTH_TOKEN environment variable:
Preferably, for security reasons use a token with minimum permissions required rather than an admin token
```bash
export ARTIFACTORY_AUTH_TOKEN=<your artifactory token goes here>
```

Once the plugin is installed and token set, your mlflow tracking server can be started with JFrog artifactory repository as a target artifacts destination
USe the mlflow documentation for additional mlflow server options
```bash
mlflow server --host <mlflow tracking server host> --port <mlflow tracking server port> --artifacts-destination artifactory://<JFrog artifactory URL>/artifactory/<repository[/optional base path]>
```
For allowing large artifacts upload to JFrog artifactory, it is advisable to increase upload timeout settings when starting th mlflow server:
--gunicorn-opts '--timeout <timeout in seconds>'


## Usage

MLflow model logging code example: 
```python
import mlflow
from mlflow import MlflowClient
from transformers import pipeline

mlflow.set_tracking_uri(
    "<your mlflow tracking server uri>"
)
mlflow.create_experiment(
    "<your_exp_name>"
)
classifier = pipeline("sentiment-analysis", model="michellejieli/emotion_text_classifier")

with mlflow.start_run():
     mlflow.transformers.log_model(transformers_model=classifier, artifact_path=<model_name>)
mlflow.end_run()
```

## Configuration

Additional optional settings (set on mlflow tracking server before its started):
to use no-ssl artifactory URL, set ARTIFACTORY_NO_SSL to true. default is false
```bash
export ARTIFACTORY_NO_SSL=true
```
to allow JFrog operations debug logging, set ARTIFACTORY_DEBUG to true. default is false
```bash
export ARTIFACTORY_DEBUG=true
```
to prevent MLflow garbage collection remove any artifacts from being removed from artifactory, set ARTIFACTORY_ARTIFACTS_DELETE_SKIP to true. default is false
Notice this settings might cause significant storage usage and might require JFrog files retention setup. 
```bash
export ARTIFACTORY_ARTIFACTS_DELETE_SKIP=true
```

## Features
- Experiments artifacts log/save are performed against JFrog Artifactory
- Experiments artifacts viewing and downloading using MLflow UI and APIs as well as JFrog UI and APIs are done against JFrog Artifactory
- Experiments Artifacts deletion follow experiments lifecycle (automatically or through mlflow gc)
- Changing specific experiments artifacts destination is allowed through experiment creation command (by changing artifact_location)  

## Contributing
We welcome contributions! If you find any issues or have suggestions for improvements, please create an issue or pull request on the GitHub repository.

Notice that for running the testing locally, you will need to either launch an artifactory and point the test scripts to it, or upload a license string into tests/art.lic 

## License
Apache 2.0
