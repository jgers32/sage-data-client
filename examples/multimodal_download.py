"""
Download media files and sensor data from a set of nodes over a date range, then save both to disk for later use.

Before running, save your credentials:
    sagecli login

Equivalent CLI command for the media downloads:
    sagecli download --start 2026-05-06 --end 2026-07-09 \
        --vsn W020 W01B W06C W067 \
        --task imagesampler-bottom imagesampler-left imagesampler-mobotix audio-sampler \
        --dest ./data/media \
        --layout "{date}/{vsn}/{task}/{filename}"
"""

import sage_data_client
import pandas as pd

VSNS = ["W020", "W01B", "W06C", "W067"]

MEDIA_TASKS = [
    "imagesampler-bottom",
    "imagesampler-left",
    "imagesampler-mobotix",
    "audio-sampler",
]

SENSOR_TASKS = [
    "wes-iio-bme280",
    "wes-iio-bme680",
    "wes-raingauge",
]

START = "2026-05-06"
END = "2026-07-09"

# --- Download media files ---
media_dfs = []
for vsn in VSNS:
    for task in MEDIA_TASKS:
        print("Querying media: vsn={}, task={}...".format(vsn, task))
        data = sage_data_client.query_downloads(
            start=START,
            end=END,
            filter={"vsn": vsn, "task": task},
        )
        print("  {} file(s) found.".format(len(data)))
        media_dfs.append(data.df)

media = sage_data_client.DownloadResponse(pd.concat(media_dfs, ignore_index=True))
print("\nDownloading {} media file(s)...".format(len(media)))
media.download_all(dest="./data/media", layout="{date}/{vsn}/{task}/{filename}")

# Save the manifest so it can be reloaded later without re-querying.
media.save("./data/media_manifest.csv")

# --- Query sensor timeseries ---
sensor_dfs = []
for vsn in VSNS:
    for task in SENSOR_TASKS:
        print("Querying sensor: vsn={}, task={}...".format(vsn, task))
        df = sage_data_client.query(
            start=START,
            end=END,
            filter={"vsn": vsn, "task": task},
        )
        sensor_dfs.append(df)

sensors = pd.concat(sensor_dfs, ignore_index=True)
print("\n{} sensor record(s) found.".format(len(sensors)))
sensors.to_csv("./data/sensor_data.csv", index=False)

print("\nDone. Saved:")
print("  ./data/media_manifest.csv  — media file URLs and metadata")
print("  ./data/sensor_data.csv     — sensor timeseries")
print("  ./data/media/              — downloaded media files")
