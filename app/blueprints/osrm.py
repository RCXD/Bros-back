from flask import Blueprint, jsonify, request
from app.config import Config
import requests

bp = Blueprint("osrm", __name__)

"""# OSRM API
## 문서 주소: 
https://project-osrm.org/docs/v5.24.0/api/#nearest-service
  
## 서비스 설명
### Nearest Service (최근접 서비스)
주어진 좌표를 가장 가까운 n개의 일치하는 도로 정보로 스냅(가져다 붙임)시킵니다.  
- `coordinates`: 요청할 좌표 목록입니다. `{longitude}`, `{latitude}`
- `number`: 각 좌표에 대해 반환할 최근접 도로의 개수입니다. 기본값은 1입니다.
  
####  요청 예시:
`GET http://{server}/nearest/v1/{profile}/{coordinates}.json?number={number}`  
`curl 'http://router.project-osrm.org/nearest/v1/driving/13.388860,52.517037?number=3&bearings=0,20'`
  
  
## Route Service (경로 서비스)
주어진 출발지와 도착지 사이의 최적 경로를 계산합니다. (순서에 유의)  

### 요청 예시:
`GET
/route/v1/{profile}/{coordinates}?alternatives={true|false|number}&steps={true|false}&geometries={polyline|polyline6|geojson}&overview={full|simplified|false}&annotations={true|false}`  
`# Query on Berlin with three coordinates and no overview geometry returned:
curl 'http://router.project-osrm.org/route/v1/driving/13.388860,52.517037;13.397634,52.529407;13.428555,52.523219?overview=false'`  
  
옵션을 통해 경로의 세부 정보, 대안 경로, 지오메트리 형식 등을 지정할 수 있습니다.  
추가로 [general options](https://project-osrm.org/docs/v5.24.0/api/#general-options)도 지원합니다.  
  
## Table Service (거리/시간 행렬 서비스)
주어진 여러 좌표 간의 거리 및 시간을 계산합니다.  
  
### 요청 예시:
`GET /table/v1/{profile}/{coordinates}?{sources}=[{elem}...];&{destinations}=[{elem}...]&annotations={duration|distance|duration,distance}`
```
# Returns a 3x3 duration matrix:
curl 'http://router.project-osrm.org/table/v1/driving/13.388860,52.517037;13.397634,52.529407;13.428555,52.523219'

# Returns a 1x3 duration matrix
curl 'http://router.project-osrm.org/table/v1/driving/13.388860,52.517037;13.397634,52.529407;13.428555,52.523219?sources=0'

# Returns a asymmetric 3x2 duration matrix with from the polyline encoded locations `qikdcB}~dpXkkHz`:
curl 'http://router.project-osrm.org/table/v1/driving/polyline(egs_Iq_aqAppHzbHulFzeMe`EuvKpnCglA)?sources=0;1;3&destinations=2;4'

# Returns a 3x3 duration matrix:
curl 'http://router.project-osrm.org/table/v1/driving/13.388860,52.517037;13.397634,52.529407;13.428555,52.523219?annotations=duration'

# Returns a 3x3 distance matrix for CH:
curl 'http://router.project-osrm.org/table/v1/driving/13.388860,52.517037;13.397634,52.529407;13.428555,52.523219?annotations=distance'

# Returns a 3x3 duration matrix and a 3x3 distance matrix for CH:
curl 'http://router.project-osrm.org/table/v1/driving/13.388860,52.517037;13.397634,52.529407;13.428555,52.523219?annotations=distance,duration'
```

## Match Service (매치 서비스)
주어진 GPS 좌표들을 도로 네트워크 상의 경로로 매칭시킵니다.  

### 요청 예시:
`GET /match/v1/{profile}/{coordinates}?steps={true|false}&geometries={polyline|polyline6|geojson}&overview={simplified|full|false}&annotations={true|false}`

## Trip Service (여행 서비스)
주어진 여러 좌표들을 포함하는 최적의 순회 경로를 계산합니다.

### 요청 예시:
`GET /trip/v1/{profile}/{coordinates}?roundtrip={true|false}&source{any|first}&destination{any|last}&steps={true|false}&geometries={polyline|polyline6|geojson}&overview={simplified|full|false}&annotations={true|false}'`  

```
# Round trip in Berlin with three stops:
curl 'http://router.project-osrm.org/trip/v1/driving/13.388860,52.517037;13.397634,52.529407;13.428555,52.523219'
# Round trip in Berlin with four stops, starting at the first stop, ending at the last:
curl 'http://router.project-osrm.org/trip/v1/driving/13.388860,52.517037;13.397634,52.529407;13.428555,52.523219;13.418555,52.523215?source=first&destination=last'
```

## Tile Service (타일 서비스)
타일 형식으로 경로 데이터를 제공합니다. Mapbox Vector Tiles(MVT) 형식을 사용합니다.  
Mapbox GL JS와의 호환성을 위해 설계되어 있으므로, 아래 링크를 참고하세요. https://docs.mapbox.com/mapbox-gl-js/api/  

### 요청 예시:
`GET /tile/v1/{profile}/tile({x},{y},{zoom}).mvt`
```
# This fetches a Z=13 tile for downtown San Francisco:
curl 'http://router.project-osrm.org/tile/v1/car/tile(1310,3166,13).mvt'
```
"""

