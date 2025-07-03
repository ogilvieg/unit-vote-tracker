import plotly.express as px
import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
from decimal import Decimal, ROUND_DOWN
import io
import os

def truncate_pct(val):
    return Decimal(val * 100).quantize(Decimal("0.01"), rounding=ROUND_DOWN)

def weighted_vote_percentages(df):
    df = df.copy()

    # Separate valid voters (YES/NO) and non-voters
    valid_votes = df[df["Vote"].isin(["YES", "NO"])]
    non_voters = df[~df["Vote"].isin(["YES", "NO"])]

    # Map YES/NO to binary
    valid_votes["VoteBinary"] = valid_votes["Vote"].map({"YES": 1, "NO": 0})

    # Calculate weights
    valid_votes["WeightedVote"] = valid_votes["VoteBinary"] * valid_votes["Beneficial Interest"]
    total_interest = df["Beneficial Interest"].sum()

    yes_weight = valid_votes["WeightedVote"].sum()
    voted_interest = valid_votes["Beneficial Interest"].sum()
    non_voter_interest = total_interest - voted_interest

    if total_interest == 0:
        return {"0": 0.0, "1": 0.0, "non_voters": 0.0}

    return {
        "0": (voted_interest - yes_weight) / total_interest,
        "1": yes_weight / total_interest,
        "non_voters": non_voter_interest / total_interest
    }

# Helper: valid 4-digit number?
def is_valid_voter_id(voter_id):
    return voter_id.isdigit() and len(voter_id) == 4
#-------APP LOGIC------------

st.markdown("""
### 🗳️ Voting Instructions

To begin or continue voting, you'll need to enter a **4-digit Voter ID**.

- If this is your **first time**, simply choose any 4-digit number (e.g. `1234`) to **create your Voter ID**.
- If you’ve already started voting before, enter the **same 4-digit Voter ID** to **load your previous progress**.
- Your votes will be saved in a private file associated with your Voter ID so you can return and finish later.

🔒 _Please remember your Voter ID — it’s the only way to access your saved progress._
""")

df = pd.read_csv('dataset/owners_vote.csv')  # your df_unique
df['Vote'] = 'Click to Vote'

voter_id = st.text_input("Voter ID (4 digits) e.g. 2025", max_chars=4)
start_fresh = False
if st.button("🔄 Load My Previous Vote"):
    if not is_valid_voter_id(voter_id):
        st.error("Voter ID must be a 4-digit number.")
    else:
        file_path = f"votes_{voter_id}.csv"
        if os.path.exists(file_path):
            user_votes = pd.read_csv(file_path)
            st.session_state.df = user_votes
            st.success(f"✅ Loaded vote data for Voter ID {voter_id}.")
        else:
            st.warning("No existing vote found. You can start fresh.")


# 1. Initialize
if 'df' not in st.session_state:
    # st.session_state.df = df
    st.session_state.df = df.copy()

st.markdown("""
### 🗳️ Voting Instructions - Ballot Simulator

Use the dropdown in the **Vote** column to select `YES` or `NO`.  
Your voting power is weighted by your **Beneficial Interest** percentage.
""")


# Configure AgGrid with dropdown for "Vote"
gb = GridOptionsBuilder.from_dataframe(st.session_state.df)
# Enable global column behaviors: filter, sort, resize
gb.configure_default_column(filter=True, sortable=True, resizable=True)
gb.configure_column("Vote", editable=True, cellEditor="agSelectCellEditor",
                    cellEditorParams={"values": ["Click to Vote", "YES", "NO"]})
gb.configure_column("VoteBinary", hide=True)
# gb.configure_column("Owner Type", hide=True)
gb.configure_columns(["Unit Number", "Beneficial Interest", "VoteBinary", "Owner Type"], editable=False)
gb.configure_grid_options(singleClickEdit=True,
                          stopEditingWhenCellsLoseFocus=True)
grid_options = gb.build()



####------------PLOTLY PyChart

# Create two columns: table | chart
table_col, chart_col = st.columns([3, 2])  # wider for table, smaller for chart

with table_col:
    # Re-render voting table here
    # Show interactive table
    grid_response = AgGrid(
        st.session_state.df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.VALUE_CHANGED,
        fit_columns_on_grid_load=True,
        theme='streamlit',
    )

# Step 4: Process updated votes (VoteBinary calculated but not shown)
updated_df = grid_response["data"].copy()
updated_df["VoteBinary"] = updated_df["Vote"].map({"YES": 1, "NO": 0}).fillna(-500).astype(int)

# Step 5: Save updated data (excluding VoteBinary from UI)
st.session_state.df = updated_df.drop(columns=["VoteBinary"], errors="ignore")

weighted = weighted_vote_percentages(updated_df)

# Convert to percentages (0.0–1.0 → 0–100)
vote_data = {
    "YES": weighted["1"] * 100,
    "NO": weighted["0"] * 100,
    "Non-Voters": weighted["non_voters"] * 100
}
with chart_col:
    st.markdown("### 🧮 Vote Breakdown")
    fig = px.pie(
        names=list(vote_data.keys()),
        values=list(vote_data.values()),
        title="Weighted Vote Distribution",
        hole=0.4
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig, use_container_width=True)

# column metrics
yes_pct = truncate_pct(weighted["1"])
no_pct = truncate_pct(weighted["0"])
non_pct = truncate_pct(weighted["non_voters"])
col1, col2, col3 = st.columns(3)
col1.metric("YES | vote %", f"{yes_pct}%")
col2.metric("NO | vote %", f"{no_pct}%")
col3.metric("Non-voters | vote %", f"{non_pct}%")

csv = st.session_state.df.to_csv(index=False).encode("utf-8")
st.download_button("📥 Download Vote Results as CSV", csv, "vote_results.csv", "text/csv")

if st.button("💾 Save My Vote"):
    if not is_valid_voter_id(voter_id):
        st.error("Please enter a valid 4-digit Voter ID before saving.")
    else:
        save_path = f"votes_{voter_id}.csv"
        if os.path.exists(save_path):
            st.warning(f"⚠️ This will overwrite an existing vote file: {save_path}")
            st.session_state.df.to_csv(save_path, index=False)
            st.success(f"✅ Vote saved to {save_path}")

st.dataframe(st.session_state.df)
