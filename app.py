import streamlit as st
import sqlite3
import pandas as pd

# DB connection
conn = sqlite3.connect('shade.db', check_same_thread=False)
cursor = conn.cursor()

# Create tables
cursor.execute('''CREATE TABLE IF NOT EXISTS Locations (
    id INTEGER PRIMARY KEY,
    name TEXT,
    type TEXT,
    capacity INTEGER,
    region TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS Bookings (
    id INTEGER PRIMARY KEY,
    user TEXT,
    location TEXT,
    time TEXT
)''')

conn.commit()

# Bulk data generator
def insert_bulk_data():
    import random

    locations = [
        "Majestic", "KR Market", "BTM Layout", "Electronic City",
        "Whitefield", "Yelahanka", "Hebbal", "Marathahalli",
        "Indiranagar", "Jayanagar", "Banashankari", "Bannerghatta",
        "Silk Board", "Hosur Road", "MG Road", "Brigade Road",
        "Rajajinagar", "Malleshwaram", "Kengeri", "Nagawara"
    ]

    extra_places = [
        "Bus Stop", "Metro Station", "College", "School",
        "Park", "Parking", "Hospital", "Mall"
    ]

    shade_types = ["Tree", "Building", "Bus Stop", "Shelter", "Umbrella"]
    regions = ["North", "South", "East", "West"]

    for i in range(1000):
        name = random.choice(locations) + " " + random.choice(extra_places) + f" {i}"
        type_ = random.choice(shade_types)
        capacity = random.randint(5, 100)
        region = random.choice(regions)

        cursor.execute(
            "INSERT INTO Locations (name, type, capacity, region) VALUES (?, ?, ?, ?)",
            (name, type_, capacity, region)
        )

    conn.commit()

# UI
st.title("🌳 Shade Locator System")

menu = ["Add Location", "Book Shade", "View Bookings"]
choice = st.sidebar.selectbox("Menu", menu)

# ---------------- ADD LOCATION ----------------
if choice == "Add Location":
    st.subheader("Add Location")

    name = st.text_input("Location Name")

    shade_types = ["Tree", "Building", "Bus Stop", "Shelter", "Umbrella"]
    type_ = st.selectbox("Shade Type", shade_types)

    capacity = st.number_input("Capacity", min_value=1)

    region = st.selectbox("Region", ["North", "South", "East", "West"])

    if st.button("Add"):
        cursor.execute(
            "INSERT INTO Locations (name, type, capacity, region) VALUES (?, ?, ?, ?)",
            (name, type_, capacity, region)
        )
        conn.commit()
        st.success("Location Added")

    if st.button("⚡ Generate 1000 Locations"):
        insert_bulk_data()
        st.success("1000 Locations Added!")

# ---------------- BOOK SHADE ----------------
elif choice == "Book Shade":
    st.subheader("🔍 Smart Shade Booking")

    user = st.text_input("User Name")
    search = st.text_input("Search Location")

    region_filter = st.selectbox(
        "Filter by Region",
        ["All", "North", "South", "East", "West"]
    )

    time = st.time_input("Select Time")

    if not time:
        st.warning("Enter time to check availability")
        st.stop()

    # Query with capacity + time filtering
    query = """
    SELECT L.name, L.capacity,
    COUNT(CASE WHEN B.time=? THEN 1 END) as booked
    FROM Locations L
    LEFT JOIN Bookings B ON L.name = B.location
    WHERE L.name LIKE ?
    """

    params = [time, f"%{search}%"]

    if region_filter != "All":
        query += " AND L.region=?"
        params.append(region_filter)

    query += """
    GROUP BY L.name
    ORDER BY L.name
    LIMIT 20
    """

    results = cursor.execute(query, params).fetchall()

    # Format results
    location_options = []

    for name, capacity, booked in results:
        status = "🟢 Available" if booked < capacity else "🔴 Full"
        display = f"{name} ({booked}/{capacity}) {status}"
        location_options.append((display, name, booked, capacity))

    # Dropdown
    if location_options:
        selected = st.selectbox(
            "Select Location",
            location_options,
            format_func=lambda x: x[0]
        )
    else:
        st.warning("No locations found")
        selected = None

    # Booking
    if st.button("Book Smart") and selected:
        name, booked, capacity = selected[1], selected[2], selected[3]

        if booked >= capacity:
            st.error("❌ Location is FULL")
        else:
            cursor.execute(
                "INSERT INTO Bookings (user, location, time) VALUES (?, ?, ?)",
                (user, name, time)
            )
            conn.commit()
            st.success("✅ Booking Successful")

# ---------------- VIEW BOOKINGS ----------------
elif choice == "View Bookings":
    st.subheader("📊 All Bookings")

    data = cursor.execute("SELECT * FROM Bookings").fetchall()

    if data:
        df = pd.DataFrame(data, columns=["ID", "User", "Location", "Time"])
        st.table(df)
    else:
        st.warning("No bookings found")
