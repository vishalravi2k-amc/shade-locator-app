import streamlit as st
import folium
from streamlit_folium import st_folium
import sqlite3
import pandas as pd

# ---------------- DEBUG (IMPORTANT) ----------------
st.write("✅ App Loaded Successfully")

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

    col1, col2 = st.columns([1, 2])

    # LEFT PANEL
    with col1:
        name = st.text_input("Location Name")
        type_ = st.selectbox("Shade Type", ["Tree","Building","Bus Stop","Shelter","Umbrella"])
        capacity = st.number_input("Capacity", min_value=1)
        region = st.selectbox("Region", ["North","South","East","West"])

        st.write("Selected Lat:", st.session_state.get("lat", "Not selected"))
        st.write("Selected Lon:", st.session_state.get("lon", "Not selected"))

        if st.button("Add Location"):
            lat = st.session_state.get("lat", None)
            lon = st.session_state.get("lon", None)

            if lat is None or lon is None:
                st.error("❌ Please click on map first")
            else:
                cursor.execute(
                    "INSERT INTO Locations (name,type,capacity,region,lat,lon) VALUES (?,?,?,?,?,?)",
                    (name, type_, capacity, region, lat, lon)
                )
                conn.commit()
                st.success("✅ Location Added")

    # RIGHT PANEL (MAP)
    with col2:
        st.markdown("### 📍 Click Map to Select Location")
        st.write("---")

        try:
            m = folium.Map(location=[12.97, 77.59], zoom_start=12)

            # ADD CLICK MARKER (visual feedback)
            if "lat" in st.session_state:
                folium.Marker(
                    [st.session_state["lat"], st.session_state["lon"]],
                    popup="Selected Location",
                    icon=folium.Icon(color="blue")
                ).add_to(m)

            map_data = st_folium(
                m,
                height=500,
                use_container_width=True,
                key="map_add"
            )

            if map_data and map_data.get("last_clicked"):
                st.session_state["lat"] = map_data["last_clicked"]["lat"]
                st.session_state["lon"] = map_data["last_clicked"]["lng"]

                st.success(f"📍 Selected: {st.session_state['lat']}, {st.session_state['lon']}")

        except Exception as e:
            st.error("❌ Map failed to load")
            st.write(e)

# ---------------- BOOK SHADE ----------------
elif choice == "Book Shade":
    st.subheader("🗺️ Book Shade from Map")

    user = st.text_input("User Name")
    search = st.text_input("Search Location")

    date = st.date_input("Date")
    time_input = st.time_input("Time")

    datetime_str = f"{date.strftime('%Y-%m-%d')} {time_input.strftime('%H:%M:%S')}"

    query = """
    SELECT L.name, L.capacity, L.lat, L.lon,
    COUNT(CASE WHEN B.time=? THEN 1 END)
    FROM Locations L
    LEFT JOIN Bookings B ON L.name=B.location
    WHERE L.name LIKE ?
    GROUP BY L.name
    """

    results = cursor.execute(query, (datetime_str, f"%{search}%")).fetchall()

    m = folium.Map(location=[12.97, 77.59], zoom_start=12)

    for name, capacity, lat, lon, booked in results:
        color = "green" if booked < capacity else "red"

        folium.Marker(
            [lat, lon],
            popup=f"{name}|{booked}|{capacity}",
            icon=folium.Icon(color=color)
        ).add_to(m)

    map_data = st_folium(m, height=500, use_container_width=True, key="map_book")

    selected = None
    if map_data and map_data.get("last_object_clicked"):
        popup = map_data["last_object_clicked"]["popup"]

        if popup:
            parts = popup.split("|")
            selected = parts[0]
            booked = int(parts[1])
            capacity = int(parts[2])

            st.success(f"Selected: {selected}")

            if st.button("Book"):
                if booked >= capacity:
                    st.error("Full")
                else:
                    cursor.execute(
                        "INSERT INTO Bookings (user,location,time) VALUES (?,?,?)",
                        (user, selected, datetime_str)
                    )
                    conn.commit()
                    st.success("Booked")

# ---------------- REPORT ----------------
elif choice == "Report Issue":
    st.subheader("Report Shade Issue")

    m = folium.Map(location=[12.97, 77.59], zoom_start=12)
    map_data = st_folium(m, height=500, use_container_width=True)

    lat, lon = None, None
    if map_data and map_data.get("last_clicked"):
        lat = map_data["last_clicked"]["lat"]
        lon = map_data["last_clicked"]["lng"]

        st.success(f"Selected: {lat}, {lon}")

    issue = st.selectbox("Issue", ["No Shade","Wrong Location","Closed"])

    if st.button("Submit") and lat:
        cursor.execute(
            "INSERT INTO Reports (location,lat,lon,issue) VALUES (?,?,?,?)",
            ("User Report", lat, lon, issue)
        )
        conn.commit()
        st.success("Reported")

# ---------------- VIEW BOOKINGS ----------------
elif choice == "View Bookings":
    st.subheader("Bookings")

    data = cursor.execute("SELECT * FROM Bookings").fetchall()

    if data:
        df = pd.DataFrame(data, columns=["ID","User","Location","Time"])
        st.dataframe(df)
