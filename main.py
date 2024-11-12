import streamlit as st

# Set page config at the very beginning
st.set_page_config(page_title="Order Analytics Dashboard", layout="wide")

import pymysql
import pandas as pd
from datetime import datetime, timedelta
import io


def get_db_connection():
    return pymysql.connect(
        host=st.secrets["DB_HOST"],
        user=st.secrets["DB_USER"],
        password=st.secrets["DB_PASSWORD"],
        database=st.secrets["DB_NAME"]
    )


def get_restaurant_stats(start_date=None, end_date=None):
    conn = get_db_connection()
    query = """
    SELECT 
        s.name as restaurant_name,
        COUNT(o.id) as total_orders,
        SUM(o.order_amount) as total_order_amount,
        SUM(o.delivery_charge) as total_delivery_fee,
        SUM(o.additional_charge) as total_additional_charge,
        SUM(o.order_amount - o.delivery_charge - o.additional_charge) as total_revenue
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
        monetary_columns = ['total_order_amount', 'total_delivery_fee', 'total_additional_charge', 'total_revenue']
        for col in monetary_columns:
            if col in df.columns:
                df[col] = df[col].round(2)

    conn.close()
    return df


def get_delivery_stats(start_date=None, end_date=None):
    conn = get_db_connection()
    query = """
    SELECT 
        dm.l_name as delivery_man_name,
        COUNT(o.id) as total_deliveries,
        SUM(o.order_amount) as total_order_amount,
        SUM(o.delivery_charge) as total_delivery_fee
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
        monetary_columns = ['total_order_amount', 'total_delivery_fee']
        for col in monetary_columns:
            if col in df.columns:
                df[col] = df[col].round(2)

    conn.close()
    return df


def get_final_stats(start_date=None, end_date=None):
    conn = get_db_connection()
    query = """
    SELECT 
        COUNT(id) as total_orders,
        COALESCE(SUM(order_amount), 0) as total_order_amount,
        COALESCE(SUM(order_amount - delivery_charge - additional_charge), 0) as total_restaurant_revenue,
        COALESCE(SUM(delivery_charge), 0) as total_delivery_charge,
        COALESCE(SUM(additional_charge), 0) as total_additional_charge
    FROM orders 
    WHERE order_status = 'delivered'
    """

    if start_date and end_date:
        query += f" AND DATE(created_at) BETWEEN '{start_date}' AND '{end_date}'"
    elif start_date:
        query += f" AND DATE(created_at) = '{start_date}'"

    df = pd.read_sql(query, conn)

    if not df.empty:
        monetary_columns = ['total_order_amount', 'total_restaurant_revenue',
                            'total_delivery_charge', 'total_additional_charge']
        for col in monetary_columns:
            if col in df.columns:
                df[col] = df[col].round(2)

    conn.close()
    return df


def export_to_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()


def get_date_range_text(start_date, end_date):
    if end_date:
        return f"from {start_date} to {end_date}"
    return f"for {start_date}"


def main():
    st.title("Order Analytics Dashboard")
    st.caption("Note: All statistics are based on delivered orders only")

    # Date Range Selection
    st.sidebar.header("Date Range Selection")

    # Today's stats button
    if st.sidebar.button("Get Today's Stats"):
        start_date = datetime.now().date()
        end_date = None
    else:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("Start Date")
        with col2:
            end_date = st.date_input("End Date")

    # Final Stats at the top
    st.header("Overall Statistics")
    final_stats = get_final_stats(start_date, end_date)

    if final_stats['total_orders'].iloc[0] == 0:
        st.warning(f"No orders found {get_date_range_text(start_date, end_date)}")
    else:
        # Display final stats in columns
        cols = st.columns(5)
        with cols[0]:
            st.metric("Total Orders", f"{final_stats['total_orders'].iloc[0]:,.0f}")
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

        # Restaurant Stats
        st.header("Restaurant Statistics")
        restaurant_stats = get_restaurant_stats(start_date, end_date)
        if restaurant_stats.empty:
            st.warning(f"No restaurant orders found {get_date_range_text(start_date, end_date)}")
        else:
            st.dataframe(restaurant_stats, use_container_width=True)
            if st.button("Export Restaurant Stats"):
                excel_data = export_to_excel(restaurant_stats)
                st.download_button(
                    label="Download Restaurant Stats Excel",
                    data=excel_data,
                    file_name=f"restaurant_stats_{start_date}_to_{end_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

        # Delivery Man Stats
        st.header("Delivery Man Statistics")
        delivery_stats = get_delivery_stats(start_date, end_date)
        if delivery_stats.empty:
            st.warning(f"No delivery orders found {get_date_range_text(start_date, end_date)}")
        else:
            st.dataframe(delivery_stats, use_container_width=True)
            if st.button("Export Delivery Stats"):
                excel_data = export_to_excel(delivery_stats)
                st.download_button(
                    label="Download Delivery Stats Excel",
                    data=excel_data,
                    file_name=f"delivery_stats_{start_date}_to_{end_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )


if __name__ == "__main__":
    main()