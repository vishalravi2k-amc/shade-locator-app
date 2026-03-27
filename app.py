
import streamlit as st
import sqlite3
import pandas as pd
conn = sqlite3.connect('shade.db', check_same_thread=False)
cursor = conn.cursor()

def insert_bulk_data():
    import random

    locations = [
        "Majestic Bus Stand", "KR Market", "BTM Layout", "Electronic City",
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

# Create tables

conn.commit()
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

st.title("🌳 Shade Locator System")

menu = ["Add Location", "Book Shade", "View Bookings"]
choice = st.sidebar.selectbox("Menu", menu)

# Add Location
if choice == "Add Location":
    st.subheader("Add Location")
    name = st.text_input("Location Name")
    shade_types = ["Tree", "Building", "Bus Stop", "Shelter", "Umbrella"]

    type_ = st.selectbox("Shade Type", shade_types)
    capacity = st.number_input("Capacity", min_value=1)

region = st.selectbox("Region", ["North", "South", "East", "West"])

if choice == "Add Location":
    st.subheader("Add Location")

    name = st.text_input("Location Name")

    shade_types = ["Tree", "Building", "Bus Stop", "Shelter", "Umbrella"]
    type_ = st.selectbox("Shade Type", shade_types)

    capacity = st.number_input("Capacity", min_value=1)

    region = st.selectbox("Region", ["North", "South", "East", "West"])

    # ✅ NORMAL ADD BUTTON
    if st.button("Add"):
        cursor.execute(
            "INSERT INTO Locations (name, type, capacity, region) VALUES (?, ?, ?, ?)",
            (name, type_, capacity, region)
        )
        conn.commit()
        st.success("Location Added")

    # ✅ BULK GENERATE BUTTON (SEPARATE)
    if st.button("⚡ Generate 1000 Locations"):
        insert_bulk_data()
        st.success("1000 Locations Added!")
# Book Shade
elif choice == "Book Shade":
    st.subheader("Book Shade")
    user = st.text_input("User Name")

    locations = [row[0] for row in cursor.execute("SELECT name FROM Locations").fetchall()]
    selected_location = st.selectbox("Select Location", locations)

    time = st.text_input("Time")

    if st.button("Book"):
        cursor.execute("INSERT INTO Bookings (user, location, time) VALUES (?, ?, ?)",
                       (user, selected_location, time))
        conn.commit()
        st.success("Booking Done")

# View Bookings
elif choice == "View Bookings":
    st.subheader("📊 All Bookings")

    data = cursor.execute("SELECT * FROM Bookings").fetchall()

    if data:
        df = pd.DataFrame(data, columns=["ID", "User", "Location", "Time"])
        st.table(df)
    else:
        st.warning("No bookings found")


