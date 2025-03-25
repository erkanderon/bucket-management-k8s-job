import boto3
import requests
import json
import os
import subprocess
from datetime import datetime

# MinIO erişim bilgilerinizi ve dosya yollarınızı buraya girin
access_key = os.environ["minio_access"]#"myaccesskey"
secret_key = os.environ["minio_secret"]#"mysecretkey"
endpoint_url = os.environ["minio_url"]#"http://localhost:9000"  # MinIO uç nokta URL'si (varsayılan)
bucket_name = os.environ["bucket_name"] #"test-bucket"

backup_list_url = os.environ["backup_list_url"] #"http://localhost:8001/api/get_all_pending_images"
backup_update_url = os.environ["backup_update_url"] #"http://localhost:8001/api/update"
registry = os.environ["registry"] #docker.io
registry_username = os.environ["registry_username"]
registry_password = os.environ["registry_password"]

logged_in = False

def minio_upload(access_key, secret_key, endpoint_url, bucket_name, file_path, object_name):
    """
    MinIO'ya dosya yükleme işlemi.

    Args:
        access_key (str): MinIO erişim anahtarı.
        secret_key (str): MinIO gizli anahtarı.
        endpoint_url (str): MinIO uç nokta URL'si.
        bucket_name (str): Yüklenecek dosyanın bulunduğu bucket adı.
        file_path (str): Yüklenecek dosyanın yerel dosya yolu.
        object_name (str): MinIO'daki nesne adı.
    """
    try:
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
        )

        s3_client.upload_file(file_path, bucket_name, object_name)
        print(f"{file_path} dosyası {bucket_name} bucket'ına {object_name} adıyla yüklendi.")

    except Exception as e:
        print(f"Dosya yükleme hatası: {e}")
        return "error"




def send_post_request(url, data):
    """
    Sends a POST request to the specified URL and parses the JSON response.

    Args:
        url (str): The URL to send the POST request to.
        data (dict): The data to send in the request body (as a dictionary).

    Returns:
        dict or None: The parsed JSON response as a dictionary, or None if an error occurs.
    """
    try:
        response = requests.post(url, json=data)  # Send POST request with JSON data
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Parse the JSON response
        response_json = response.json()
        return response_json

    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        return None  # Or handle the error as needed
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        return None

def send_get_request(url):
    """
    Sends a POST request to the specified URL and parses the JSON response.

    Args:
        url (str): The URL to send the POST request to.
        data (dict): The data to send in the request body (as a dictionary).

    Returns:
        dict or None: The parsed JSON response as a dictionary, or None if an error occurs.
    """
    try:
        response = requests.get(url)  # Send POST request with JSON data
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Parse the JSON response
        response_json = response.json()
        return response_json

    except requests.exceptions.RequestException as e:
        print(f"Error during request: {e}")
        return None  # Or handle the error as needed
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        return None

def execute_shell_command(command):
    """
    Executes a shell command and waits for it to finish.

    Args:
        command (str or list): The shell command to execute.

    Returns:
        subprocess.CompletedProcess: A CompletedProcess instance containing information about the command's execution.
    """
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print("Command executed successfully.")
        print("Standard Output:")
        print(result.stdout)
        print("Standard Error:")
        print(result.stderr)
        return result
    except subprocess.CalledProcessError as e:
        print(f"Command failed with error: {e}")
        print(e.stderr)
        return "error"

def login_registry(registry, username, password):
    print("Logging in Registry")
    operation = execute_shell_command("docker login -u='{}' -p='{}' {}".format(username, password, registry))

    if operation != "error":
        return "success"
    return operation

def docker_pull(name, version):
    print("Pulling image {}/{}:{}".format(registry, name, version))
    operation = execute_shell_command("docker pull {}/{}:{}".format(registry, name, version))
    
    if operation != "error":
        return "success"
    return operation

def gzip_image(name, version):
    print("Zipping image")
    today = datetime.today()
    now = today.strftime("%d_%m_%Y-%H_%M")
    operation = execute_shell_command("docker save {}/{}:{} | gzip > {}_{}_{}.tar.gz".format(registry, name, version, name, version, now))
    if operation != "error":
        operation = "success"

    return "{}_{}_{}.tar.gz".format(name, version, now), today.year, today.month, operation

response_data = send_get_request(backup_list_url)
if response_data:
    for image in response_data["data"]:
        if not logged_in:
            operation = login_registry(registry, registry_username, registry_password)
            if operation == "error":
                send_post_request(backup_update_url, {"name": image["name"], "version": image["version"], "status": "FAILED"})
                continue
            logged_in = True

        operation = docker_pull(image["name"], image["version"])
        if operation == "error":
            send_post_request(backup_update_url, {"name": image["name"], "version": image["version"], "status": "FAILED"})
            continue
        image_zip, year, month, operation = gzip_image(image["name"], image["version"])
        if operation == "error":
            send_post_request(backup_update_url, {"name": image["name"], "version": image["version"], "status": "FAILED"})
            continue
        operation = minio_upload(access_key, secret_key, endpoint_url, bucket_name, "./{}".format(image_zip), "{}/{}/{}".format(year, month, image_zip))
        if operation == "error":
            send_post_request(backup_update_url, {"name": image["name"], "version": image["version"], "status": "FAILED"})
            continue
        send_post_request(backup_update_url, {"name": image["name"], "version": image["version"], "status": "COMPLETED"})
else:
    print("Failed to get response data.")

