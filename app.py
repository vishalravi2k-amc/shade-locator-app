
import streamlit as st
import sqlite3

conn = sqlite3.connect('shade.db', check_same_thread=False)
cursor = conn.cursor()

# Create tables
cursor.execute("DROP TABLE IF EXISTS Locations")
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

if st.button("Add"):
    cursor.execute(
        "INSERT INTO Locations (name, type, capacity, region) VALUES (?, ?, ?, ?)",
        (name, type_, capacity, region)
    )
    conn.commit()
        st.success("Location Added")

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
    st.subheader("All Bookings")
import pandas as pd

data = cursor.execute("SELECT * FROM Bookings").fetchall()

df = pd.DataFrame(data, columns=["ID", "User", "Location", "Time"])

st.dataframe(df)
