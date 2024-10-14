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
import plotly.graph_objects as go


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


def plot(data):
    fig = go.Figure()
    for row in data:
        fig.add_trace(go.Scatter(x=row['time'], y=row['snow_array'], mode='lines', name=row['name']))

    fig.update_layout(
        title="Accumulation de neige 2 jours",
        xaxis_title=None,
        yaxis_title=None,
        dragmode=False,
        margin=dict(l=10, r=10, t=40, b=40),
        legend=dict(
            orientation="h",  # Set legend horizontal
            yanchor="top",
            y=-0.2,  # Adjust the 'y' position to place it below the x-axis ticks
            xanchor="center",
            x=0.5
        ),
        )

    # Disable zooming and panning
    config = dict(
        displayModeBar=False,
        scrollZoom=False,
        doubleClick=False,
        modeBarButtonsToRemove=['zoom2d', 'pan2d', 'select2d', 'lasso2d']
    )

    return fig.to_html(full_html=False, include_plotlyjs=False, config=config)


def generate_html(sorted_mountains, fig):
    # Get the current time in Montreal timezone
    now = datetime.now(montreal_timezone)

    data = {
        "mountains": sorted_mountains,
        "last_update": now.strftime("%Y-%m-%d %H:%M"),
    }

    # Load a template from the templates directory
    template = templates.get_template('prochaine_tempete_v2.html')

    output = template.render({"data": data, "fig": fig})

    file_name = 'output/index.html'
    os.makedirs(os.path.dirname(file_name), exist_ok=True)
    with open(file_name, 'w', encoding="utf-8") as filetowrite:
        filetowrite.write(output)

    return file_name


def main():
    try:
        unsorted_mountains = populate_dict_array()

        sorted_mountains = sorted(unsorted_mountains, key=lambda x: float(x["snow"]), reverse=True)

        fig = plot(sorted_mountains)

        file_name = generate_html(sorted_mountains, fig)

        print("HTML done...")

    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        print("Error: " + str(e) + " " + str(exc_type) + " " + str(fname) + " " + str(exc_tb.tb_lineno))


if __name__ == "__main__":
    main()
