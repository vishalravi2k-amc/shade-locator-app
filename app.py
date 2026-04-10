import streamlit as st
import sqlite3
import hashlib
import folium
from streamlit_folium import st_folium
from datetime import datetime
import math
import requests

# -------------------- DATABASE --------------------
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT)""")
c.execute("""
CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT, spot_name TEXT, lat REAL, lon REAL,
    shade_type TEXT, date TEXT, time_slot TEXT, booked_at TEXT
)
""")
conn.commit()

def hash_password(p): return hashlib.sha256(p.encode()).hexdigest()

def add_user(u, p):
    try:
        c.execute("INSERT INTO users VALUES (?,?)", (u, hash_password(p)))
        conn.commit(); return True
    except: return False

def login_user(u, p):
    c.execute("SELECT * FROM users WHERE username=? AND password=?", (u, hash_password(p)))
    return c.fetchone()

def book_spot(username, name, lat, lon, shade_type, date, slot):
    c.execute("INSERT INTO bookings (username,spot_name,lat,lon,shade_type,date,time_slot,booked_at) VALUES (?,?,?,?,?,?,?,?)",
              (username, name, lat, lon, shade_type, date, slot, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()

def get_bookings(username):
    c.execute("SELECT spot_name, shade_type, lat, lon, date, time_slot, booked_at FROM bookings WHERE username=? ORDER BY booked_at DESC", (username,))
    return c.fetchall()

def cancel_booking(username, spot_name, date, time_slot):
    c.execute("DELETE FROM bookings WHERE id=(SELECT id FROM bookings WHERE username=? AND spot_name=? AND date=? AND time_slot=? LIMIT 1)",
              (username, spot_name, date, time_slot))
    conn.commit()

def haversine(lat1, lon1, lat2, lon2):
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

# -------------------- OVERPASS: FETCH REAL SHADE FROM OSM --------------------
def fetch_shade_spots(lat, lon, radius_m=1500):
    query = f"""
    [out:json][timeout:25];
    (
      node["natural"="tree"](around:{radius_m},{lat},{lon});
      way["landuse"="forest"](around:{radius_m},{lat},{lon});
      way["natural"="wood"](around:{radius_m},{lat},{lon});
      way["leisure"="park"](around:{radius_m},{lat},{lon});
      way["amenity"="shelter"](around:{radius_m},{lat},{lon});
      node["amenity"="shelter"](around:{radius_m},{lat},{lon});
      way["landuse"="grass"](around:{radius_m},{lat},{lon});
      way["leisure"="garden"](around:{radius_m},{lat},{lon});
      node["tourism"="picnic_site"](around:{radius_m},{lat},{lon});
      way["highway"="pedestrian"]["trees"](around:{radius_m},{lat},{lon});
      node["natural"="tree_row"](around:{radius_m},{lat},{lon});
      way["natural"="tree_row"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """
    try:
        resp = requests.post("https://overpass-api.de/api/interpreter",
                             data={"data": query}, timeout=30)
        data = resp.json()
        spots = []
        seen = set()
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            # Get lat/lon
            if el["type"] == "node":
                elat, elon = el.get("lat"), el.get("lon")
            else:
                center = el.get("center", {})
                elat, elon = center.get("lat"), center.get("lon")
            if not elat or not elon:
                continue

            # Determine shade type and icon
            natural = tags.get("natural", "")
            landuse = tags.get("landuse", "")
            leisure = tags.get("leisure", "")
            amenity = tags.get("amenity", "")
            tourism = tags.get("tourism", "")

            if natural in ("tree", "tree_row"):
                shade_type = "🌳 Tree / Tree Row"
                color = "#2ecc40"
                intensity = 85
            elif natural == "wood" or landuse == "forest":
                shade_type = "🌲 Forest / Wood"
                color = "#27ae60"
                intensity = 95
            elif leisure == "park":
                shade_type = "🏞️ Park"
                color = "#52c41a"
                intensity = 75
            elif leisure == "garden":
                shade_type = "🌺 Garden"
                color = "#73d13d"
                intensity = 70
            elif landuse == "grass":
                shade_type = "🌿 Grass / Open Green"
                color = "#95de64"
                intensity = 50
            elif amenity == "shelter":
                shade_type = "🏠 Shelter / Canopy"
                color = "#fa8c16"
                intensity = 90
            elif tourism == "picnic_site":
                shade_type = "🧺 Picnic Site"
                color = "#13c2c2"
                intensity = 65
            else:
                shade_type = "🌿 Green Area"
                color = "#52c41a"
                intensity = 60

            name = (tags.get("name") or
                    tags.get("description") or
                    f"{shade_type} ({elat:.4f}, {elon:.4f})")

            # Deduplicate by rounding coords
            key = (round(elat, 4), round(elon, 4))
            if key in seen:
                continue
            seen.add(key)

            dist = haversine(lat, lon, elat, elon)
            spots.append({
                "name": name,
                "lat": elat, "lon": elon,
                "shade_type": shade_type,
                "color": color,
                "intensity": intensity,
                "distance": dist,
                "tags": tags
            })

        spots.sort(key=lambda x: x["distance"])
        return spots[:40]  # top 40 nearest

    except Exception as e:
        return []

def get_google_maps_url(lat, lon):
    return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=walking"

def get_osm_url(lat, lon):
    return f"https://www.openstreetmap.org/directions?engine=fossgis_osrm_foot&route=;{lat},{lon}"

# -------------------- SESSION --------------------
for k, v in {"logged_in": False, "username": "", "user_lat": None, "user_lon": None,
             "shade_spots": [], "booking_spot": None, "loading": False}.items():
    if k not in st.session_state:
        st.session_state[k] = v

# -------------------- PAGE CONFIG --------------------
st.set_page_config(page_title="Shade Locator ULTRA", layout="wide")
st.markdown("""
<style>
.big-title { font-size:32px; font-weight:bold; text-align:center; margin-bottom:2px; }
.tip-box {
    background:#2a2a1e; border-left:4px solid #ffcc00;
    border-radius:8px; padding:10px 16px; margin-bottom:10px; font-size:14px;
}
.spot-card {
    background:#1e2a1e; border-left:4px solid #4caf50;
    border-radius:8px; padding:10px 14px; margin:5px 0;
}
.booking-row {
    background:#1a2433; border-left:4px solid #2196f3;
    border-radius:6px; padding:10px 14px; margin-bottom:8px;
}
.nav-btn {
    background:#1a3a5c; border-radius:6px; padding:6px 12px;
    font-size:13px; color:white; text-decoration:none;
    display:inline-block; margin-top:4px;
}
</style>
""", unsafe_allow_html=True)

# -------------------- LOGIN --------------------
if not st.session_state.logged_in:
    st.markdown('<div class="big-title">🌳 Shade Locator ULTRA</div>', unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:gray;'>Tap anywhere in Bangalore — find real shade spots near you</p>", unsafe_allow_html=True)
    st.divider()
    col1, col2, col3 = st.columns([1,1.5,1])
    with col2:
        choice = st.radio("", ["Login", "Sign Up"], horizontal=True)
        if choice == "Sign Up":
            st.subheader("Create Account")
            nu = st.text_input("Username")
            np_ = st.text_input("Password", type="password")
            if st.button("Create Account", use_container_width=True):
                if nu and np_:
                    st.success("Created! Log in now.") if add_user(nu, np_) else st.error("Username taken.")
                else:
                    st.warning("Fill both fields.")
        else:
            st.subheader("Login")
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Login", use_container_width=True):
                if login_user(u, p):
                    st.session_state.logged_in = True
                    st.session_state.username = u
                    st.rerun()
                else:
                    st.error("Invalid credentials.")

# -------------------- MAIN APP --------------------
else:
    st.markdown('<div class="big-title">🌳 Shade Locator ULTRA</div>', unsafe_allow_html=True)
    col_u, col_l = st.columns([5,1])
    with col_u:
        st.markdown(f"<p style='color:#aaa;margin:0;'>👤 <b>{st.session_state.username}</b></p>", unsafe_allow_html=True)
    with col_l:
        if st.button("🚪 Logout"):
            for k in ["logged_in","username","user_lat","user_lon","shade_spots","booking_spot"]:
                st.session_state[k] = False if k=="logged_in" else "" if k=="username" else None if k in ["user_lat","user_lon","booking_spot"] else []
            st.rerun()

    st.divider()
    tab1, tab2 = st.tabs(["📍 Find Shade Near Me", "🎫 My Bookings"])

    with tab1:
        st.markdown("""
        <div class="tip-box">
            🗺️ <b>Pinch to zoom</b> to any street in Bangalore, then <b>tap the map</b> to drop your pin.<br>
            Real shade spots (trees, parks, shelters, forests) are fetched live from OpenStreetMap within <b>1.5 km</b>.
        </div>
        """, unsafe_allow_html=True)

        center_lat = st.session_state.user_lat or 12.9716
        center_lon = st.session_state.user_lon or 77.5946

        m = folium.Map(location=[center_lat, center_lon], zoom_start=13,
                       tiles="CartoDB positron")

        # Plot fetched shade spots
        for spot in st.session_state.shade_spots:
            folium.CircleMarker(
                location=[spot["lat"], spot["lon"]],
                radius=9,
                color=spot["color"],
                weight=2,
                fill=True,
                fill_color=spot["color"],
                fill_opacity=0.85,
                tooltip=folium.Tooltip(f"{spot['shade_type']}\n{spot['name']}\n📏 {spot['distance']:.2f} km"),
                popup=folium.Popup(
                    f"<b>{spot['name']}</b><br>{spot['shade_type']}<br>☀️ Shade: {spot['intensity']}%<br>📏 {spot['distance']:.2f} km",
                    max_width=220
                )
            ).add_to(m)

        # User pin
        if st.session_state.user_lat:
            folium.Marker(
                [st.session_state.user_lat, st.session_state.user_lon],
                tooltip="📍 Your Location",
                icon=folium.Icon(color="blue", icon="map-marker", prefix="glyphicon")
            ).add_to(m)
            folium.Circle(
                [st.session_state.user_lat, st.session_state.user_lon],
                radius=1500, color="#2196f3", fill=True, fill_opacity=0.06
            ).add_to(m)

        map_data = st_folium(m, width=None, height=430, key="main_map",
                             returned_objects=["last_clicked"])

        # On tap — fetch real OSM shade data
        if map_data and map_data.get("last_clicked"):
            clk = map_data["last_clicked"]
            new_lat, new_lon = clk["lat"], clk["lng"]
            if new_lat != st.session_state.user_lat or new_lon != st.session_state.user_lon:
                st.session_state.user_lat = new_lat
                st.session_state.user_lon = new_lon
                st.session_state.booking_spot = None
                with st.spinner("🔍 Fetching real shade spots from OpenStreetMap..."):
                    st.session_state.shade_spots = fetch_shade_spots(new_lat, new_lon, radius_m=1500)
                st.rerun()

        # Results
        if st.session_state.user_lat:
            st.markdown(f"📍 **Your pin:** `{st.session_state.user_lat:.5f}, {st.session_state.user_lon:.5f}`")

            spots = st.session_state.shade_spots
            if spots:
                st.markdown(f"### 🌿 {len(spots)} Shade Spot(s) Found — Nearest First")

                # Legend
                st.markdown("🌳 Tree &nbsp;|&nbsp; 🌲 Forest &nbsp;|&nbsp; 🏞️ Park &nbsp;|&nbsp; 🌺 Garden &nbsp;|&nbsp; 🏠 Shelter &nbsp;|&nbsp; 🧺 Picnic Site &nbsp;|&nbsp; 🌿 Green Area")
                st.divider()

                for spot in spots:
                    shade_pct = spot["intensity"]
                    badge = f"🟢 {shade_pct}%" if shade_pct >= 75 else f"🟠 {shade_pct}%" if shade_pct >= 50 else f"🔴 {shade_pct}%"
                    gmaps_url = get_google_maps_url(spot["lat"], spot["lon"])

                    col_card, col_nav, col_book = st.columns([4, 1, 1])
                    with col_card:
                        st.markdown(f"""
                        <div class="spot-card">
                            {spot['shade_type']} &nbsp;<b>{spot['name']}</b><br>
                            ☀️ Shade: {badge} &nbsp;|&nbsp; 📏 <b>{spot['distance']:.2f} km away</b>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_nav:
                        st.write("")
                        st.markdown(
                            f'<a href="{gmaps_url}" target="_blank" class="nav-btn">🗺️ Navigate</a>',
                            unsafe_allow_html=True
                        )
                    with col_book:
                        st.write("")
                        if st.button("📋 Book", key=f"book_{spot['lat']}_{spot['lon']}"):
                            st.session_state.booking_spot = spot
                            st.rerun()
            else:
                st.warning("😔 No shade features found within 1.5 km of your tap. Try tapping near a park, road with trees, or residential area.")

        else:
            st.info("👆 Tap anywhere on the map above to find real shade spots near that location.")

        # ---- Booking panel ----
        if st.session_state.booking_spot:
            spot = st.session_state.booking_spot
            st.divider()
            st.markdown(f"### 📋 Booking: **{spot['name']}**")
            st.markdown(f"{spot['shade_type']} &nbsp;|&nbsp; ☀️ {spot['intensity']}% shade &nbsp;|&nbsp; 📏 {spot['distance']:.2f} km from you")

            gmaps = get_google_maps_url(spot["lat"], spot["lon"])
            st.markdown(f'<a href="{gmaps}" target="_blank" class="nav-btn">🗺️ Open Navigation in Google Maps</a>', unsafe_allow_html=True)
            st.write("")

            col_a, col_b = st.columns(2)
            with col_a:
                sel_date = st.date_input("📅 Date", min_value=datetime.today().date(), key="book_date")
            with col_b:
                avail = [s for s in ["6:00 AM","8:00 AM","10:00 AM","12:00 PM","2:00 PM","4:00 PM","6:00 PM"]
                         if not (lambda sn,d,sl: (c.execute("SELECT COUNT(*) FROM bookings WHERE spot_name=? AND date=? AND time_slot=?",(sn,d,sl)), c.fetchone()[0]>0)[1])(spot["name"], str(sel_date), s)]
                taken  = [s for s in ["6:00 AM","8:00 AM","10:00 AM","12:00 PM","2:00 PM","4:00 PM","6:00 PM"] if s not in avail]
                if avail:
                    sel_slot = st.radio("⏰ Time Slot", avail, horizontal=True, key="book_slot")
                else:
                    st.warning("All slots taken for this date.")
                    sel_slot = None
                if taken:
                    st.caption(f"Taken: {', '.join(taken)}")

            col_c, col_d = st.columns(2)
            with col_c:
                if sel_slot and st.button("✅ Confirm Booking", use_container_width=True, type="primary"):
                    book_spot(st.session_state.username, spot["name"], spot["lat"], spot["lon"],
                              spot["shade_type"], str(sel_date), sel_slot)
                    st.success(f"🎉 Booked **{spot['name']}** on **{sel_date}** at **{sel_slot}**!")
                    st.session_state.booking_spot = None
                    st.balloons()
                    st.rerun()
            with col_d:
                if st.button("✖ Close", use_container_width=True):
                    st.session_state.booking_spot = None
                    st.rerun()

    # ==================== TAB 2 ====================
    with tab2:
        st.subheader(f"🎫 My Bookings — {st.session_state.username}")
        bookings = get_bookings(st.session_state.username)
        if not bookings:
            st.info("No bookings yet. Tap the map to find and book a shaded spot!")
        else:
            st.markdown(f"**{len(bookings)} booking(s)**")
            st.divider()
            for b in bookings:
                spot_name, shade_type, lat, lon, date, time_slot, booked_at = b
                gmaps = get_google_maps_url(lat, lon)
                col_info, col_nav, col_cancel = st.columns([4, 1, 1])
                with col_info:
                    st.markdown(f"""
                    <div class="booking-row">
                        {shade_type} <b>{spot_name}</b><br>
                        📅 {date} &nbsp;|&nbsp; ⏰ {time_slot}<br>
                        <span style='color:#666;font-size:12px;'>Booked: {booked_at}</span>
                    </div>
                    """, unsafe_allow_html=True)
                with col_nav:
                    st.write("")
                    st.write("")
                    st.markdown(f'<a href="{gmaps}" target="_blank" class="nav-btn">🗺️ Go</a>', unsafe_allow_html=True)
                with col_cancel:
                    st.write("")
                    st.write("")
                    if st.button("❌", key=f"cancel_{spot_name}_{date}_{time_slot}"):
                        cancel_booking(st.session_state.username, spot_name, date, time_slot)
                        st.success("Cancelled.")
                        st.rerun()

    st.divider()
    st.info("🚀 Next upgrade: GPS auto-detect + shade intensity from satellite imagery")
