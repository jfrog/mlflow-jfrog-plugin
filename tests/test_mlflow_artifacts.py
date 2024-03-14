import logging
import os
import json
import subprocess
import tempfile
import time
from collections import namedtuple
import socket
import pytest
import requests
import shutil
import mlflow
from pathlib import Path
from mlflow import MlflowClient
from mlflow.artifacts import download_artifacts
_logger = logging.getLogger(__name__)
from requests.auth import HTTPBasicAuth
LOCALHOST = "127.0.0.1"
ARTIFACTS_DESTINATION = "localhost:8082/artifactory/test-server/subpath"
def is_windows():
    return os.name == "nt"

def _launch_server(host, port,  backend_store_uri, default_artifact_root,artifacts_destination):
    # cleanup mlruns folder

    cmd = [
        "mlflow",
        "server",
        "--host",
        host,
        "--port",
        str(port),
        "--backend-store-uri",
        backend_store_uri,
        "--default-artifact-root",
        default_artifact_root,
        "--artifacts-destination",
        artifacts_destination,
        "--dev",
  #      "--gunicorn-opts",
  #      '--timeout 180 --log-level debug',
 #       *extra_cmd,
    ]
    process = subprocess.Popen(cmd)
    _await_server_up_or_die(port)
    return process
def _launch_RT_server():
    image_name ="test_server_container"

    server_is_already_up = _await_RT_server_up_or_die(8081, timeout=5)
    if not server_is_already_up:
        # cleanup leftovers
        rt_kill(image_name)
        rt_temp_dir = os.path.join(Path.home(), "rt_test")

        # RT file system preperation
        # cleanup test dir
        shutil.rmtree(rt_temp_dir)
        os.makedirs(rt_temp_dir)
        lic_dir = os.path.join(rt_temp_dir, "etc/artifactory")
        access_dir = os.path.join(rt_temp_dir, "etc/access")
        if not os.path.exists(lic_dir):
            os.makedirs(lic_dir)
        if not os.path.exists(access_dir):
            os.makedirs(access_dir)
        shutil.copyfile('tests/resources/art.lic', os.path.join(lic_dir, "artifactory.lic"))
        shutil.copyfile('tests/resources/access.config.import.yml', os.path.join(access_dir, "access.config.import.yml"))

        with open("/tmp/output.log", "a") as output:
            subprocess.call(f"docker run --detach --name {image_name} -v {rt_temp_dir}:/var/opt/jfrog/artifactory -p 8082:8082 -p 8081:8081 releases-docker.jfrog.io/jfrog/artifactory-pro:latest", shell=True, stdout=output, stderr=output)
        print("_launch_RT_server docker statrted")

        server_is_up = _await_RT_server_up_or_die(8081, timeout=600)
        print(f"_launch_RT_server after await server_is_up={server_is_up}")
        if not server_is_up:
            err = f"Error Starting Artifacotry instance, server_is_up={server_is_up}"
            raise Exception(err)
        # if server started, lets wait another 1 minute for everything to be stable
        time.sleep(60)
    else :
        print("_launch_RT_server server was already up=".format(server_is_already_up))


def rt_kill(image_name):
    try:
        with open("/tmp/image_kill.log" ,"a") as kill:
            subprocess.call(
                f"docker kill {image_name}", shell=True, stdout=kill, stderr=kill)

    except Exception as e:
        print(f"rt_kill docker kill RT container {image_name} failed, maybe system is fresh, {e}")

    try:
        with open("/tmp/image_kill.log" ,"a") as rm:
            subprocess.call(
                f"docker rm {image_name}",shell=True, stdout=rm, stderr=rm)
    except Exception as e:
        print(f"rt_kill docker remove RT container {image_name} failed, maybe system is fresh, {e}")


ArtifactsServer = namedtuple(
    "ArtifactsServer",
    ["backend_store_uri", "default_artifact_root", "artifacts_destination", "url", "process"],
)

def set_rt_token():
    # create token
    headers = {
        "Content-Type": "application/json",
    }
    # creating the rt token
    token_creation_response = requests.post("http://localhost:8081/access/api/v1/tokens",
                                            auth=HTTPBasicAuth('admin', 'password'), headers=headers)

    print(f"token_creation_response={token_creation_response}")
    if token_creation_response.status_code != 200:
        err = f"Error preparing Artifacotry instance, could not create auth token response code={token_creation_response.status_code}"
        raise Exception(err)
    token_response = token_creation_response.json()
    print(f"Create token response = {token_response}")
    access_token = token_response["access_token"]
    print(f"Create token access_token = {access_token}")

    # setting the token as var for mlflow
    os.environ['ARTIFACTORY_NO_SSL'] = 'true'
    os.environ['ARTIFACTORY_AUTH_TOKEN'] = access_token

