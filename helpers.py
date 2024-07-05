import csv
from io import StringIO
import requests


def get_csv(url: str) -> list:
    # Download the CSV file
    print("Requesting CSV file... " + url)
    response = requests.get(url)
    if response.status_code == 200:
        # Convert the CSV content to a dictionary
        csv_content = StringIO(response.text)
        csv_reader = csv.DictReader(csv_content)

        # Create a list of dictionaries
        data_as_list_of_dicts = [row for row in csv_reader]

        return data_as_list_of_dicts
    else:
        print(f"Failed to download the CSV file. Status code: {response.status_code}")
        return None