def osrm_request(service: str, profile: str, coordinates: str, params: dict):
    base_url = Config.OPENSTREET_URL
    url = f"{base_url}/{service}/v1/{profile}/{coordinates}"
    print(url)
    response = requests.get(url, params=params)
    print(response.json())
    return response.json()

def parse_route(response):
    '''응답결과 처리
    - code: "Ok"가 아니면 에러 반환
    - routes: 비어있으면 404 반환. 요약정보(distance, duration)와 좌표 정보(geometry), 경로 세그먼트(legs) 포함.
    '''
    if "code" in response and response["code"] != "Ok":
        return {"error": response.get("message", "Unknown error")}, 400

    routes = response.get("routes", [])
    if not routes:
        return {"error": "No routes found"}, 404
    
    route = routes[0]
    result = {
        "distance": route.get("distance"),
        "duration": route.get("duration"),
        "geometry": route.get("geometry"),
        "legs": route.get("legs"),
    }
    return result, 200

def parse_nearest(response):
    '''응답결과 처리
    - code: "Ok"가 아니면 에러 반환
    - waypoints: 비어있으면 404 반환. 각 좌표에 대한 최근접 도로 정보 포함.
    '''
    if "code" in response and response["code"] != "Ok":
        return {"error": response.get("message", "Unknown error")}, 400

    waypoints = response.get("waypoints", [])
    if not waypoints:
        return {"error": "No waypoints found"}, 404
    
    result = []
    for wp in waypoints:
        result.append({
            "name": wp.get("name"),
            "location": wp.get("location"),
            "distance": wp.get("distance"),
        })
    return {"waypoints": result}, 200

def parse_table(response):
    '''응답결과 처리
    - code: "Ok"가 아니면 에러 반환
    - durations/distances: 비어있으면 404 반환. 거리 및 시간 행렬 포함.
    '''
    if "code" in response and response["code"] != "Ok":
        return {"error": response.get("message", "Unknown error")}, 400
    durations = response.get("durations", [])
    distances = response.get("distances", [])

    if not durations or not distances:
        return {"error": "No duration/distance data found"}, 404

    result = {
        "durations": durations,
        "distances": distances,
    }
    return result, 200

def parse_match(response):
    '''응답결과 처리
    - code: "Ok"가 아니면 에러 반환
    - matchings: 비어있으면 404 반환. 매칭된 경로 정보 포함.
    '''
    if "code" in response and response["code"] != "Ok":
        return {"error": response.get("message", "Unknown error")}, 400

    matchings = response.get("matchings", [])
    if not matchings:
        return {"error": "No matchings found"}, 404
    
    result = []
    for match in matchings:
        result.append({
            "distance": match.get("distance"),
            "duration": match.get("duration"),
            "geometry": match.get("geometry"),
            "legs": match.get("legs"),
        })
    return {"matchings": result}, 200

def parse_trip(response):
    '''응답결과 처리
    - code: "Ok"가 아니면 에러 반환
    - trips: 비어있으면 404 반환. 최적 순회 경로 정보 포함.
    '''
    if "code" in response and response["code"] != "Ok":
        return {"error": response.get("message", "Unknown error")}, 400

    trips = response.get("trips", [])
    if not trips:
        return {"error": "No trips found"}, 404
    
    result = []
    for trip in trips:
        result.append({
            "distance": trip.get("distance"),
            "duration": trip.get("duration"),
            "geometry": trip.get("geometry"),
            "legs": trip.get("legs"),
        })
    return {"trips": result}, 200

def parse_tile(response):
    '''응답결과 처리
    - 타일 데이터 반환
    '''
    return response, 200

def coordinates_to_string(coords):
    '''좌표 리스트를 OSRM 형식의 문자열로 변환 (위도-경도 순서를 경도-위도 스트링으로 변경)
    - coords: [(lon, lat), (lon, lat), ...]
    - 반환값: "lat,lon;lat,lon;..."
    '''
    return ';'.join([f"{lat},{lon}" for lon, lat in coords])

@bp.get("/test")
def test():
    import polyline
    url = f'{Config.OPENSTREET_URL}/route/v1/driving/{coordinates_to_string([(37.5421042, 126.9904227), (37.5399670, 126.9899975)])}'
    print(url)
    response = requests.get(url)
    print(response.json())
    polyline_data = response.json().get("routes", [])[0].get("geometry", "")
    print('polyline:', polyline.decode(polyline_data))
    return {"message": "OSRM Blueprint is working!"}, 200

# 경로 계산요청
@bp.get("/<service>/<profile>/<coordinates>")
def navigate(service, profile, coordinates):
    print(service, profile, coordinates)
    response = osrm_request(service, profile, coordinates, request.args)
    if service == "route":
        return parse_route(response)
    elif service == "nearest":
        return parse_nearest(response)
    elif service == "table":
        return parse_table(response)
    elif service == "match":
        return parse_match(response)
    elif service == "trip":
        return parse_trip(response)
    elif service == "tile":
        return parse_tile(response)
    else:
        return {"message": "Invalid service"}, 400