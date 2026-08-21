"""
Load previously saved media and sensor data and combine them into a
multimodal DataFrame for analysis.

Run multimodal_download.py first to generate the input files.
"""
import sage_data_client
import pandas as pd

# --- Load media manifest ---
media = sage_data_client.load_downloads("./data/media_manifest.csv")

# Flatten into a DataFrame with one row per file, including local path.
media_df = media.df.copy()
media_df["local_path"] = [
    str(record.path_for("./data/media", "{date}/{vsn}/{task}/{filename}"))
    for record in media
]

# Keep only the columns useful for analysis.
media_df = media_df.rename(columns={"meta.vsn": "vsn", "meta.task": "task"})[
    ["timestamp", "vsn", "task", "local_path"]
]

# --- Load sensor timeseries ---
sensors = pd.read_csv("./data/sensor_data.csv", parse_dates=["timestamp"])
sensors["timestamp"] = pd.to_datetime(sensors["timestamp"], utc=True)

# --- Build a combined per-hour summary ---
# Resample sensor readings to hourly means, then join the count of media files captured in that same window per node.
sensors["hour"] = sensors["timestamp"].dt.floor("h")
media_df["hour"] = media_df["timestamp"].dt.floor("h")

sensor_hourly = (
    sensors.groupby(["hour", "meta.vsn", "name"])["value"]
    .mean()
    .unstack("name")
    .reset_index()
    .rename(columns={"meta.vsn": "vsn"})
)

media_counts = (
    media_df.groupby(["hour", "vsn", "task"])
    .size()
    .unstack("task", fill_value=0)
    .reset_index()
)

combined = sensor_hourly.merge(media_counts, on=["hour", "vsn"], how="outer")

print(combined.head())
print("\nColumns:", list(combined.columns))

combined.to_csv("./data/combined_hourly.csv", index=False)
print("\nSaved combined summary to ./data/combined_hourly.csv")
