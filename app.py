import folium
from streamlit_folium import st_folium
import streamlit as st
import sqlite3
import pandas as pd

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

cursor.execute('''CREATE TABLE IF NOT EXISTS Reports (
    id INTEGER PRIMARY KEY,
    location TEXT,
    lat REAL,
    lon REAL,
    issue TEXT
)''')

conn.commit()

# ---------------- UI ----------------
st.set_page_config(layout="wide")
st.title("🌳 Shade Locator System")

menu = ["Add Location", "Book Shade", "Report Issue", "View Bookings"]
choice = st.sidebar.selectbox("Menu", menu)

# ---------------- ADD LOCATION ----------------
if choice == "Add Location":
    st.subheader("Add Location")

    name = st.text_input("Location Name")
    type_ = st.selectbox("Shade Type", ["Tree","Building","Bus Stop","Shelter","Umbrella"])
    capacity = st.number_input("Capacity", min_value=1)
    region = st.selectbox("Region", ["North","South","East","West"])

    st.markdown("### 📍 Click on map to select location")

    m = folium.Map(location=[12.97, 77.59], zoom_start=12)

    map_data = st_folium(
        m,
        height=500,
        width=700,
        key="add_map"
    )

    lat, lon = 12.97, 77.59

    if map_data and map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lon = map_data["last_clicked"]["lng"]
        st.success(f"📍 Selected: {lat}, {lon}")

    if st.button("Add Location"):
        cursor.execute(
            "INSERT INTO Locations (name,type,capacity,region,lat,lon) VALUES (?,?,?,?,?,?)",
            (name,type_,capacity,region,lat,lon)
        )
        conn.commit()
        st.success("✅ Location Added")

# ---------------- BOOK SHADE ----------------
elif choice == "Book Shade":
    st.subheader("🗺️ Select Shade from Map")

    user = st.text_input("User Name")
    search = st.text_input("Search Location")

    region_filter = st.selectbox("Region", ["All","North","South","East","West"])

    date = st.date_input("Date")
    time_input = st.time_input("Time")

    datetime_str = f"{date.strftime('%Y-%m-%d')} {time_input.strftime('%H:%M:%S')}"

    query = """
    SELECT L.name, L.capacity, L.lat, L.lon,
    COUNT(CASE WHEN B.time=? THEN 1 END)
    FROM Locations L
    LEFT JOIN Bookings B ON L.name=B.location
    WHERE L.name LIKE ?
    """

    params = [str(datetime_str), f"%{search}%"]

    if region_filter != "All":
        query += " AND L.region=?"
        params.append(region_filter)

    query += " GROUP BY L.name LIMIT 50"

    results = cursor.execute(query, params).fetchall()

    st.markdown("### 👉 Click a marker to select location")

    m = folium.Map(location=[12.97,77.59], zoom_start=12)

    for name, capacity, lat, lon, booked in results:
        color = "green" if booked < capacity else "red"
        folium.Marker(
            [lat, lon],
            popup=f"{name}|{booked}|{capacity}",
            icon=folium.Icon(color=color)
        ).add_to(m)

    map_data = st_folium(
        m,
        height=500,
        width=900,
        key="book_map"
    )

    selected_name = None
    selected_booked = 0
    selected_capacity = 0

    if map_data and map_data.get("last_object_clicked"):
        popup = map_data["last_object_clicked"]["popup"]

        if popup and "|" in popup:
            parts = popup.split("|")
            selected_name = parts[0]
            selected_booked = int(parts[1])
            selected_capacity = int(parts[2])

            st.success(f"📍 Selected: {selected_name}")

    if st.button("Book Selected Location") and selected_name:
        if selected_booked >= selected_capacity:
            st.error("❌ Location Full")
        else:
            cursor.execute(
                "INSERT INTO Bookings (user,location,time) VALUES (?,?,?)",
                (user,selected_name,datetime_str)
            )
            conn.commit()
            st.success("✅ Booking Successful")

# ---------------- REPORT ISSUE ----------------
elif choice == "Report Issue":
    st.subheader("⚠️ Report Shade Issue")

    st.markdown("### 📍 Click map to report issue")

    m = folium.Map(location=[12.97,77.59], zoom_start=12)

    map_data = st_folium(
        m,
        height=500,
        width=700,
        key="report_map"
    )

    lat, lon = None, None

    if map_data and map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lon = map_data["last_clicked"]["lng"]
        st.success(f"📍 Selected: {lat}, {lon}")

    issue = st.selectbox("Issue", ["No Shade","Wrong Location","Closed"])

    if st.button("Submit Report") and lat:
        cursor.execute(
            "INSERT INTO Reports (location,lat,lon,issue) VALUES (?,?,?,?)",
            ("User Report",lat,lon,issue)
        )
        conn.commit()
        st.success("✅ Report Submitted")

# ---------------- VIEW BOOKINGS ----------------
elif choice == "View Bookings":
    st.subheader("📊 All Bookings")

    data = cursor.execute("SELECT * FROM Bookings").fetchall()

    if data:
        df = pd.DataFrame(data, columns=["ID","User","Location","Time"])
        st.dataframe(df)
    else:
        st.warning("No bookings found")
