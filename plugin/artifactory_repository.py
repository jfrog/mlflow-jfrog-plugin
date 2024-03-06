# This plugin was developed by JFrog

import os
import posixpath
import logging

import requests
from urllib.parse import urlparse, urljoin
from mlflow.store.artifact.artifact_repo import ArtifactRepository, verify_artifact_path
from mlflow.entities import FileInfo
from mlflow.utils.file_utils import relative_path_to_artifact_path
_logger = logging.getLogger(__name__)

VERSION = "1.0.1"
class JFrogArtifactoryRepository(ArtifactRepository):
    is_plugin = True

    def __init__(self, artifact_uri):
        super(JFrogArtifactoryRepository, self).__init__(artifact_uri)
        self.debug_mode = (os.getenv("ARTIFACTORY_DEBUG", "false") == "true")
        if self.debug_mode:
            print(f"JFROG: __init__ artifact_uri={artifact_uri}")
        rt_no_ssl = os.getenv("ARTIFACTORY_NO_SSL", "false")
        uri, repo = self.extract_uri(artifact_uri, rt_no_ssl)
        self.rt_url = uri
        self.repository = repo
        self.token = os.getenv("ARTIFACTORY_AUTH_TOKEN")

        self.artifacts_delete_skip = os.getenv("ARTIFACTORY_ARTIFACTS_DELETE_SKIP", "false")
        if self.artifacts_delete_skip.lower() == "false":
            print(f"JFrog: Deletions of experiments or runs will result in artifacts deletions on Artifactory")
        else:
            print(f"JFrog: Deletions of experiments or runs will not result in artifacts deletions on Artifactory")
        if self.debug_mode:
            print("JFrog: uri = {} repo={}".format(self.rt_url, self.repository))
        if self.token is None:
            raise Exception(f"No Artifactory Token provided through environment ARTIFACTORY_AUTH_TOKEN`")




    @staticmethod
    def extract_uri(uri, rt_no_ssl):
        parsed_url = urlparse(uri)
        if parsed_url.scheme not in ["artifactory"]:
            raise Exception(f"Not a valid Artifactory URI: {uri}. "
                            f"Artifactory URI example: `artifactory://frogger.jfrog.io/artifactory/mlflow-local`")
        path_segments = parsed_url.path.strip('/').split('/')
        if len(path_segments) < 2 or path_segments[0] != 'artifactory' or not path_segments[1]:
            raise Exception(f"Not a valid Artifactory URI: {uri}. "
                            f"Artifactory URI example: `artifactory://frogger.jfrog.io/artifactory/mlflow-local`")
        protocol = "http://" if  rt_no_ssl.lower() =="true" else "https://"
        artifactory_uri = protocol +  parsed_url.netloc + "/" + path_segments.pop(0)
        repo_name = '/'.join(str(x) for x in path_segments)

        return artifactory_uri, repo_name


    def log_artifact(self, local_file, artifact_path=None):
        if self.debug_mode:
            print("JFrog: log_artifact localfile={} , artifact_path={}".format(local_file, artifact_path))
        verify_artifact_path(artifact_path)
        dest_path = os.path.basename(local_file)
        if artifact_path:
            dest_path = posixpath.join(artifact_path, os.path.basename(local_file))
        if self.debug_mode:
            print("JFrog: log_artifact dest_path={}".format(dest_path))

        with open(local_file, "rb") as f:
            r = requests.put(
                self.rt_url + "/" + self.repository + "/" + dest_path, data=f, headers=self.get_headers()
            )

    def log_artifacts(self, local_dir, artifact_path=None):
        if self.debug_mode:
            print(f"JFrog: log_artifacts parameters local_dir={local_dir}, artifact_path={artifact_path}")
        verify_artifact_path(artifact_path)
        local_dir = os.path.abspath(local_dir)
        dest_path = ""
        if artifact_path:
            dest_path = artifact_path  # posixpath.join(artifact_path, os.path.basename(local_dir))
        if self.debug_mode:
            print(f"JFrog: log_artifacts dest_path={dest_path}")

        for root, _, filenames in os.walk(local_dir):
            upload_path = dest_path
            if root != local_dir:
                rel_path = os.path.relpath(root, local_dir)
                rel_path = relative_path_to_artifact_path(rel_path)
                upload_path = dest_path + "/" + rel_path

            headers = self.get_headers()
            for f in filenames:
                with open(os.path.join(root, f), "rb") as file:
                    if self.debug_mode:
                        print(f"JFrog: log_artifacts log_artifacts.file {file} put into path {upload_path}")
                    if upload_path:
                        url = self.rt_url + "/" + self.repository + "/" + upload_path + "/" + f
                    else:
                        url = self.rt_url + "/" + self.repository + "/" + f
                    r = requests.put(url, data=file, headers=headers)
                    if self.debug_mode:
                        print(f"JFrog: log_artifacts put status {r.status_code} reason { r.reason}")

    def list_artifacts(self, path=None):
        if self.debug_mode:
            print(f"JFrog: list_artifacts in path={path} " )
        path = '' if path is None else "/" + path


        r = requests.get(self.rt_url + "/api/storage/" + self.repository + path, headers=self.get_headers())
        if r.status_code != 200:
            raise Exception(f"Error: {r.status_code} {r.reason}")
        item_info = r.json()
        if 'children' not in item_info or len(item_info['children']) == 0:
            if self.debug_mode:
                print("JFrog: list_artifacts no children in path")
            return []

        r = requests.get(
            self.rt_url + "/api/storage/" + self.repository + path + "?list&deep=0&depth=1&listFolders=1",
            headers=self.get_headers())
        if r.status_code != 200:
            raise Exception(f"Error: {r.status_code} {r.reason}")

        file_info_objects = []
        json_result = r.json()
        arr = json_result['uri'].split(self.repository + "/")
        parent_dir = arr[1] if len(arr) > 1 and arr[1] else None
        for file in r.json().get("files", []):
            file_uri = file['uri'].lstrip('/')
            filename = parent_dir + "/" + file_uri if parent_dir else file_uri
            file_info = FileInfo(filename, file['folder'], file['size'])
            file_info_objects.append(file_info)
        return file_info_objects

    def _download_file(self, remote_file_path, local_path):
        print(f"JFrog: _download_file in remote_file_path={remote_file_path}, local_path={local_path} ")

        with requests.get(
                self.rt_url + "/" + self.repository + "/" + remote_file_path, headers=self.get_headers(), stream=True) as r:
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

    def delete_artifacts(self, artifact_path=None):
        print(f"JFrog: delete skip in artifact_path={artifact_path}, is set to {self.artifacts_delete_skip}")
        if self.debug_mode:
            print("JFrog: uri = {} repo={}".format(self.rt_url, self.repository))

        if self.artifacts_delete_skip == "true":
            return

        dest_path = self.rt_url + "/" + self.repository
        if artifact_path is not None and len(artifact_path)>0:
            dest_path = dest_path + "/" + artifact_path

        if self.debug_mode:
            print(f'DELETE path: {dest_path}')
        with requests.delete(
                dest_path, headers=self.get_headers(), stream=True) as r:
            r.raise_for_status()


    def get_headers(self):
       headers = {
            "Authorization": f"Bearer {self.token}",
            "User-Agent": f"mlflow-jfrog-plugin/{VERSION}"
        }
       return headers