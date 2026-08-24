import requests
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

API_BASE_URL = "https://api.tcgdex.net/v2/en/sets"
REQUEST_TIMEOUT = 30


def fetch_release_date(set_id):
    response = requests.get(f"{API_BASE_URL}/{set_id}", timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json().get("releaseDate")

def update_sets_json():
    filename = "sets.json"

    try:
        print("Fetching data from API...")
        response = requests.get(API_BASE_URL, timeout=REQUEST_TIMEOUT)
        # Raise an exception if the request was unsuccessful
        response.raise_for_status()
        
        # Parse the JSON response
        data = response.json()

        filtered_sets = [{"id": item["id"], "name": item["name"]} for item in data]

        # TCGdex only includes releaseDate on the individual set endpoint.
        # Special sets use .5 IDs and intentionally keep manual release dates.
        regular_sets = [item for item in filtered_sets if ".5" not in item["id"]]
        with ThreadPoolExecutor(max_workers=10) as executor:
            requests_by_id = {
                executor.submit(fetch_release_date, item["id"]): item
                for item in regular_sets
            }
            for request in as_completed(requests_by_id):
                item = requests_by_id[request]
                release_date = request.result()
                if release_date:
                    item["releaseDate"] = release_date

        # Writing to 'w' mode automatically clears the file before writing
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(filtered_sets, f, indent=2)

        dated_sets = sum("releaseDate" in item for item in filtered_sets)
        print(
            f"Successfully updated {filename} with {len(filtered_sets)} sets "
            f"and {dated_sets} release dates."
        )

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    update_sets_json()
