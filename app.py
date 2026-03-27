import streamlit as st
import sqlite3

conn = sqlite3.connect('shade.db', check_same_thread=False)
cursor = conn.cursor()

st.title("🌳 Shade Locator System")

menu = ["Add Location", "Book Shade", "View Bookings"]
choice = st.sidebar.selectbox("Menu", menu)

# Add Location
if choice == "Add Location":
    st.subheader("Add Location")
    name = st.text_input("Location Name")
    type_ = st.text_input("Shade Type")
    capacity = st.number_input("Capacity", min_value=1)

    if st.button("Add"):
        cursor.execute("INSERT INTO Locations (name, type, capacity) VALUES (?, ?, ?)",
                       (name, type_, capacity))
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
    data = cursor.execute("SELECT * FROM Bookings").fetchall()
    for row in data:
        st.write(row)
