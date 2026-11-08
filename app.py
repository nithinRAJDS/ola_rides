import streamlit as st
import plotly.express as px
import ola_data as od

st.set_page_config(page_title="OLA Ride Analytics", page_icon="🚖", layout="wide")

GREEN, BLUE, RED, AMBER, GREY = "#92D050", "#156082", "#C0504D", "#E97132", "#7F7F7F"
STATUS_COLORS = {"Success": GREEN, "Canceled by Driver": RED, "Canceled by Customer": AMBER, "Driver Not Found": GREY}


def cr(v): return f"₹{v/1e7:,.2f} Cr"
def lk(v): return f"₹{v/1e5:,.2f} L"


@st.cache_data
def get_data():
    return od.load("ola_cleaned.csv")


raw = get_data()

# ---------------- Sidebar filters
st.sidebar.title("🚖 OLA Analytics")
st.sidebar.caption("July 2024 · Bengaluru")
vehicles = st.sidebar.multiselect("Vehicle type", od.VEHICLE_ORDER, default=od.VEHICLE_ORDER)
statuses = st.sidebar.multiselect("Booking status", od.STATUS_ORDER, default=od.STATUS_ORDER)
pays = st.sidebar.multiselect("Payment method (completed rides)", ["Cash", "UPI", "Credit Card", "Debit Card"],
                              default=["Cash", "UPI", "Credit Card", "Debit Card"])
dmin, dmax = raw.Day.min().date(), raw.Day.max().date()
dr = st.sidebar.date_input("Date range", (dmin, dmax), min_value=dmin, max_value=dmax)

df = od.apply_filters(raw, vehicles, statuses, pays, dr)
st.title("OLA Ride-Sharing Dashboard")
if df.empty:
    st.warning("No bookings match the current filters.")
    st.stop()

k = od.kpis(df)
tab_over, tab_veh, tab_rev, tab_can, tab_rat, tab_data = st.tabs(
    ["Overall", "Vehicle Type", "Revenue", "Cancellation", "Ratings", "Data"])

# ---------------- Overall
with tab_over:
    c = st.columns(5)
    c[0].metric("Total bookings", f"{k['bookings']:,}")
    c[1].metric("Success rate", f"{k['success_rate']:.1%}")
    c[2].metric("Total booking value", cr(k["total_value"]))
    c[3].metric("Successful booking value", cr(k["success_value"]))
    c[4].metric("Avg ride distance", f"{k['avg_distance']:.1f} km")
    a, b = st.columns([1, 2])
    fig = px.pie(od.status_counts(df), names="Status", values="Bookings", hole=0.55,
                 color="Status", color_discrete_map=STATUS_COLORS, title="Booking status")
    a.plotly_chart(fig, use_container_width=True)
    d = od.daily(df)
    fig = px.line(d, x="Day", y="Bookings", title="Daily bookings", markers=True)
    fig.update_traces(line_color=BLUE)
    b.plotly_chart(fig, use_container_width=True)
    h = od.hourly(df)
    fig = px.bar(h, x="Hour", y="Bookings", title="Bookings by hour of day")
    fig.update_traces(marker_color=BLUE)
    st.plotly_chart(fig, use_container_width=True)

# ---------------- Vehicle type
with tab_veh:
    vt = od.vehicle_table(df)
    st.dataframe(
        vt.style.format({"Total Booking Value": lk, "Success Booking Value": lk, "Avg Distance (km)": "{:.1f}",
                         "Total Distance (km)": "{:,.0f}", "Success Rate": "{:.1%}",
                         "Avg Driver Rating": "{:.2f}", "Avg Customer Rating": "{:.2f}"}),
        use_container_width=True)
    a, b = st.columns(2)
    a.plotly_chart(px.bar(vt.reset_index(), x="Vehicle_Type", y="Avg Distance (km)",
                          title="Average distance per completed ride", color_discrete_sequence=[BLUE]),
                   use_container_width=True)
    b.plotly_chart(px.bar(vt.reset_index(), x="Vehicle_Type", y="Total Distance (km)",
                          title="Total distance travelled", color_discrete_sequence=[GREEN]),
                   use_container_width=True)
    st.info("Auto rides average ~10 km versus ~25 km for every other vehicle type, while the fare per ride is "
            "similar (~₹550). That implies a much higher fare per km for Autos and is worth validating at source.")

