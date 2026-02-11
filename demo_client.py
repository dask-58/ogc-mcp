import requests
import json

url = "http://localhost:5001/processes/geometry-buffer/execution"

# GeoJSON Polygon and buffer distance
payload = {
    "inputs": {
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]
            ],
        },
        "distance": 0.5,
        "resolution": 4,
    }
}

print(f"Sending POST request to: {url}")
print("\nRequest Payload:")
print(json.dumps(payload, indent=2))

try:
    response = requests.post(url, json=payload)

    if response.status_code == 200:
        print("\nResponse Status Code: 200 OK")
        print("Response Body:")
        print(json.dumps(response.json(), indent=2))
    else:
        print(f"\nRequest failed with status code: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"\nAn error occurred: {e}")
