import streamlit as st
import pandas as pd
import mysql.connector
from datetime import datetime
import base64
import os
import logging
import sys
import warnings
import openpyxl



# ✅ Show banner/logo
st.image("dddd.jpg", use_container_width=True)

# ✅ MySQL Connection Function using secrets.toml
def get_mysql_connection():
    try:
        return mysql.connector.connect(
            host=st.secrets["mysql"]["host"],
            user=st.secrets["mysql"]["user"],
            password=st.secrets["mysql"]["password"],
            database=st.secrets["mysql"]["database"],
        )
    except mysql.connector.Error as err:
        st.error(f"Error: {err}")
        return None

# ✅ Load and clean Excel file
@st.cache_data(hash_funcs={pd.DataFrame: lambda _: None})
def load_data(file_path):
    df = pd.read_excel(file_path)
    df.rename(columns={'Actual_Manager_Column_Name': 'Manager Name', 'Actual_SPOC_Column_Name': 'SPOC Name'}, inplace=True)
    return df

# ✅ Insert slot booking
def insert_booking(date, time_range, manager, spoc, booked_by):
    if not booked_by:
        st.error('Please enter your name to book the slot.')
        return

    selected_date = datetime.strptime(date, '%Y-%m-%d')
    current_date = datetime.now()
    holidays = ['2024-10-31', '2024-11-09', '2024-11-16']

    if selected_date.strftime('%Y-%m-%d') in holidays:
        st.error('Booking not allowed on holidays.')
        return

    if selected_date < current_date:
        st.error('Cannot book for past dates.')
        return

    if selected_date.weekday() == 6:
        st.error('Sundays are not allowed for booking.')
        return

    conn = get_mysql_connection()
    if conn is None:
        return

    cursor = conn.cursor()
    cursor.execute("SELECT * FROM appointment_bookings WHERE date = %s AND spoc = %s", (date, spoc))
    existing_booking = cursor.fetchone()

    if existing_booking:
        conn.close()
        st.error('SPOC is already booked on this date.')
        return

    cursor.execute("""
        INSERT INTO appointment_bookings (date, time_range, manager, spoc, booked_by)
        VALUES (%s, %s, %s, %s, %s)
    """, (date, time_range, manager, spoc, booked_by))
    conn.commit()
    conn.close()
    st.success('Slot booked successfully!')

# ✅ Upload student verification data
def update_another_database(file):
    df = pd.read_excel(file)
    conn = get_mysql_connection()
    if conn is None:
        return
    cursor = conn.cursor()
    for _, row in df.iterrows():
        cursor.execute("""
            INSERT INTO plana 
            (cmis_id, student_name, cmis_ph_no, center_name, uploader_name, verification_type, mode_of_verification, verification_date)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            row['CMIS ID'], row['Student Name'], row['CMIS PH No(10 Number)'],
            row['Center Name'], row['Name Of Uploder'], row['Verification Type'],
            row['Mode Of Verification'], row['Verification Date']
        ))
    conn.commit()
    conn.close()
    st.success('Student verification data uploaded!')

# ✅ Download verification data
def download_another_database_data():
    conn = get_mysql_connection()
    if conn is None:
        return
    df = pd.read_sql("SELECT * FROM plana", conn)
    conn.close()
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="plana.csv">📥 Download CSV</a>'
    st.markdown(href, unsafe_allow_html=True)

# ✅ Main App UI
def main():
    st.title('📅 Slot Booking Platform')

    data = load_data('managers_spocs.xlsx')  # Your Excel file
    selected_manager = st.selectbox('👨‍💼 Select Manager', data['Manager Name'].unique())
    spocs = data[data['Manager Name'] == selected_manager]['SPOC Name'].tolist()
    selected_spoc = st.selectbox('👤 Select SPOC', spocs)
    selected_date = st.date_input('📆 Select Date')
    time_ranges = ['10:00 AM - 11:00 AM', '11:00 AM - 12:00 PM', '12:00 PM - 1:00 PM', '2:00 PM - 3:00 PM', '3:00 PM - 4:00 PM']
    selected_time = st.selectbox('🕐 Select Time Slot', time_ranges)
    booked_by = st.text_input('✍️ Your Name')
    file = st.file_uploader('📤 Upload Student Verification Excel', type=['xlsx'])

    if file is not None and st.button('⬆️ Update Data'):
        update_another_database(file)

    if st.button('📌 Book Slot'):
        insert_booking(str(selected_date), selected_time, selected_manager, selected_spoc, booked_by)

    if st.button('📥 Download Data For M&E'):
        download_another_database_data()

    # ✅ Show today's bookings
    conn = get_mysql_connection()
    if conn is None:
        return
    df = pd.read_sql("SELECT * FROM appointment_bookings", conn)
    conn.close()

    st.subheader("📋 Today's Bookings")
    current_date = datetime.now().strftime("%Y-%m-%d")
    df['date'] = pd.to_datetime(df['date'])
    today = df[df['date'].dt.strftime('%Y-%m-%d') == current_date]
    if not today.empty:
        for _, row in today.iterrows():
            st.write(f"- 🕒 {row['time_range']}, 👨‍💼 Manager: {row['manager']}, 👤 SPOC: {row['spoc']}")
    else:
        st.write("No bookings today.")

if __name__ == '__main__':
    main()
