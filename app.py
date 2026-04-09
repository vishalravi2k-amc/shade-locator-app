import streamlit as st
import folium
from streamlit_folium import st_folium
import sqlite3
import pandas as pd
from geopy.distance import geodesic
import requests
import streamlit.components.v1 as components

# ---------------- DATABASE ----------------
conn = sqlite3.connect('shade.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS Locations (
    id INTEGER PRIMARY KEY,
    name TEXT,
    type TEXT,
    capacity INTEGER,
    region TEXT,
    lat REAL,
    lon REAL
)''')

conn.commit()

# ---------------- PAGE CONFIG ----------------
st.set_page_config(layout="wide", page_title="Shade Locator")
st.markdown("<h1 style='text-align:center;'>🌳 Shade Locator System</h1>", unsafe_allow_html=True)

menu = ["Add Location", "Explore Map"]
choice = st.sidebar.selectbox("Menu", menu)

# ---------------- SEARCH FUNCTION ----------------
def get_suggestions(query):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}"
    return requests.get(url).json()[:5]

# ---------------- GPS DETECTION ----------------
def get_gps():
    gps_html = """
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
    components.html(gps_html)

params = st.query_params
user_lat = float(params.get("lat", 12.97))
user_lon = float(params.get("lon", 77.59))

# ---------------- ADD LOCATION ----------------
if choice == "Add Location":
    st.subheader("➕ Add New Shade Location")

    col1, col2 = st.columns([1,2])

    with col1:
        query = st.text_input("🔍 Search Location")

        lat, lon = None, None
        name = ""

        if query:
            results = get_suggestions(query)
            options = [r["display_name"] for r in results]

            selected = st.selectbox("Suggestions", options)

            data = next(r for r in results if r["display_name"] == selected)

            lat = float(data["lat"])
            lon = float(data["lon"])
            name = selected

            st.success(f"📍 {name}")

        type_ = st.selectbox("Shade Type", ["Tree","Building","Bus Stop"])
        capacity = st.number_input("Capacity", 1)
        region = st.selectbox("Region", ["North","South","East","West"])

        if st.button("Add Location") and lat:
            cursor.execute(
                "INSERT INTO Locations (name,type,capacity,region,lat,lon) VALUES (?,?,?,?,?,?)",
                (name, type_, capacity, region, lat, lon)
            )
            conn.commit()
            st.success("✅ Added")

    with col2:
        m = folium.Map(location=[lat or 12.97, lon or 77.59], zoom_start=13)

        if lat:
            folium.Marker([lat, lon], popup="Selected").add_to(m)

        st_folium(m, height=500)

# ---------------- EXPLORE MAP ----------------
elif choice == "Explore Map":
    st.subheader("🗺️ Smart Shade Finder")

    st.button("📍 Detect My Location", on_click=get_gps)

    st.info(f"Your Location: {user_lat}, {user_lon}")

    data = cursor.execute("SELECT name, lat, lon FROM Locations").fetchall()

    m = folium.Map(location=[user_lat, user_lon], zoom_start=13)

    # User marker
    folium.Marker(
        [user_lat, user_lon],
        popup="You",
        icon=folium.Icon(color="blue")
    ).add_to(m)

    # Find nearest
    nearest = None
    min_dist = 999999

    for name, lat, lon in data:
        dist = geodesic((user_lat, user_lon), (lat, lon)).km

        if dist < min_dist:
            min_dist = dist
            nearest = (name, lat, lon)

        folium.Marker([lat, lon], popup=name).add_to(m)

    # Highlight nearest + route
    if nearest:
        st.success(f"🧭 Nearest Shade: {nearest[0]} ({min_dist:.2f} km)")

        folium.Marker(
            [nearest[1], nearest[2]],
            popup="Nearest",
            icon=folium.Icon(color="green")
        ).add_to(m)

        # Route line
        folium.PolyLine(
            [(user_lat, user_lon), (nearest[1], nearest[2])],
            color="blue",
            weight=5
        ).add_to(m)

    st_folium(m, height=600)
