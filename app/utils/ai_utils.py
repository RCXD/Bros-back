from flask import current_app
import requests

def detect_object(image_file):
    # attach-model 관련 처리 추가 필요
    url = current_app.config["AI_OBJECT_DETECTION_URL"]
    files = {"file": image_file}
    response = requests.post(f"{url}/detect", files=files)
    return response.json()

def detect_road_boundary(image_file):
    url = current_app.config["AI_ROAD_BOUNDARY_URL"]
    files = {"file": image_file}
    response = requests.post(f"{url}/detect", files=files)
    return response.json()