@pytest.fixture(scope="module")
def artifacts_server():
    with tempfile.TemporaryDirectory() as tmpdir:
        port = get_safe_port()
        print("port={}".format(port))

        backend_store_uri = f'sqlite:///{os.path.join(tmpdir, "mlruns.db")}'
        artifacts_destination = ARTIFACTS_DESTINATION

        print("backend_store_uri={}".format(backend_store_uri))
        _launch_RT_server()
        # create repo if does ont exist
        try:
            headers = {
                "Content-Type": "application/json",
            }
            repo_creation_response = requests.put(f"http://{LOCALHOST}:8081/artifactory/api/repositories/test-server",
                                                  headers=headers, auth=HTTPBasicAuth('admin', 'password'),
                                                  data="{\"rclass\": \"local\",\"packageType\": \"generic\",\"repoLayoutRef\": \"simple-default\"}")

            print(f"test-server repo_creation_response={repo_creation_response}")
        except Exception as e:
            print(f"failed creating repo test-server, maybe repo exists? http response was {e}")

        set_rt_token()

        url = f"http://{LOCALHOST}:{port}"

        default_artifact_root = f"{url}/api/2.0/mlflow-artifacts/artifacts"
        process = _launch_server(
            LOCALHOST,
            port,
            backend_store_uri,
            default_artifact_root,
            ("artifactory://" + artifacts_destination),
        )
        yield ArtifactsServer(
            backend_store_uri, default_artifact_root, ARTIFACTS_DESTINATION, url, process
        )
        print(f"mlflow server process id={process}")
        process.kill()
        rt_kill('test_server_container')

def read_file(path):
    with open(path) as f:
        return f.read()

def upload_file(path, url, headers=None):
    with open(path, "rb") as f:
        res = requests.put(url, data=f, headers=headers).raise_for_status()

