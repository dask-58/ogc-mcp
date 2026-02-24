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

headers = {"Prefer": "respond-async"}

print(f"Sending POST request to: {url}")
print("Headers:", headers)
print("\nRequest Payload:")
print(json.dumps(payload, indent=2))

try:
    response = requests.post(url, json=payload, headers=headers)

    if response.status_code == 201:
        print("\nResponse Status Code: 201 Created (Async job accepted)")
        job_url = response.headers.get("Location")
        print(f"Tracking Job at: {job_url}")

        # Poll for job completion
        import time

        while True:
            time.sleep(2)
            print("Polling status...")
            status_res = requests.get(job_url)
            status_json = status_res.json()
            status = status_json.get("status")
            print(f"Current Status: {status}")

            if status == "successful":
                print("\nJob completed successfully! Fetching results...")
                results_res = requests.get(f"{job_url}/results?f=json")
                print("Final Buffer GeoJSON Geometry:")
                try:
                    # Attempt to parse json directly
                    print(json.dumps(results_res.json(), indent=2))
                except json.JSONDecodeError:
                    # If it's returning raw text or stringified JSON rather than application/json mime
                    print(results_res.text)
                break
            elif status in ["failed", "dismissed"]:
                print(f"Job failed with status: {status}")
                break

    else:
        print(f"\nRequest failed with status code: {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"\nAn error occurred: {e}")
