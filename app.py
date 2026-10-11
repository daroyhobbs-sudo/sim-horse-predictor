import streamlit as st
import pandas as pd
import json

# Set wide layout for dense betting grids
st.set_page_config(layout="wide", page_title="SIM Horse Predictor")

st.title("🏇 SIM Horse Racing High-Pace Calculator")

# --- SECTION 1: SIDEBAR DATA STORAGE ---
st.sidebar.header("📁 Backup & History Dataset")

# Multi-file or single-file backup loader
uploaded_backup = st.sidebar.file_uploader("Upload your .json backup file", type=["json"])

# Keep track of history across app refreshes
if uploaded_backup:
    try:
        raw_data = json.load(uploaded_backup)
        
        # Extract the list of races from the JSON structure
        races_list = raw_data.get("races", [])
        st.sidebar.success(f"✅ Successfully read {len(races_list)} historical races!")
        
        # Flatten the data so Python can run fast math on it
        all_past_horses = []
        for r in races_list:
            track = r.get("track", "Unknown")
            dist = r.get("dist", "0")
            surf = r.get("surf", "Unknown")
            cond = r.get("cond", "Unknown")
            
            # Map out who actually won the race
            winners = r.get("result", [])
            actual_winner_pp = winners[0] if len(winners) > 0 else None
            
            for h in r.get("horses", []):
                all_past_horses.append({
                    "track": track,
                    "dist": dist,
                    "surf": surf,
                    "cond": cond,
                    "horse_name": h.get("name"),
                    "pp": h.get("pp"),
                    "peak": pd.to_numeric(h.get("peak"), errors="coerce"),
                    "lifeFig": pd.to_numeric(h.get("lifeFig"), errors="coerce"),
                    "is_winner": 1 if h.get("pp") == actual_winner_pp else 0
                })
        
        history_df = pd.DataFrame(all_past_horses)
    except Exception as e:
        st.sidebar.error(f"Error reading JSON dataset: {e}")
        history_df = pd.DataFrame()
else:
    st.sidebar.info("Please drop your historical .json backup file here to activate calculations.")
    history_df = pd.DataFrame()


# --- SECTION 2: LIVE CARD PROCESSING ---
st.header("⚡ Fast-Batch Race Processing")
st.write("Drag and drop your upcoming SIM .json race cards below for instant overlay alerts.")

uploaded_cards = st.file_uploader(
    "Upload Upcoming SIM Race Cards", 
    accept_multiple_files=True, 
    type=["json"]
)

if uploaded_cards:
    for card_file in uploaded_cards:
        try:
            card_data = json.load(card_file)
            # Handle files that contain multiple races or single races
            incoming_races = card_data.get("races", [card_data])
            
            for race in incoming_races:
                race_name = race.get("name", "Unknown Race")
                r_dist = race.get("dist", "0")
                r_surf = race.get("surf", "Unknown")
                
                st.subheader(f"📊 Predictions for: {race_name} ({r_dist}F, {r_surf})")
                
                # Dynamic calculations using your historical records
                calc_rows = []
                for horse in race.get("horses", []):
                    h_name = horse.get("name")
                    pp = horse.get("pp")
                    ml_odds = horse.get("ml", "0-1")
                    peak_speed = pd.to_numeric(horse.get("peak"), errors="coerce")
                    lifetime_speed = pd.to_numeric(horse.get("lifeFig"), errors="coerce")
                    
                    # --- AUTOMATED ALGORITHMIC BRAIN ---
                    # Look at past horses in your dataset that ran under similar parameters
                    if not history_df.empty:
                        similar_races = history_df[(history_df["dist"] == r_dist) & (history_df["surf"] == r_surf)]
                        
                        if not similar_races.empty:
                            # Calculate exactly how strong peak speed is on this surface/distance
                            avg_peak_winner = similar_races[similar_races["is_winner"] == 1]["peak"].mean()
                            avg_life_winner = similar_races[similar_races["is_winner"] == 1]["lifeFig"].mean()
                            
                            # Score current entry based on your actual data metrics
                            score = 0
                            if peak_speed >= avg_peak_winner: score += 60
                            if lifetime_speed >= avg_life_winner: score += 40
                        else:
                            # Fallback basic formula if no track matches are found yet
                            score = (peak_speed * 0.6) + (lifetime_speed * 0.4)
                    else:
                        score = (peak_speed * 0.6) + (lifetime_speed * 0.4)
                        
                    calc_rows.append({
                        "PP": pp,
                        "Horse": h_name,
                        "ML Odds": ml_odds,
                        "Peak Rating": peak_speed,
                        "Life Fig": lifetime_speed,
                        "Raw Score": round(score, 1)
                    })
                
                # Turn calculations into an interactive table
                race_results_df = pd.DataFrame(calc_rows)
                
                # Compute true percentage odds distribution across the field
                total_score = race_results_df["Raw Score"].sum()
                if total_score > 0:
                    race_results_df["Win %"] = ((race_results_df["Raw Score"] / total_score) * 100).round(1)
                else:
                    race_results_df["Win %"] = 0.0
                    
                # Rank fields highest score first
                race_results_df = race_results_df.sort_values(by="Win %", ascending=False)
                
                # Call out the high-probability value targets
                top_pct = race_results_df["Win %"].max()
                race_results_df["Bet Signal"] = race_results_df["Win %"].apply(
                    lambda x: "🔥 VALUE BET" if x == top_pct and x > 25 else "PASS"
                )
                
                # Render table inside the web browser view
                st.dataframe(race_results_df, use_container_width=True, hide_index=True)
                
        except Exception as card_error:
            st.error(f"Error parsing race card file {card_file.name}: {card_error}")
else:
    st.info("Ready. Drop your upcoming SIM race files in the area above to check for bets.")