def download_file(url, local_path, headers=None):
    with requests.get(url, stream=True, headers=headers) as r:
        r.raise_for_status()
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert "Content-Type" in r.headers
        assert "Content-Disposition" in r.headers
        with open(local_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        return r

def test_mlflow_artifacts_rest_apis(artifacts_server, tmp_path):
    default_artifact_root = artifacts_server.default_artifact_root
    artifacts_destination = artifacts_server.artifacts_destination
    print (f"default_artifact_root={default_artifact_root}")
    print (f"artifacts_destination={artifacts_destination}")
    # Upload artifacts
    file_a = tmp_path.joinpath("a.txt")
    file_a.write_text("{\"test\":\"OK\"}")
    upload_file(file_a, f"{default_artifact_root}/a.txt")
    # check RT upload
    download_url = f"http://{artifacts_destination}/a.txt"
    rt_downloadCheck(download_url, "OK")


    file_b = tmp_path.joinpath("b.txt")
    file_b.write_text("{\"test\":\"B_OK\"}")
    upload_file(file_b, f"{default_artifact_root}/dir/b.txt")
    download_url = f"http://{artifacts_destination}/dir/b.txt"
    rt_downloadCheck(download_url, "B_OK")

    # Download artifacts
    local_dir = tmp_path.joinpath("folder")
    local_dir.mkdir()
    local_path_a = local_dir.joinpath("a.txt")
    download_file(f"{default_artifact_root}/a.txt", local_path_a)
    assert read_file(local_path_a) == "{\"test\":\"OK\"}"

    local_path_b = local_dir.joinpath("b.txt")
    download_file(f"{default_artifact_root}/dir/b.txt", local_path_b)
    assert read_file(local_path_b) == "{\"test\":\"B_OK\"}"

    # List artifacts
    resp = requests.get(default_artifact_root)
    print(f"resp.json()={resp.json()}")
    resp_string = json.dumps(resp.json())
    assert ("a.txt" in resp_string)
    assert ("\"path\": \"dir\"") in resp_string

    resp = requests.get(default_artifact_root, params={"path": "dir"})
    resp_string = json.dumps(resp.json())
    print(f"dir resp.json()={resp.json()}")

    assert ("b.txt" in resp_string)
    assert ("\"is_dir\": false" in resp_string)
    assert ("\"file_size\": 15" in resp_string)


def  test_client_experiment_artifacts(artifacts_server, tmp_path):
    url = artifacts_server.url
    artifacts_destination_client = "localhost:8082/artifactory/test-rt2"
    headers = {
        "Content-Type": "application/json",
    }
    print(f"test-rt2 repo_creation")
    repo_creation_response = requests.put(f"http://{LOCALHOST}:8081/artifactory/api/repositories/test-rt2",
                                          headers=headers, auth=HTTPBasicAuth('admin', 'password'),
                                          data="{\"rclass\": \"local\",\"packageType\": \"generic\",\"repoLayoutRef\": \"simple-default\"}")

    print(f"repo_creation_response={repo_creation_response}")

    class Mod(mlflow.pyfunc.PythonModel):
        def predict(self, ctx, inp, params=None):
            return 7

    destination = "artifactory://" + artifacts_destination_client
    print(f"test-rt2 adding files into location={destination}")
    exp_name = "myexp3"
    test_experiments = mlflow.search_experiments(filter_string=f"name = '{exp_name}'")

    if test_experiments is None or len(test_experiments) == 0:
        print(f"creating experiment={exp_name}")
        mlflow.create_experiment(exp_name, artifact_location=destination)

    mlflow.set_experiment(exp_name)
    with mlflow.start_run():
        mlflow.pyfunc.log_model("model_test", python_model=Mod())
        mlflow.log_metric("bar", 2)
    mlflow.end_run()
    # artifact: test-rt2/model_test/model/python_model.pkl
    download_url = f"http://{artifacts_destination_client}/model_test/model/python_model.pkl"
    print(f'download_url={download_url}')
    response = requests.get(download_url, auth=HTTPBasicAuth('admin', 'password'))
    print(f"response status={response.status_code}")

    assert response.status_code == 200

def test_log_artifact(artifacts_server, tmp_path):
    url = artifacts_server.url
    artifacts_destination = artifacts_server.artifacts_destination
    mlflow.set_tracking_uri(url)

    experiment_name = "test2"
    test_experiments = mlflow.search_experiments(filter_string=f"name = '{experiment_name}'")

    if test_experiments is None or len(test_experiments)==0:
        experiment_id = mlflow.create_experiment(experiment_name)
    else:
        print(f"test_experiment={test_experiments} type {type(test_experiments)}")
        actual_ids = [e.experiment_id for e in test_experiments]
        print(f"actual_ids={actual_ids} ")
        experiment_id = actual_ids[0]
    print(f"experiment_id={experiment_id} ")

    mlflow.set_experiment(experiment_name)

    tmp_path = tmp_path.joinpath("a.txt")
    tmp_path.write_text("{\"test\":\"OK\"}")

    # check RT upload
    with mlflow.start_run() as run:
        mlflow.log_artifact(tmp_path)

    mlflow.end_run()

    # check RT download
    download_url = f"http://{ARTIFACTS_DESTINATION}/{experiment_id}/{run.info.run_id}/artifacts/{tmp_path.name}"
    rt_downloadCheck(download_url)

    # check RT upload
    with mlflow.start_run() as run:
        mlflow.log_artifact(tmp_path, artifact_path="artifact_path")
    mlflow.end_run()
    # check RT download
    download_url = f"http://{ARTIFACTS_DESTINATION}/{experiment_id}/{run.info.run_id}/artifacts/artifact_path/{tmp_path.name}"
    rt_downloadCheck(download_url)



def rt_downloadCheck(download_url, content="OK"):
    print(f"download_url={download_url}")
    response = requests.get(download_url, auth=HTTPBasicAuth('admin', 'password'))
    print(f"response status={response.status_code}")
    json_res = response.json()
    print(f"response json_res={json_res}")
    assert response.status_code == 200
    assert json_res["test"] == content


def get_safe_port():
    """Returns an ephemeral port that is very likely to be free to bind to."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((LOCALHOST, 0))
    port = sock.getsockname()[1]
    sock.close()
    return port

def _await_server_up_or_die(port, timeout=30):
    """Waits until the local flask server is listening on the given port."""
    print(f"Awaiting server to be up on {LOCALHOST}:{port}")
    start_time = time.time()
    while time.time() - start_time < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            if sock.connect_ex((LOCALHOST, port)) == 0:
                print(f"Server is up on {LOCALHOST}:{port}!")
                break
        print("Server not yet up, waiting...")
        time.sleep(0.5)
    else:
        raise Exception(f"Failed to connect on {LOCALHOST}:{port} within {timeout} seconds")



def _await_RT_server_up_or_die(port, timeout=300):
    print(f"_await_RT_server_up_or_die START")
    """Waits until the local flask server is listening on the given port."""
    uri = f"http://{LOCALHOST}:8081/artifactory/api/system/ping"
    print(f"Awaiting server to be up on uri {uri}")

    start_time = time.time()
    server_is_up = False
    while time.time() - start_time < timeout:
        print(f"time.time() - start_time= {time.time() - start_time}")
        try:
            response = requests.get(uri, timeout=2)
            print("response={} {}".format(response.status_code, response.reason))
            if response is not None and response.status_code == 200:
                print(f"Server is up on {LOCALHOST}:{port}!")
                server_is_up = True
                break
            else:
                print("Server not yet up, waiting...")
                time.sleep(3)
        except Exception as err:
            print(f"Server not yet up, requests raised exception {err}, waiting...")
            time.sleep(3)
    print(f"completed waiting for server with results server_is_up={server_is_up}")
    return server_is_up