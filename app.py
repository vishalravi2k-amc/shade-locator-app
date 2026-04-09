import streamlit as st
import folium
from streamlit_folium import st_folium
import sqlite3
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
import requests

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

cursor.execute('''CREATE TABLE IF NOT EXISTS Bookings (
    id INTEGER PRIMARY KEY,
    user TEXT,
    location TEXT,
    time TEXT
)''')

conn.commit()

# ---------------- SETUP ----------------
st.set_page_config(layout="wide")
st.title("🌳 Shade Locator System")

geolocator = Nominatim(user_agent="shade_locator")

menu = ["Add Location", "Book Shade", "Find Nearest Shade"]
choice = st.sidebar.selectbox("Menu", menu)

# ---------------- FUNCTION: AUTOCOMPLETE ----------------
def get_suggestions(query):
    url = f"https://nominatim.openstreetmap.org/search?format=json&q={query}"
    response = requests.get(url).json()
    return response[:5]

# ---------------- FUNCTION: DISTANCE ----------------
def find_nearest(user_loc, locations):
    min_dist = float('inf')
    nearest = None

    for loc in locations:
        dist = geodesic(user_loc, (loc[2], loc[3])).km
        if dist < min_dist:
            min_dist = dist
            nearest = loc

    return nearest, min_dist

# ---------------- ADD LOCATION ----------------
if choice == "Add Location":
    st.subheader("➕ Add Location")

    col1, col2 = st.columns([1,2])

    with col1:
        query = st.text_input("🔍 Search Location")

        selected_lat, selected_lon = None, None

        if query:
            suggestions = get_suggestions(query)

            options = [s["display_name"] for s in suggestions]
            selected = st.selectbox("Suggestions", options)

            selected_data = next(s for s in suggestions if s["display_name"] == selected)

            selected_lat = float(selected_data["lat"])
            selected_lon = float(selected_data["lon"])

            st.success(f"📍 {selected}")

        type_ = st.selectbox("Shade Type", ["Tree","Building","Bus Stop"])
        capacity = st.number_input("Capacity", min_value=1)
        region = st.selectbox("Region", ["North","South","East","West"])

        if st.button("Add Location") and selected_lat:
            cursor.execute(
                "INSERT INTO Locations (name,type,capacity,region,lat,lon) VALUES (?,?,?,?,?,?)",
                (selected, type_, capacity, region, selected_lat, selected_lon)
            )
            conn.commit()
            st.success("✅ Location Added")

    with col2:
        map_center = [selected_lat or 12.97, selected_lon or 77.59]
        m = folium.Map(location=map_center, zoom_start=13)

        if selected_lat:
            folium.Marker([selected_lat, selected_lon], popup="Selected").add_to(m)

        st_folium(m, height=500)

# ---------------- BOOK SHADE ----------------
elif choice == "Book Shade":
    st.subheader("🗺️ Book Shade")

    data = cursor.execute("SELECT name, capacity, lat, lon FROM Locations").fetchall()

    m = folium.Map(location=[12.97,77.59], zoom_start=12)

    for name, cap, lat, lon in data:
        folium.Marker([lat, lon], popup=name).add_to(m)

    map_data = st_folium(m, height=500)

    selected = None
    if map_data and map_data.get("last_object_clicked"):
        selected = map_data["last_object_clicked"]["popup"]
        st.success(f"Selected: {selected}")

    user = st.text_input("User Name")

    if st.button("Book") and selected:
        cursor.execute(
            "INSERT INTO Bookings (user,location,time) VALUES (?,?,datetime('now'))",
            (user, selected)
        )
        conn.commit()
        st.success("✅ Booked")

# ---------------- GPS + NEAREST ----------------
elif choice == "Find Nearest Shade":
    st.subheader("📍 Find Nearest Shade")

    st.info("Allow location access in browser")

    # JS-based GPS
    gps = st.experimental_get_query_params()

    lat = st.number_input("Your Latitude", value=12.97)
    lon = st.number_input("Your Longitude", value=77.59)

    user_loc = (lat, lon)

    data = cursor.execute("SELECT name, capacity, lat, lon FROM Locations").fetchall()

    if st.button("Find Nearest"):
        nearest, dist = find_nearest(user_loc, data)

        if nearest:
            st.success(f"Nearest: {nearest[0]} ({dist:.2f} km)")

            m = folium.Map(location=[lat, lon], zoom_start=13)

            folium.Marker([lat, lon], popup="You", icon=folium.Icon(color="blue")).add_to(m)
            folium.Marker([nearest[2], nearest[3]], popup=nearest[0], icon=folium.Icon(color="green")).add_to(m)

            st_folium(m, height=500)
        else:
            st.warning("No locations available")
