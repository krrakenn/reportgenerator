import streamlit as st
import pandas as pd
from sql_generator import generate_sql
from query_runner import run_sql

st.set_page_config(
    page_title="Report Generator",
    layout="wide"
)

MAX_RETRIES = 3

# -------------------- Load Schema CSV --------------------

@st.cache_data
def load_schema():
    df = pd.read_csv("restructured_schema.csv")
    return df

schema_df = load_schema()
all_tables = list(schema_df.columns)

# -------------------- Build Schema Context --------------------

def build_schema_context(schema_df, selected_tables):

    schema_text = ""

    for table in selected_tables:

        schema_text += f"\nTable: {table}\nColumns:\n"

        cols = schema_df[table].dropna().tolist()

        for col in cols:
            schema_text += f"- {col}\n"

    return schema_text


# -------------------- Theme Styling --------------------

st.markdown("""
<style>
.stApp {
    background-color: #0E1117;
}

section[data-testid="stSidebar"] {
    background-color: #161B22;
}

h1, h2, h3, h4 {
    font-weight: 600;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}
</style>
""", unsafe_allow_html=True)

# -------------------- Header --------------------

st.title("Report Generator")
st.caption("Generate reports from tables and KPI definitions")

st.divider()

# -------------------- Sidebar --------------------

with st.sidebar:

    st.header("Settings")

    MAX_RETRIES = st.number_input(
        "Maximum Retry Attempts",
        min_value=1,
        max_value=5,
        value=3
    )

    st.divider()

    st.caption(
        "If the generated SQL fails, the system will retry by providing the error back to the model."
    )

# -------------------- Input Section --------------------

col1, col2, col3 = st.columns(3, gap="large")

# -------- Table Selection --------
with col1:

    st.markdown("### Select Tables")

    selected_tables = st.multiselect(
        "Choose tables",
        options=all_tables,
        placeholder="Search tables from im_dwh_rpt"
    )

    if selected_tables:

        with st.expander("Preview Schema"):

            preview_context = build_schema_context(schema_df, selected_tables)

            st.text_area(
                "Schema Preview",
                preview_context,
                height=220,
                disabled=True
            )

# -------- KPI Input --------
with col2:

    st.markdown("### KPI Definitions")

    kpis = st.text_area(
        "Define KPIs",
        height=260,
        placeholder="""
Example:
Daily revenue
New users per day
Churn rate
Top categories by sales
"""
    )

# -------- Additional Instructions --------
with col3:

    st.markdown("### Conditions/Flags/Filters")

    additional_prompt = st.text_area(
        "Column meanings, flag values, filters",
        height=200,
        placeholder="""
Example:
is_active = 1 means active users
status_flag 0 = inactive
country_code = 'IN'
"""
    )

    # Date Filter Checkbox
    use_date_filter = st.checkbox("Add Date Filter (only if exists)")

    if use_date_filter:

        date_col1, date_col2 = st.columns(2)

        with date_col1:
            date_from = st.date_input("From Date")

        with date_col2:
            date_to = st.date_input("To Date")

    else:
        date_from = None
        date_to = None

st.markdown(" ")

run = st.button("Generate Report", use_container_width=True)

st.divider()

# -------------------- Execution --------------------

if run:

    if not selected_tables:
        st.warning("Please select at least one table")
        st.stop()

    if not kpis:
        st.warning("KPI definitions are required")
        st.stop()

    if not additional_prompt:
        st.warning("Additional instructions are required")
        st.stop()

    schema_context = build_schema_context(schema_df, selected_tables)

    # -------- Dynamic Date Instruction --------
    date_instruction = ""

    if use_date_filter and date_from and date_to:

        date_instruction = f"""
Date Filtering Requirement:
The report must include data between '{date_from}' and '{date_to}'.
Use the most appropriate date column from the selected tables.
Ensure the SQL WHERE clause applies this filter.
"""

    additional_prompt_final = additional_prompt + "\n" + date_instruction

    attempt = 0
    last_error = None
    sql = None

    status = st.status("Running SQL generation", expanded=True)

    while attempt < MAX_RETRIES:

        attempt += 1

        status.write(f"Attempt {attempt}: generating SQL")

        if last_error:

            prompt_kpi = f"""
KPIs:
{kpis}

Additional Instructions:
{additional_prompt_final}

Previous SQL:
{sql}

Previous SQL Error:
{last_error}

Fix the SQL.
Return only SQL.
"""

            sql = generate_sql(schema_context, prompt_kpi, "")

        else:

            sql = generate_sql(schema_context, kpis, additional_prompt_final)

        try:

            status.write("Executing SQL query")

            result = run_sql(sql)

            status.update(label="Execution completed", state="complete")

            tab1, tab2 = st.tabs(["Result", "Generated SQL"])

            with tab1:
                st.dataframe(result, use_container_width=True)

            with tab2:
                st.code(sql, language="sql")

            st.success(f"Query succeeded on attempt {attempt}")

            break

        except Exception as e:

            last_error = str(e)

            status.write(f"Attempt {attempt} failed")
            status.write(last_error)

    else:

        status.update(label="Execution failed", state="error")

        st.error("All retry attempts failed")

        with st.expander("Last Generated SQL"):
            st.code(sql, language="sql")
