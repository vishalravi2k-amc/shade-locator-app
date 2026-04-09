import streamlit as st
import folium
from streamlit_folium import st_folium
import sqlite3
import pandas as pd
from geopy.distance import geodesic
import requests
import streamlit.components.v1 as components

# ---------------- DB ----------------
conn = sqlite3.connect('shade.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS locations (
    id INTEGER PRIMARY KEY,
    name TEXT,
    lat REAL,
    lon REAL
)''')

conn.commit()

# ---------------- CONFIG ----------------
st.set_page_config(layout="wide")
st.title("🌳 Shade Locator PRO")

menu = st.sidebar.selectbox("Menu", ["Add Location","Explore","Analytics"])

# ---------------- GPS ----------------
def get_gps():
    html = """
    <script>
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            const lat = pos.coords.latitude;
            const lon = pos.coords.longitude;
            const url = new URL(window.location);
            url.searchParams.set("lat", lat);
            url.searchParams.set("lon", lon);
            window.location.href = url.toString();
        }
    );
    </script>
    """
    components.html(html)

params = st.query_params
user_lat = float(params.get("lat", 12.97))
user_lon = float(params.get("lon", 77.59))

# ---------------- SEARCH ----------------
def search_location(query):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}"
    return requests.get(url).json()[:5]

# ---------------- ADD LOCATION ----------------
if menu == "Add Location":
    st.subheader("➕ Add Location")

    query = st.text_input("🔍 Search place")

    lat, lon = None, None
    name = ""

    if query:
        results = search_location(query)

        if results:
            options = [r["display_name"] for r in results]
            selected = st.selectbox("Suggestions", options)

            data = next(r for r in results if r["display_name"] == selected)

            lat = float(data["lat"])
            lon = float(data["lon"])
            name = selected

            st.success(f"📍 {name}")

    if st.button("Add Location") and lat:
        cursor.execute(
            "INSERT INTO locations (name,lat,lon) VALUES (?,?,?)",
            (name, lat, lon)
        )
        conn.commit()
        st.success("✅ Added")

    m = folium.Map(location=[lat or 12.97, lon or 77.59], zoom_start=13)

    if lat:
        folium.Marker([lat, lon], popup="Selected").add_to(m)

    st_folium(m, height=500)

# ---------------- EXPLORE ----------------
elif menu == "Explore":
    st.subheader("🗺️ Explore Shade")

    st.button("📍 Detect My Location", on_click=get_gps)
    st.info(f"Your location: {user_lat}, {user_lon}")

    data = cursor.execute("SELECT name, lat, lon FROM locations").fetchall()

    m = folium.Map(location=[user_lat, user_lon], zoom_start=13)

    folium.Marker(
        [user_lat, user_lon],
        popup="You",
        icon=folium.Icon(color="blue")
    ).add_to(m)

    nearest = None
    min_dist = 9999

    for name, lat, lon in data:
        dist = geodesic((user_lat, user_lon), (lat, lon)).km

        if dist < min_dist:
            min_dist = dist
            nearest = (name, lat, lon)

        folium.Marker([lat, lon], popup=name).add_to(m)

    if nearest:
        st.success(f"🧭 Nearest: {nearest[0]} ({min_dist:.2f} km)")

        folium.Marker(
            [nearest[1], nearest[2]],
            popup="Nearest",
            icon=folium.Icon(color="green")
        ).add_to(m)

        folium.PolyLine(
            [(user_lat, user_lon), (nearest[1], nearest[2])],
            color="blue",
            weight=4
        ).add_to(m)

    st_folium(m, height=600)

# ---------------- ANALYTICS ----------------
elif menu == "Analytics":
    st.subheader("📊 Analytics")

    df = pd.read_sql_query("SELECT * FROM locations", conn)

    st.metric("Total Locations", len(df))

    if not df.empty:
        st.map(df.rename(columns={"lat":"latitude","lon":"longitude"}))
