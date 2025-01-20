# -*- coding: utf-8 -*-
# !/usr/bin/python3

from datetime import datetime
import time
import sys
import pytz
from jinja2 import Environment, FileSystemLoader
from helpers import get_csv
import os
from mountains import mountains
from highcharts_core.chart import Chart

import openmeteo_requests

import requests_cache
import pandas as pd
from retry_requests import retry


base_api_url = "https://spotwx.io/api.php"
api_key = os.environ['API_KEY']

models = [
    ["hrdps_continental", "hrdps_continental"],
    ["rdps", "rdps_10km"],
    ["gdps", "gem_glb_15km"],
    ["nam", "nam_awphys"],
    ["gfs", "gfs_pgrb2_0p25_f"],
]

model_for_data = "hrdps_continental"

# Set the timezone to Montreal
montreal_timezone = pytz.timezone('America/Toronto')

# Create a Jinja2 environment and specify the templates directory
templates = Environment(loader=FileSystemLoader('templates'))


def get_model_for_data(model_str):
    for model in models:
        if model[0] == model_str:
            return model


def plot_highcharts_snow_depth():
    try:
        snow_array = []
        for row in mountains:
            snow_array.append({"name": row['name'], "data": (row['snow_depth']['snow_depth'] * 100).tolist()})

        time_array = mountains[0]['snow_depth']['date']

        str_time_array = []
        current_time = 0
        for i in range(len(time_array)):
            datetime_i = datetime.astimezone(time_array[i].to_pydatetime(), montreal_timezone)
            str_time_array.append(datetime_i.strftime("%b %d %H:%M"))

            if datetime.now(montreal_timezone) > datetime_i:
                current_time = i

        time_array = str_time_array

        chart = Chart(container='snow_depth_chart', options={
            "chart": {"type": "line",
                      "height": 500,  # Set minimum height here
                      "style": {
                          "minHeight": "500px"  # Ensure it's respected across various devices
                      }
                      },
            "title": {"text": "Neige au sol"},
            "xAxis": {
                "categories": time_array,
                "plotLines": [{
                    "color": '#FF0000', # Red
                    "width": 1,
                    "value": current_time
                    }]
            },
            "yAxis": {"title": {"text": "Neige (cm)"}},
            "series": snow_array,
            "legend": {"enabled": False},  # Disable legend
        })

        return chart.to_js_literal()
    except Exception as e:
        print("Error in plot_highcharts_snow_depth: " + str(e))
        return ""


def get_snow_depth_array():
    lat_array = []
    lon_array = []
    timezone_array = []
    snow_depth_array = []

    try:
        for mountain in mountains:
            lat_array.append(float(mountain["lat"]))
            lon_array.append(float(mountain["lon"]))
            timezone_array.append("America/Toronto")

        # Setup the Open-Meteo API client with cache and retry on error
        cache_session = requests_cache.CachedSession('.cache', expire_after=3600)
        retry_session = retry(cache_session, retries=5, backoff_factor=0.2)
        openmeteo = openmeteo_requests.Client(session=retry_session)

        # Make sure all required weather variables are listed here
        # The order of variables in hourly or daily is important to assign them correctly below
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat_array,
            "longitude": lon_array,
            "hourly": "snow_depth",
            "timezone": timezone_array,
            "past_days": 3,
            "forecast_days": 3,
            "models": "best_match"
        }
        responses = openmeteo.weather_api(url, params=params)

        for i, response in enumerate(responses):
            # Process hourly data. The order of variables needs to be the same as requested.
            hourly = response.Hourly()
            hourly_snow_depth = hourly.Variables(0).ValuesAsNumpy()

            hourly_data = {"date": pd.date_range(
                start=pd.to_datetime(hourly.Time(), unit="s", utc=True),
                end=pd.to_datetime(hourly.TimeEnd(), unit="s", utc=True),
                freq=pd.Timedelta(seconds=hourly.Interval()),
                inclusive="left"
            )}

            hourly_data["snow_depth"] = hourly_snow_depth

            mountains[i]["snow_depth"] = hourly_data

            current_snow_depth = 0.0
            current_time = datetime.now(montreal_timezone)
            for j in range(len(hourly_data["snow_depth"])):
                if hourly_data["date"][j] <= current_time:
                    current_snow_depth = hourly_data["snow_depth"][j]

            mountains[i]["current_snow_depth"] = round(current_snow_depth * 100.0)

    except Exception as e:
        print("Error in snow depth: " + str(e))


