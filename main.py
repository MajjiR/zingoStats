import streamlit as st

# Set page config at the very beginning
st.set_page_config(page_title="Order Analytics Dashboard", layout="wide")

import pymysql
import pandas as pd
from datetime import datetime
import io


# ---------------- DB CONNECTION ---------------- #
def get_db_connection():
    try:
        return pymysql.connect(
            host=st.secrets["DB_HOST"],
            user=st.secrets["DB_USER"],
            password=st.secrets["DB_PASSWORD"],
            database=st.secrets["DB_NAME"],
            port=3306,
            connect_timeout=10,
            read_timeout=10,
            write_timeout=10,
            ssl={"ssl": {}},
            cursorclass=pymysql.cursors.DictCursor
        )
    except Exception as e:
        st.error(f"Database connection failed: {e}")
        return None


# ---------------- UTILS ---------------- #
def export_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


def get_date_range_text(start_date, end_date):
    if end_date:
        return f"from {start_date} to {end_date}"
    return f"for {start_date}"


# ---------------- FINAL STATS ---------------- #
def get_final_stats(start_date=None, end_date=None):
    conn = get_db_connection()
    if conn is None:
        return pd.DataFrame()

    query = """
    SELECT 
        COUNT(id) + 0 as total_orders,
        COALESCE(SUM(order_amount), 0) + 0 as total_order_amount,
        COALESCE(SUM(order_amount - delivery_charge - additional_charge), 0) + 0 as total_restaurant_revenue,
        COALESCE(SUM(delivery_charge), 0) + 0 as total_delivery_charge,
        COALESCE(SUM(additional_charge), 0) + 0 as total_additional_charge
    FROM orders 
    WHERE order_status = 'delivered'
    """

    if start_date and end_date:
        query += f" AND DATE(created_at) BETWEEN '{start_date}' AND '{end_date}'"
    elif start_date:
        query += f" AND DATE(created_at) = '{start_date}'"

    df = pd.read_sql(query, conn)

    if not df.empty:
        df = df.astype({
            "total_orders": "int",
            "total_order_amount": "float",
            "total_restaurant_revenue": "float",
            "total_delivery_charge": "float",
            "total_additional_charge": "float"
        })

    conn.close()
    return df


# ---------------- RESTAURANT STATS ---------------- #
def get_restaurant_stats(start_date=None, end_date=None):
    conn = get_db_connection()
    if conn is None:
        return pd.DataFrame()

    query = """
    SELECT 
        s.name as restaurant_name,
        COUNT(o.id) + 0 as total_orders,
        SUM(o.order_amount) + 0 as total_order_amount,
        SUM(o.delivery_charge) + 0 as total_delivery_fee,
        SUM(o.additional_charge) + 0 as total_additional_charge,
        SUM(o.order_amount - o.delivery_charge - o.additional_charge) + 0 as total_revenue
    FROM orders o
    JOIN stores s ON o.store_id = s.id
    WHERE o.order_status = 'delivered'
    """

    if start_date and end_date:
        query += f" AND DATE(o.created_at) BETWEEN '{start_date}' AND '{end_date}'"
    elif start_date:
        query += f" AND DATE(o.created_at) = '{start_date}'"

    query += " GROUP BY s.id, s.name ORDER BY total_revenue DESC"

    df = pd.read_sql(query, conn)

    if not df.empty:
        df = df.astype({
            "total_orders": "int",
            "total_order_amount": "float",
            "total_delivery_fee": "float",
            "total_additional_charge": "float",
            "total_revenue": "float"
        })

    conn.close()
    return df


# ---------------- DELIVERY STATS ---------------- #
def get_delivery_stats(start_date=None, end_date=None):
    conn = get_db_connection()
    if conn is None:
        return pd.DataFrame()

    query = """
    SELECT 
        dm.l_name as delivery_man_name,
        COUNT(o.id) + 0 as total_deliveries,
        SUM(o.order_amount) + 0 as total_order_amount,
        SUM(o.delivery_charge) + 0 as total_delivery_fee
    FROM orders o
    JOIN delivery_men dm ON o.delivery_man_id = dm.id
    WHERE o.order_status = 'delivered'
    """

    if start_date and end_date:
        query += f" AND DATE(o.created_at) BETWEEN '{start_date}' AND '{end_date}'"
    elif start_date:
        query += f" AND DATE(o.created_at) = '{start_date}'"

    query += " GROUP BY dm.id, dm.l_name ORDER BY total_order_amount DESC"

    df = pd.read_sql(query, conn)

    if not df.empty:
        df = df.astype({
            "total_deliveries": "int",
            "total_order_amount": "float",
            "total_delivery_fee": "float"
        })

    conn.close()
    return df


# ---------------- MAIN APP ---------------- #
def main():
    st.title("Order Analytics Dashboard")
    st.caption("Note: All statistics are based on delivered orders only")

    # Sidebar date selection
    st.sidebar.header("Date Range Selection")

    if st.sidebar.button("Get Today's Stats"):
        start_date = datetime.now().date()
        end_date = None
    else:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("Start Date")
        with col2:
            end_date = st.date_input("End Date")

    # ---------------- FINAL STATS ---------------- #
    st.header("Overall Statistics")
    final_stats = get_final_stats(start_date, end_date)

    if final_stats.empty or final_stats['total_orders'].iloc[0] == 0:
        st.warning(f"No orders found {get_date_range_text(start_date, end_date)}")
        st.stop()

    cols = st.columns(5)

    with cols[0]:
        st.metric("Total Orders", f"{final_stats['total_orders'].iloc[0]:,}")

    with cols[1]:
        st.metric("Total Order Amount", f"₹{final_stats['total_order_amount'].iloc[0]:,.2f}")

    with cols[2]:
        st.metric("Total Restaurant Revenue", f"₹{final_stats['total_restaurant_revenue'].iloc[0]:,.2f}")

    with cols[3]:
        st.metric("Total Delivery Charge", f"₹{final_stats['total_delivery_charge'].iloc[0]:,.2f}")

    with cols[4]:
        st.metric("Total Additional Charge", f"₹{final_stats['total_additional_charge'].iloc[0]:,.2f}")

    if st.button("Export Overall Stats"):
        excel_data = export_to_excel(final_stats)
        st.download_button(
            label="Download Overall Stats Excel",
            data=excel_data,
            file_name=f"overall_stats_{start_date}_to_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    # ---------------- RESTAURANTS ---------------- #
    st.header("Restaurant Statistics")
    restaurant_stats = get_restaurant_stats(start_date, end_date)

    if restaurant_stats.empty:
        st.warning("No restaurant data found")
    else:
        st.dataframe(restaurant_stats, use_container_width=True)

    # ---------------- DELIVERY ---------------- #
    st.header("Delivery Man Statistics")
    delivery_stats = get_delivery_stats(start_date, end_date)

    if delivery_stats.empty:
        st.warning("No delivery data found")
    else:
        st.dataframe(delivery_stats, use_container_width=True)


if __name__ == "__main__":
    main()
