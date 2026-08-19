"""
This example demonstrates a bulk download across multiple nodes and a date range,
with a custom file layout.

Before running, save your credentials:
    sagecli login

The equivalent CLI command for this example is:
    sagecli download --start 2026-07-01 --end 2026-07-31 \
        --vsn W020 --vsn W039 \
        --task imagesampler-top \
        --dest ./data \
        --layout "{date}/{vsn}/{task}/{filename}"
"""
import sage_data_client
import pandas as pd

# Replace with the VSNs you have access to.
# Request access at https://portal.sagecontinuum.org
VSNS = ["W020", "W039"]

start = "2026-07-01"
end = "2026-07-31"
task = "imagesampler-top"

# Query each node and combine results.
dfs = []
for vsn in VSNS:
    print("Querying {} ...".format(vsn))
    data = sage_data_client.query_downloads(
        start=start,
        end=end,
        filter={"vsn": vsn, "task": task},
    )
    dfs.append(data.df)

combined = sage_data_client.DownloadResponse(pd.concat(dfs, ignore_index=True))
print("Found {} file(s) across {} node(s).".format(len(combined), len(VSNS)))

# Preview what would be downloaded and where before committing.
for record in combined:
    print("  {} -> {}".format(record.url, record.path_for("./data", "{date}/{vsn}/{task}/{filename}")))

# Download all files with a custom layout.
# workers=4 limits concurrent requests to be polite to the server.
combined.download_all(
    dest="./data",
    layout="{date}/{vsn}/{task}/{filename}",
    workers=4,
)
