import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
from datetime import date, datetime
import calendar


@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error(f"Failed to connect to Supabase: {e}")
        return None

supabase: Client = init_connection()


if 'user' not in st.session_state:
    st.session_state['user'] = None


def login_page():
    st.title("💸 Personal Expense Tracker")
    st.write("Please log in to manage your expenses.")
    
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        try:
            response = supabase.auth.sign_in_with_password({"email": email, "password": password})
            st.session_state['user'] = response.user
            st.rerun()
        except Exception as e:
            st.error("Login failed. Check your credentials.")


def dashboard_page():
    
    col1, col2 = st.columns([4, 1])
    with col1:
        st.title("Expense Dashboard")
    with col2:
        if st.button("Logout"):
            supabase.auth.sign_out()
            st.session_state['user'] = None
            st.rerun()

    user_id = st.session_state['user'].id

    
    st.sidebar.header("➕ Add New Expense")
    with st.sidebar.form("expense_form", clear_on_submit=True):
        exp_date = st.date_input("Date", date.today())
        exp_amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0)
        exp_category = st.selectbox("Category", [
            "Food & Dining", "Travel & Commute", "Groceries", 
            "Shopping", "Bills & Utilities", "Education", 
            "Health", "Entertainment", "Paid to Someone", "Other"
        ])
        exp_need_want = st.radio("Type", ["Need", "Want"])
        exp_desc = st.text_input("Description (Optional)")
        
        submitted = st.form_submit_button("Save Expense")
        if submitted and exp_amount > 0:
            supabase.table("expenses").insert({
                "user_id": user_id,
                "date": str(exp_date),
                "amount": exp_amount,
                "category": exp_category,
                "need_want": exp_need_want,
                "description": exp_desc
            }).execute()
            st.sidebar.success("Expense saved!")
            st.rerun()
            
    
    response = supabase.table("expenses").select("*").eq("user_id", user_id).execute()
    data = response.data
    
    if not data:
        st.info("No expenses found. Add your first expense from the sidebar!")
        return

    
    df = pd.DataFrame(data)
    df['date'] = pd.to_datetime(df['date'])
    df['year_month'] = df['date'].dt.strftime('%B %Y') 
    df['sort_key'] = df['date'].dt.strftime('%Y-%m')    

    
    unique_months = df.sort_values(by='sort_key', ascending=False)['year_month'].unique().tolist()
    
    current_month_str = datetime.now().strftime('%B %Y')
    if current_month_str not in unique_months:
        unique_months.insert(0, current_month_str)

    
    st.markdown("### 📅 Select Month")
    selected_month = st.selectbox("Viewing data for:", options=unique_months, index=0)

    
    month_df = df[df['year_month'] == selected_month].copy()

    
    with st.expander("🔍 Additional Filters & Search", expanded=False):
        f_col1, f_col2, f_col3 = st.columns(3)
        
        with f_col1:
            categories = ["All"] + list(month_df['category'].unique()) if not month_df.empty else ["All"]
            selected_category = st.selectbox("Category Filter", categories)
            
        with f_col2:
            selected_type = st.selectbox("Need/Want Filter", ["All", "Need", "Want"])
            
        with f_col3:
            search_query = st.text_input("Search Description", "")

    
    filtered_df = month_df.copy()
    if not filtered_df.empty:
        if selected_category != "All":
            filtered_df = filtered_df[filtered_df['category'] == selected_category]
        if selected_type != "All":
            filtered_df = filtered_df[filtered_df['need_want'] == selected_type]
        if search_query:
            filtered_df = filtered_df[filtered_df['description'].str.contains(search_query, case=False, na=False)]

    st.markdown("---")
    
    
    st.subheader(f"Summary for {selected_month}")
    
    total_spent = month_df['amount'].sum() if not month_df.empty else 0
    needs_spent = month_df[month_df['need_want'] == 'Need']['amount'].sum() if not month_df.empty else 0
    wants_spent = month_df[month_df['need_want'] == 'Want']['amount'].sum() if not month_df.empty else 0
    paid_someone = month_df[month_df['category'] == 'Paid to Someone']['amount'].sum() if not month_df.empty else 0

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Spent", f"₹{total_spent:,.2f}")
    m2.metric("Needs", f"₹{needs_spent:,.2f}")
    m3.metric("Wants", f"₹{wants_spent:,.2f}")
    m4.metric("Paid to Someone", f"₹{paid_someone:,.2f}")

    st.markdown("---")

    
    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        st.markdown("**Category Breakdown**")
        if not filtered_df.empty:
            cat_fig = px.pie(filtered_df, values='amount', names='category', hole=0.4)
            st.plotly_chart(cat_fig, use_container_width=True)
        else:
            st.info("No matching records for this month.")

    with col_chart2:
        st.markdown("**Needs vs Wants**")
        if not filtered_df.empty:
            nw_summary = filtered_df.groupby('need_want')['amount'].sum().reset_index()
            nw_fig = px.bar(nw_summary, x='need_want', y='amount', color='need_want', text_auto=True)
            st.plotly_chart(nw_fig, use_container_width=True)
        else:
            st.info("No matching records for this month.")

    st.markdown("---")
    
    
    st.subheader("Transactions Log")
    if not filtered_df.empty:
        
        display_df = filtered_df.sort_values(by="date", ascending=False)[['date', 'amount', 'category', 'need_want', 'description']]
        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')
        st.dataframe(
            display_df, 
            use_container_width=True,
            hide_index=True
        )
    else:
        st.write("No transactions found matching the applied filters.")

    
    with st.expander("🗑️ Delete an Expense"):
        if not filtered_df.empty:
            st.warning("Warning: Deleting an expense cannot be undone.")
            
            
            delete_options = {}
            
            sorted_for_delete = filtered_df.sort_values(by="date", ascending=False)
            
            for _, row in sorted_for_delete.iterrows():
                date_str = row['date'].strftime('%Y-%m-%d')
                desc = row['description'] if pd.notna(row['description']) and row['description'] != '' else 'No description'
                
                label = f"{date_str} - {row['category']} - ₹{row['amount']} ({desc})"
                delete_options[label] = row['id']
            
            selected_to_delete = st.selectbox("Select the expense you want to remove:", options=list(delete_options.keys()))
            
            if st.button("Delete Selected Expense", type="primary"):
                expense_id_to_delete = delete_options[selected_to_delete]
                try:
                    
                    supabase.table("expenses").delete().eq("id", expense_id_to_delete).execute()
                    st.success("Expense deleted successfully!")
                    st.rerun() # Refresh the app to update the charts and table
                except Exception as e:
                    st.error(f"Failed to delete: {e}")
        else:
            st.write("No expenses available to delete for this month.")


if st.session_state['user'] is None:
    login_page()
else:
    dashboard_page()