def populate_dict_array():
    for mountain in mountains:

        # Get the current time in the Montreal timezone
        current_time = datetime.now(montreal_timezone)

        # Get the UTC offset as a timedelta
        utc_offset_timedelta = current_time.utcoffset()

        # Extract hours from the timedelta and convert it to a string
        utc_offset_hours = str(int(utc_offset_timedelta.total_seconds() // 3600))

        # Add a '+' sign for positive UTC offsets
        if utc_offset_timedelta.total_seconds() >= 0:
            utc_offset_hours = '+' + utc_offset_hours

        url = base_api_url + "?key=" + api_key + "&lat=" + mountain["lat"] + "&lon=" + mountain["lon"] + "&model=" + \
              get_model_for_data(model_for_data)[1] + "&tz=" + utc_offset_hours + "&format=csv"

        csv_data = get_csv(url)

        mountain["snow_array"] = []
        mountain["time"] = []
        for row in csv_data:
            mountain["snow_array"].append(float(row["SQP"]))

            date_string = row["DATETIME"]
            date_format = "%Y/%m/%d %H:%M"
            date_obj = datetime.strptime(date_string, date_format)
            mountain["time"].append(date_obj)

        mountain["snow"] = csv_data[len(csv_data) - 1]["SQP"]
        mountain["rain"] = csv_data[len(csv_data) - 1]["RQP"]
        mountain["freezing_rain"] = csv_data[len(csv_data) - 1]["FQP"]
        mountain["ice_pellets"] = csv_data[len(csv_data) - 1]["IQP"]

        mountain["rdps_link"] = "https://spotwx.com/products/grib_index.php?model=" + get_model_for_data("rdps")[
            1] + "&lat=" + mountain["lat"] + "&lon=" + mountain["lon"] + "&tz=America%2FMontreal&label=" + mountain[
                                    "name"]
        mountain["rdps_link"] = mountain["rdps_link"].replace(" ", "%20")

        mountain["hrdps_link"] = "https://spotwx.com/products/grib_index.php?model=" + get_model_for_data("hrdps_continental")[
            1] + "&lat=" + mountain["lat"] + "&lon=" + mountain["lon"] + "&tz=America%2FMontreal&label=" + mountain[
                                     "name"]
        mountain["hrdps_link"] = mountain["hrdps_link"].replace(" ", "%20")

        mountain["gdps_link"] = "https://spotwx.com/products/grib_index.php?model=" + get_model_for_data("gdps")[
            1] + "&lat=" + mountain["lat"] + "&lon=" + mountain["lon"] + "&tz=America%2FMontreal&label=" + mountain[
                                    "name"]
        mountain["gdps_link"] = mountain["gdps_link"].replace(" ", "%20")

        mountain["nam_link"] = "https://spotwx.com/products/grib_index.php?model=" + get_model_for_data("nam")[
            1] + "&lat=" + mountain["lat"] + "&lon=" + mountain["lon"] + "&tz=America%2FMontreal&label=" + mountain[
                                   "name"]
        mountain["nam_link"] = mountain["nam_link"].replace(" ", "%20")

        mountain["gfs_link"] = "https://spotwx.com/products/grib_index.php?model=" + get_model_for_data("gfs")[
            1] + "&lat=" + mountain["lat"] + "&lon=" + mountain["lon"] + "&tz=America%2FMontreal&label=" + mountain[
                                   "name"]
        mountain["gfs_link"] = mountain["gfs_link"].replace(" ", "%20")

        mountain["google_map_link"] = "https://www.google.com/maps?z=12&t=k&q=""" + mountain["lat"] + """,""" + \
                                      mountain[
                                          "lon"] + """&ll=""" + mountain["lat"] + """,""" + mountain["lon"]

        mountain["google_map_link"] = mountain["google_map_link"].replace(" ", "%20")

        mountain["windy_link"] = ("https://www.windy.com/" + mountain["lat"] + "/" + mountain["lon"] + "?" +
                                  mountain["lat"] + "," + mountain["lon"] + ",11")

        print(mountain["name"] + " done...")

        time.sleep(0.5)

    return mountains


def plot_highcharts():
    try:
        snow_array = []
        for row in mountains:
            snow_array.append({"name": row['name'], "data": row['snow_array']})

        time_array = mountains[0]['time']

        current_time = 0
        for i in range(len(time_array)):
            if datetime.now(montreal_timezone).replace(microsecond=0, second=0, minute=0, tzinfo=None) > time_array[i]:
                current_time = i

            time_array[i] = time_array[i].strftime("%b %d %H:%M")

        chart = Chart(container='my_chart', options={
            "chart": {"type": "line",
                      "height": 500,  # Set minimum height here
                      "style": {
                          "minHeight": "500px"  # Ensure it's respected across various devices
                      }
                      },
            "title": {"text": "Accumulation de neige 2 jours"},
            "xAxis": {"categories": time_array,
                      "plotLines": [{
                          "color": '#FF0000',  # Red
                          "width": 1,
                          "value": current_time
                      }]
                      },
            "yAxis": {"title": {"text": "Neige (cm)"}},
            "series": snow_array,
            "legend": {"enabled": False},  # Disable legend
        })

        return chart.to_js_literal()
    except Exception as e:
        print("Error in plot_highcharts: " + str(e))
        return ""


def generate_html(fig, snow_depth_plot):
    # Get the current time in Montreal timezone
    now = datetime.now(montreal_timezone)

    data = {
        "mountains": mountains,
        "last_update": now.strftime("%Y-%m-%d %H:%M"),
    }

    # Load a template from the templates directory
    template = templates.get_template('prochaine_tempete_v2.html')

    output = template.render({"data": data, "fig": fig, "snow_depth_plot": snow_depth_plot})

    file_name = 'output/index.html'
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    with open(file_name, 'w', encoding="utf-8") as filetowrite:
        filetowrite.write(output)

    return file_name


def main():
    try:
        populate_dict_array()
        get_snow_depth_array()

        mountains.sort(key=lambda x: x["snow"], reverse=True)

        fig = plot_highcharts()
        snow_depth_plot = plot_highcharts_snow_depth()

        file_name = generate_html(fig, snow_depth_plot)

        print("HTML done...")

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("Error: " + str(e) + " " + str(exc_type) + " " + str(fname) + " " + str(exc_tb.tb_lineno))


if __name__ == "__main__":
    main()
