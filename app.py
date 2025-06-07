import streamlit as st
import requests
import folium
from bitstring import BitStream
import struct
from folium.plugins import MarkerCluster
from datetime import datetime, timezone
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

# Streamlit UI
st.title("Bristlemouth Rx-LIVE Acoustic Tag Detections")

spotter_id = st.text_input("Spotter ID", "SPOT-32255C")
api_token = st.text_input("API Token", "YOUR_SPOTTER_API_TOKEN")
start_date = st.text_input("Start Date (ISO)", "2025-06-07T00:00Z")

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
    else:
        detections = []
        m = folium.Map(location=[36.7411, -121.8180], zoom_start=10)
        cluster = MarkerCluster().add_to(m)

        for point in r.json().get('data', []):
            try:
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
                        'tag_string': tag_string,
                        'detection_count': decoded['detection_count'],
                        'latitude': point['latitude'],
                        'longitude': point['longitude']
                    })
                    if decoded:
                        detections.append(decoded)
                        folium.Marker(
                            location=[point['latitude'], point['longitude']],
                            popup=f"{decoded['tag_serial_no']} ({decoded['code_char']}) @ {point['timestamp']}",
                        ).add_to(cluster)
            except Exception as e:
                print(e)
                continue

        st.write(f"Found {len(detections)} detection(s).")
        st.write("### Detection Table")
        # Sort by timestamp descending (assumes formatted timestamp is lexically sortable)
        sorted_detections = sorted(
            detections,
            key=lambda d: d['time'],
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

        st.components.v1.html(m._repr_html_(), height=720, width=1024)
