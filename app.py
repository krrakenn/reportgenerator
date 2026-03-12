import streamlit as st
import pandas as pd

from sql_generator import generate_sql, merge_queries_llm
from query_runner import run_sql

st.set_page_config(
    page_title="Report Generator",
    layout="wide"
)

MAX_RETRIES = 3


@st.cache_data
def load_schema():
    df = pd.read_csv("restructured_schema.csv")
    return df


schema_df = load_schema()
all_tables = list(schema_df.columns)


def build_schema_context(schema_df, selected_tables):

    schema_text = ""

    for table in selected_tables:

        schema_text += f"\nTable: {table}\nColumns:\n"

        cols = schema_df[table].dropna().tolist()

        for col in cols:
            schema_text += f"- {col}\n"

    return schema_text


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


title_col, toggle_col = st.columns([10,2])

with title_col:
    st.title("Report Generator")
    st.caption("Generate reports from tables and KPI definitions")

with toggle_col:
    st.markdown("### ")
    mode_sql = st.toggle("I have Query")

st.divider()


if not mode_sql:

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

    col1, col2, col3 = st.columns(3, gap="large")

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

    run = st.button("Generate Report", use_container_width=True)

    st.divider()

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
{additional_prompt}

Previous SQL:
{sql}

Previous SQL Error:
{last_error}

Fix the SQL.
Return only SQL.
"""

                sql = generate_sql(schema_context, prompt_kpi, "")

            else:

                sql = generate_sql(schema_context, kpis, additional_prompt)

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


else:

    st.subheader("SQL Query Mode")

    query_count = st.number_input(
        "Number of Queries",
        min_value=1,
        max_value=5,
        value=1
    )

    queries = []

    for i in range(query_count):

        q = st.text_area(
            f"Query {i+1}",
            height=160,
            key=f"query_{i}"
        )

        queries.append(q)

    run_sql_mode = st.button("Run Queries", use_container_width=True)

    st.divider()

    if run_sql_mode:

        valid_queries = [q for q in queries if q.strip()]

        if not valid_queries:
            st.warning("Please enter at least one SQL query")
            st.stop()

        with st.spinner("Checking if queries can be merged..."):
            merged_sql = merge_queries_llm(valid_queries)

        with st.spinner("Executing Query"):

            attempt = 0
            last_error = None
            sql = merged_sql

            while attempt < MAX_RETRIES:

                attempt += 1

                try:

                    result = run_sql(sql)

                    tab1, tab2 = st.tabs(["Result", "Generated SQL"])

                    with tab1:
                        st.dataframe(result, use_container_width=True)

                    with tab2:
                        st.code(sql, language="sql")

                    break

                except Exception as e:

                    last_error = str(e)

                    prompt = f"""
Queries:
{valid_queries}

Previous SQL:
{sql}

Previous SQL Error:
{last_error}

Fix the SQL.
Return only SQL.
"""

                    sql = merge_queries_llm([prompt])

            else:

                st.error("All retry attempts failed")

                with st.expander("Last Generated SQL"):
                    st.code(sql, language="sql")
