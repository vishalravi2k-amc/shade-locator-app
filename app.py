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

TIME_SLOTS = ["6:00 AM", "8:00 AM", "10:00 AM", "12:00 PM", "2:00 PM", "4:00 PM", "6:00 PM"]

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

def is_slot_taken(spot_name, date, slot):
    c.execute("SELECT COUNT(*) FROM bookings WHERE spot_name=? AND date=? AND time_slot=?", (spot_name, date, slot))
    return c.fetchone()[0] > 0

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
      way["natural"="tree_row"](around:{radius_m},{lat},{lon});
    );
    out center tags;
    """
    try:
        resp = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, timeout=30)
        data = resp.json()
        spots = []
        seen = set()
        for el in data.get("elements", []):
            tags = el.get("tags", {})
            if el["type"] == "node":
                elat, elon = el.get("lat"), el.get("lon")
            else:
                center = el.get("center", {})
                elat, elon = center.get("lat"), center.get("lon")
            if not elat or not elon:
                continue

            natural = tags.get("natural", "")
            landuse = tags.get("landuse", "")
            leisure = tags.get("leisure", "")
            amenity = tags.get("amenity", "")
            tourism = tags.get("tourism", "")

            if natural in ("tree", "tree_row"):
                shade_type, color, intensity = "🌳 Tree", "#2ecc40", 85
            elif natural == "wood" or landuse == "forest":
                shade_type, color, intensity = "🌲 Forest", "#27ae60", 95
            elif leisure == "park":
                shade_type, color, intensity = "🏞️ Park", "#52c41a", 75
            elif leisure == "garden":
                shade_type, color, intensity = "🌺 Garden", "#73d13d", 70
            elif landuse == "grass":
                shade_type, color, intensity = "🌿 Grass", "#95de64", 50
            elif amenity == "shelter":
                shade_type, color, intensity = "🏠 Shelter", "#fa8c16", 90
            elif tourism == "picnic_site":
                shade_type, color, intensity = "🧺 Picnic Site", "#13c2c2", 65
            else:
                shade_type, color, intensity = "🌿 Green Area", "#52c41a", 60

            name = tags.get("name") or f"{shade_type} ({elat:.4f}, {elon:.4f})"
            key = (round(elat, 4), round(elon, 4))
            if key in seen:
                continue
            seen.add(key)

            spots.append({
                "name": name, "lat": elat, "lon": elon,
                "shade_type": shade_type, "color": color,
                "intensity": intensity, "distance": haversine(lat, lon, elat, elon)
            })

        spots.sort(key=lambda x: x["distance"])
        return spots[:40]
    except:
        return []

def gmaps_url(lat, lon):
    return f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}&travelmode=walking"

# -------------------- SESSION --------------------
for k, v in {"logged_in": False, "username": "", "user_lat": None, "user_lon": None,
             "shade_spots": [], "active_booking_key": None}.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.set_page_config(page_title="Shade Locator ULTRA", layout="wide")
st.markdown("""
<style>
.big-title { font-size:32px; font-weight:bold; text-align:center; margin-bottom:2px; }
.tip-box { background:#2a2a1e; border-left:4px solid #ffcc00; border-radius:8px; padding:10px 16px; margin-bottom:10px; font-size:14px; }
.spot-card { background:#1e2a1e; border-left:4px solid #4caf50; border-radius:8px; padding:10px 14px; margin:4px 0; }
.booking-panel { background:#1a2433; border:2px solid #2196f3; border-radius:10px; padding:14px 16px; margin:6px 0 12px 0; }
.booking-row { background:#1a2433; border-left:4px solid #2196f3; border-radius:6px; padding:10px 14px; margin-bottom:8px; }
a.nav-btn { background:#1a3a5c; border-radius:6px; padding:5px 12px; font-size:13px; color:white !important; text-decoration:none; display:inline-block; }
</style>
""", unsafe_allow_html=True)

# -------------------- LOGIN --------------------
if not st.session_state.logged_in:
    st.markdown('<div class="big-title">🌳 Shade Locator ULTRA</div>', unsafe_allow_html=True)
    st.markdown("<p style='text-align:center;color:gray;'>Tap anywhere in Bangalore — find real shade spots near you</p>", unsafe_allow_html=True)
    st.divider()
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        choice = st.radio("", ["Login", "Sign Up"], horizontal=True)
        if choice == "Sign Up":
            st.subheader("Create Account")
            nu = st.text_input("Username")
            np_ = st.text_input("Password", type="password")
            if st.button("Create Account", use_container_width=True):
                if nu and np_:
                    st.success("Created! Log in.") if add_user(nu, np_) else st.error("Username taken.")
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
    col_u, col_l = st.columns([5, 1])
    with col_u:
        st.markdown(f"<p style='color:#aaa;margin:0;'>👤 <b>{st.session_state.username}</b></p>", unsafe_allow_html=True)
    with col_l:
        if st.button("🚪 Logout"):
            for k in ["logged_in","username","user_lat","user_lon","shade_spots","active_booking_key"]:
                st.session_state[k] = False if k=="logged_in" else "" if k=="username" else None if k in ["user_lat","user_lon","active_booking_key"] else []
            st.rerun()

    st.divider()
    tab1, tab2 = st.tabs(["📍 Find Shade Near Me", "🎫 My Bookings"])

    with tab1:
        st.markdown("""
        <div class="tip-box">
            🗺️ <b>Pinch to zoom</b> anywhere in Bangalore, then <b>tap the map</b> to drop your pin.<br>
            Real trees, parks, shelters & gardens fetched live within <b>1.5 km</b>.
        </div>
        """, unsafe_allow_html=True)

        center_lat = st.session_state.user_lat or 12.9716
        center_lon = st.session_state.user_lon or 77.5946

        m = folium.Map(location=[center_lat, center_lon], zoom_start=14, tiles="CartoDB positron")

        for spot in st.session_state.shade_spots:
            folium.CircleMarker(
                location=[spot["lat"], spot["lon"]],
                radius=9, color=spot["color"], weight=2,
                fill=True, fill_color=spot["color"], fill_opacity=0.85,
                tooltip=folium.Tooltip(f"{spot['shade_type']} — {spot['name']}\n📏 {spot['distance']:.2f} km"),
                popup=folium.Popup(f"<b>{spot['name']}</b><br>{spot['shade_type']}<br>☀️ {spot['intensity']}% shade<br>📏 {spot['distance']:.2f} km", max_width=200)
            ).add_to(m)

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

        map_data = st_folium(m, width=None, height=400, key="main_map", returned_objects=["last_clicked"])

        if map_data and map_data.get("last_clicked"):
            clk = map_data["last_clicked"]
            new_lat, new_lon = clk["lat"], clk["lng"]
            if new_lat != st.session_state.user_lat or new_lon != st.session_state.user_lon:
                st.session_state.user_lat = new_lat
                st.session_state.user_lon = new_lon
                st.session_state.active_booking_key = None
                with st.spinner("🔍 Fetching shade spots from OpenStreetMap..."):
                    st.session_state.shade_spots = fetch_shade_spots(new_lat, new_lon)
                st.rerun()

        if st.session_state.user_lat:
            st.markdown(f"📍 **Your pin:** `{st.session_state.user_lat:.5f}, {st.session_state.user_lon:.5f}`")
            spots = st.session_state.shade_spots

            if spots:
                st.markdown(f"### 🌿 {len(spots)} Shade Spot(s) — Nearest First")
                st.caption("🌳 Tree | 🌲 Forest | 🏞️ Park | 🌺 Garden | 🏠 Shelter | 🧺 Picnic | 🌿 Green")
                st.divider()

                for i, spot in enumerate(spots):
                    badge = f"🟢 {spot['intensity']}%" if spot['intensity'] >= 75 else f"🟠 {spot['intensity']}%" if spot['intensity'] >= 50 else f"🔴 {spot['intensity']}%"
                    spot_key = f"{i}_{spot['lat']}_{spot['lon']}"

                    # Card + inline buttons
                    st.markdown(f"""
                    <div class="spot-card">
                        {spot['shade_type']} &nbsp;<b>{spot['name']}</b><br>
                        ☀️ Shade: {badge} &nbsp;|&nbsp; 📏 <b>{spot['distance']:.2f} km away</b>
                    </div>
                    """, unsafe_allow_html=True)

                    col_nav, col_book, col_spacer = st.columns([1, 1, 4])
                    with col_nav:
                        st.markdown(f'<a href="{gmaps_url(spot["lat"], spot["lon"])}" target="_blank" class="nav-btn">🗺️ Navigate</a>', unsafe_allow_html=True)
                    with col_book:
                        if st.button("📋 Book Spot", key=f"book_{spot_key}"):
                            # Toggle: clicking same spot closes it
                            if st.session_state.active_booking_key == spot_key:
                                st.session_state.active_booking_key = None
                            else:
                                st.session_state.active_booking_key = spot_key
                            st.rerun()

                    # ---- Inline booking panel opens RIGHT below this card ----
                    if st.session_state.active_booking_key == spot_key:
                        with st.container():
                            st.markdown(f"""
                            <div class="booking-panel">
                                <b>📋 Booking: {spot['name']}</b><br>
                                {spot['shade_type']} &nbsp;|&nbsp; ☀️ {spot['intensity']}% shade &nbsp;|&nbsp; 📏 {spot['distance']:.2f} km
                            </div>
                            """, unsafe_allow_html=True)

                            col_d, col_t = st.columns(2)
                            with col_d:
                                sel_date = st.date_input("📅 Date", min_value=datetime.today().date(), key=f"date_{spot_key}")
                            with col_t:
                                avail_slots = [s for s in TIME_SLOTS if not is_slot_taken(spot["name"], str(sel_date), s)]
                                taken_slots = [s for s in TIME_SLOTS if s not in avail_slots]

                            if avail_slots:
                                sel_slot = st.radio("⏰ Pick a time slot", avail_slots, horizontal=True, key=f"slot_{spot_key}")
                                if taken_slots:
                                    st.caption(f"Already booked: {', '.join(taken_slots)}")

                                col_confirm, col_close = st.columns(2)
                                with col_confirm:
                                    if st.button("✅ Confirm Booking", key=f"confirm_{spot_key}", use_container_width=True, type="primary"):
                                        if is_slot_taken(spot["name"], str(sel_date), sel_slot):
                                            st.error("Slot just taken! Pick another.")
                                        else:
                                            book_spot(st.session_state.username, spot["name"],
                                                      spot["lat"], spot["lon"], spot["shade_type"],
                                                      str(sel_date), sel_slot)
                                            st.success(f"🎉 Booked **{spot['name']}** at **{sel_slot}** on **{sel_date}**!")
                                            st.session_state.active_booking_key = None
                                            st.balloons()
                                            st.rerun()
                                with col_close:
                                    if st.button("✖ Cancel", key=f"close_{spot_key}", use_container_width=True):
                                        st.session_state.active_booking_key = None
                                        st.rerun()
                            else:
                                st.warning("All slots taken for this date. Try another date.")
                                if st.button("✖ Close", key=f"close2_{spot_key}"):
                                    st.session_state.active_booking_key = None
                                    st.rerun()

            else:
                st.warning("😔 No shade features found within 1.5 km. Try tapping near a park or residential area.")
        else:
            st.info("👆 Tap anywhere on the map to find real shade spots near that location.")

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
                    st.markdown(f'<a href="{gmaps_url(lat, lon)}" target="_blank" class="nav-btn">🗺️ Go</a>', unsafe_allow_html=True)
                with col_cancel:
                    st.write("")
                    st.write("")
                    if st.button("❌", key=f"cancel_{spot_name}_{date}_{time_slot}"):
                        cancel_booking(st.session_state.username, spot_name, date, time_slot)
                        st.success("Cancelled.")
                        st.rerun()

    st.divider()
    st.info("🚀 Next: GPS auto-detect + real-time shade from satellite imagery")
