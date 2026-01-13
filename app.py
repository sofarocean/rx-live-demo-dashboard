import streamlit as st
import requests
import folium
import pandas as pd
from bitstring import BitStream
import struct
from folium.plugins import MarkerCluster
from datetime import datetime, timezone, timedelta
import pytz

# Detection unpacking schema
DETECT_STRUCT = [
    ('uint32_t', 'tag_serial_no'),
    ('uint16_t', 'code_freq'),
    ('uint16_t', 'code_channel'),
    ('uint16_t', 'detection_count'),
    ('char', 'code_char'),
]


# Serializer
def serialize_tag_struct(tag: dict) -> str:
    return f"{tag['code_char']}{tag['code_freq']}-{tag['code_channel']}-{tag['tag_serial_no']}"



def format_timestamp(ts, to_local=False):
    dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
    if to_local:
        return dt.astimezone().strftime('%Y-%m-%d %H:%M %Z')
    else:
        return dt.astimezone(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')


# Decoder
def hex_to_struct(hex_data, struct_description):
    byte_data = bytes.fromhex(hex_data.strip())
    fmt = '<'
    for dt, _ in struct_description:
        fmt += {'uint32_t': 'I', 'uint16_t': 'H', 'char': 'c'}[dt]
    size = struct.calcsize(fmt)
    if len(byte_data) != size:
        return None
    values = struct.unpack(fmt, byte_data)
    return {name: val.decode() if isinstance(val, bytes) else val
            for (_, name), val in zip(struct_description, values)}

st.set_page_config(layout="wide")

# Streamlit UI
st.title("Bristlemouth Rx-LIVE Acoustic Tag Detections")

default_start = (datetime.now(timezone.utc) - timedelta(days=30)).strftime('%Y-%m-%dT%H:%MZ')

spotter_id = st.text_input("Spotter ID", "SPOT-32255C")
api_token = st.text_input("API Token", "YOUR_SPOTTER_API_TOKEN")
start_date = st.text_input("Start Date (ISO)", default_start)

# Option to show results in local browser time
local_time = st.checkbox("Show timestamps in local browser time", value=True)

# Option to exclude a reference tag from the results
exclude_ref_tag = st.checkbox("Exclude reference tag", value=True)
reference_tag = st.text_input("Reference tag to exclude", value="A69-9001-65011")

if st.button("Fetch & Decode Data"):
    url = f"https://api.sofarocean.com/api/sensor-data?token={api_token}&spotterId={spotter_id}&startDate={start_date}"
    r = requests.get(url)
    if not r.ok:
        st.error("Failed to fetch data.")
        print(r.text)
        print(url)
    else:
        detections = []
        for point in r.json().get('data', []):
            try:
                ts_raw = datetime.fromisoformat(point['timestamp'].replace('Z', '+00:00'))
                bitstream = BitStream('0x' + point['value'])
                count = bitstream.read('uintle:32')
                while bitstream.pos < bitstream.len:
                    detect_data = bitstream.read('bytes:11')
                    decoded = hex_to_struct(detect_data.hex(), DETECT_STRUCT)

                    tag_string = serialize_tag_struct(decoded)
                    if exclude_ref_tag and tag_string == reference_tag:
                        continue  # skip this detection

                    decoded.update({
                        'time': format_timestamp(point['timestamp'], to_local=local_time),
                        'dt': ts_raw,
                        'tag_string': tag_string,
                        'detection_count': decoded['detection_count'],
                        'latitude': point['latitude'],
                        'longitude': point['longitude']
                    })
                    if decoded:
                        detections.append(decoded)
            except Exception as e:
                print(e)
                continue
        st.session_state['detections'] = detections

if 'detections' in st.session_state:
    detections = st.session_state['detections']
    st.write(f"Found {len(detections)} detection(s).")

    resolution = st.radio("Chart Resolution", ["1 Day", "1 Week"], horizontal=True)

    # Create columns for Map and Chart
    col1, col2 = st.columns([1, 1])

    with col1:
        st.write("### Map")
        m = folium.Map(location=[36.7411, -121.8180], zoom_start=10)
        cluster = MarkerCluster().add_to(m)
        for d in detections:
            folium.Marker(
                location=[d['latitude'], d['longitude']],
                popup=f"{d['tag_serial_no']} ({d['code_char']}) @ {d['time']}",
            ).add_to(cluster)
        st.components.v1.html(m._repr_html_(), height=500)

    with col2:
        st.write("### Unique Tags Over Time")
        if detections:
            df = pd.DataFrame(detections)
            res_map = {"1 Day": "D", "1 Week": "W"}
            
            # Resample and count unique tag strings
            chart_data = (
                df.set_index('dt')
                .resample(res_map[resolution])['tag_string']
                .nunique()
                .reset_index()
            )
            chart_data.columns = ['Date', 'Unique Tags']
            chart_data['Date'] = chart_data['Date'].dt.strftime('%Y-%m-%d')
            st.line_chart(chart_data.set_index('Date'))
        else:
            st.info("No data to display in chart.")

    # Sort by timestamp descending
    sorted_detections = sorted(
        detections,
        key=lambda d: d['dt'],
        reverse=True
    )

    # Render the table
    st.write("### Detections Table")
    st.dataframe([
        {
            'Tag ID': d['tag_string'],
            'Pings': d['detection_count'],
            'Time': d['time'],
            'Latitude': f"{d['latitude']:.5f}",
            'Longitude': f"{d['longitude']:.5f}",
        }
        for d in sorted_detections
    ])