# ---------------- Revenue
with tab_rev:
    c = st.columns(4)
    c[0].metric("Revenue (successful)", cr(k["success_value"]))
    c[1].metric("Avg value / completed ride", f"₹{k['avg_value']:.0f}")
    c[2].metric("Value lost to failed bookings", cr(k["lost_value"]))
    pr = od.payment_revenue(df)
    cash = pr.loc[pr.Payment_Method == "Cash", "Revenue"].sum() / pr.Revenue.sum() if len(pr) else 0
    c[3].metric("Cash share of revenue", f"{cash:.1%}")
    d = od.daily(df)
    st.plotly_chart(px.line(d, x="Day", y="Revenue", title="Daily revenue (successful rides, ₹)", markers=True,
                            color_discrete_sequence=[GREEN]), use_container_width=True)
    a, b = st.columns(2)
    a.plotly_chart(px.pie(pr, names="Payment_Method", values="Revenue", hole=0.5,
                          title="Revenue by payment method"), use_container_width=True)
    tl = od.top_locations(df, 10).sort_values("Revenue")
    b.plotly_chart(px.bar(tl, x="Revenue", y="Pickup_Location", orientation="h",
                          title="Top 10 pickup locations by revenue", color_discrete_sequence=[BLUE]),
                   use_container_width=True)

# ---------------- Cancellation
with tab_can:
    counts = df.Booking_Status.value_counts()
    c = st.columns(3)
    for col, s_ in zip(c, ["Canceled by Driver", "Canceled by Customer", "Driver Not Found"]):
        n = int(counts.get(s_, 0))
        col.metric(s_, f"{n:,}", f"{n/len(df):.1%} of bookings", delta_color="off")
    a, b = st.columns(2)
    cc = od.cancel_reasons(df, "Customer")
    dd = od.cancel_reasons(df, "Driver")
    a.plotly_chart(px.bar(cc.sort_values("Count"), x="Count", y="Reason", orientation="h",
                          title="Customer cancellation reasons", color_discrete_sequence=[AMBER]),
                   use_container_width=True)
    b.plotly_chart(px.bar(dd.sort_values("Count"), x="Count", y="Reason", orientation="h",
                          title="Driver cancellation reasons", color_discrete_sequence=[RED]),
                   use_container_width=True)
    fv = od.failure_by_vehicle(df)
    st.plotly_chart(px.bar(fv, x="Vehicle_Type", y="Percent", color="Status", barmode="stack",
                           title="Failed bookings by vehicle type (% of bookings)",
                           color_discrete_map=STATUS_COLORS), use_container_width=True)

# ---------------- Ratings
with tab_rat:
    c = st.columns(2)
    c[0].metric("Avg driver rating", f"{k['driver_rating']:.2f}")
    c[1].metric("Avg customer rating", f"{k['customer_rating']:.2f}")
    vt = od.vehicle_table(df).reset_index()
    long = vt.melt("Vehicle_Type", ["Avg Driver Rating", "Avg Customer Rating"], var_name="Type", value_name="Rating")
    fig = px.bar(long, x="Vehicle_Type", y="Rating", color="Type", barmode="group",
                 title="Average rating by vehicle type", color_discrete_sequence=[BLUE, GREEN])
    fig.update_yaxes(range=[3, 5])
    st.plotly_chart(fig, use_container_width=True)
    st.plotly_chart(px.bar(od.ratings_distribution(df), x="Rating", y="Rides",
                           title="Driver rating distribution", color_discrete_sequence=[BLUE]),
                    use_container_width=True)
    st.caption("Only completed rides carry ratings, and every rating falls between 3.0 and 5.0.")

# ---------------- Data
with tab_data:
    st.caption(f"{len(df):,} rows after filters")
    st.dataframe(df.head(1000), use_container_width=True)
    st.download_button("Download filtered data (CSV)", df.to_csv(index=False).encode("utf-8"),
                       "ola_filtered.csv", "text/csv")
