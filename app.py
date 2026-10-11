import streamlit as st
import pandas as pd
import json

# Set wide layout for dense betting grids
st.set_page_config(layout="wide", page_title="SIM Horse Predictor")

st.title("🏇 SIM Horse Racing High-Pace Value Predictor")

# Helper function to convert Morning Line text odds (e.g., "7-2", "1-5") into implied probability percent
def parse_ml_odds(odds_str):
    try:
        odds_str = str(odds_str).strip()
        if "-" in odds_str:
            num, den = odds_str.split("-")
            n = float(num)
            d = float(den)
            return (d / (n + d)) * 100
        elif "/" in odds_str:
            num, den = odds_str.split("/")
            n = float(num)
            d = float(den)
            return (d / (n + d)) * 100
        return 0.0
    except:
        return 0.0

# --- SECTION 1: SIDEBAR CONTROLS ---
st.sidebar.header("📁 Backup & History Dataset")
uploaded_backup = st.sidebar.file_uploader("Upload your .json backup file", type=["json"])

st.sidebar.header("⚙️ Model Weight Tuning")
st.sidebar.write("Customize how much importance to give each factor:")
peak_weight = st.sidebar.slider("Peak Speed Rating Weight", 0.0, 1.0, 0.60, 0.05)
life_weight = st.sidebar.slider("Lifetime Performance Weight", 0.0, 1.0, 0.40, 0.05)

# Keep track of history across app refreshes
if uploaded_backup:
    try:
        raw_data = json.load(uploaded_backup)
        races_list = raw_data.get("races", [])
        all_past_horses = []
        valid_race_count = 0
        
        for r in races_list:
            track = r.get("track", "Unknown")
            dist = r.get("dist", "0")
            surf = r.get("surf", "Unknown")
            cond = r.get("cond", "Unknown")
            winners = r.get("result", [])
            
            if winners and isinstance(winners, list) and len(winners) > 0:
                actual_winner_pp = winners[0] # Track the first placing horse as winner
                valid_race_count += 1
                
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
                        "is_winner": 1 if str(h.get("pp")) == str(actual_winner_pp) else 0
                    })
        
        if all_past_horses:
            history_df = pd.DataFrame(all_past_horses)
            st.sidebar.success(f"✅ Loaded {valid_race_count} completed races from database!")
        else:
            st.sidebar.warning("⚠️ JSON loaded, but found 0 valid completed races.")
            history_df = pd.DataFrame()
            
    except Exception as e:
        st.sidebar.error(f"Error reading JSON dataset: {e}")
        history_df = pd.DataFrame()
else:
    st.sidebar.info("Please drop your historical .json backup file here to activate calculations.")
    history_df = pd.DataFrame()


# --- SECTION 2: LIVE CARD PROCESSING ---
st.header("⚡ Live Value Betting Dashboard")
st.write("Upload your unrun race cards to find odds discrepancies instantly.")

uploaded_cards = st.file_uploader(
    "Upload Upcoming SIM Race Cards", 
    accept_multiple_files=True, 
    type=["json"]
)

if uploaded_cards:
    for card_file in uploaded_cards:
        try:
            card_data = json.load(card_file)
            incoming_races = card_data.get("races", [card_data])
            
            for race in incoming_races:
                race_name = race.get("name", "Unknown Race")
                r_dist = str(race.get("dist", "0"))
                r_surf = race.get("surf", "Unknown")
                
                st.subheader(f"🏇 Predictions for: {race_name} ({r_dist}F, {r_surf})")
                
                calc_rows = []
                for horse in race.get("horses", []):
                    h_name = horse.get("name")
                    pp = horse.get("pp")
                    ml_odds = horse.get("ml", "0-1")
                    peak_speed = pd.to_numeric(horse.get("peak"), errors="coerce")
                    lifetime_speed = pd.to_numeric(horse.get("lifeFig"), errors="coerce")
                    
                    peak_speed = 0 if pd.isna(peak_speed) else peak_speed
                    lifetime_speed = 0 if pd.isna(lifetime_speed) else lifetime_speed
                    
                    # Convert track morning line string odds into true implied percentage
                    ml_implied_pct = parse_ml_odds(ml_odds)
                    
                    # --- DYNAMIC CALCULATION ALGORITHM ---
                    score = 0
                    if not history_df.empty:
                        similar_races = history_df[(history_df["dist"].astype(str) == r_dist) & (history_df["surf"] == r_surf)]
                        
                        if not similar_races.empty:
                            avg_peak_winner = similar_races[similar_races["is_winner"] == 1]["peak"].mean()
                            avg_life_winner = similar_races[similar_races["is_winner"] == 1]["lifeFig"].mean()
                            
                            avg_peak_winner = 0 if pd.isna(avg_peak_winner) else avg_peak_winner
                            avg_life_winner = 0 if pd.isna(avg_life_winner) else avg_life_winner
                            
                            if peak_speed >= avg_peak_winner and avg_peak_winner > 0: score += (60 * peak_weight)
                            if lifetime_speed >= avg_life_winner and avg_life_winner > 0: score += (40 * life_weight)
                        else:
                            score = (peak_speed * peak_weight) + (lifetime_speed * life_weight)
                    else:
                        score = (peak_speed * peak_weight) + (lifetime_speed * life_weight)
                        
                    calc_rows.append({
                        "PP": pp,
                        "Horse": h_name,
                        "Morning Line": ml_odds,
                        "ML Implied %": round(ml_implied_pct, 1),
                        "Peak Rating": peak_speed,
                        "Life Fig": lifetime_speed,
                        "Raw Score": round(score, 1)
                    })
                
                race_results_df = pd.DataFrame(calc_rows)
                
                # Compute your custom Model Win %
                total_score = race_results_df["Raw Score"].sum()
                if total_score > 0:
                    race_results_df["Model Win %"] = ((race_results_df["Raw Score"] / total_score) * 100).round(1)
                else:
                    race_results_df["Model Win %"] = 0.0
                
                # Calculate the exact edge disparity (Your Win % minus Track Implied %)
                race_results_df["Edge Disparity"] = (race_results_df["Model Win %"] - race_results_df["ML Implied %"]).round(1)
                
                # Rank fields highest edge advantage first
                race_results_df = race_results_df.sort_values(by="Edge Disparity", ascending=False)
                
                # Flag the optimal betting signals
                race_results_df["Bet Signal"] = race_results_df.apply(
                    lambda row: "🔥 VALUE OVERLAY" if row["Edge Disparity"] > 5.0 and row["Model Win %"] > 15.0 else "PASS", axis=1
                )
                
                # Render clean results view
                st.dataframe(race_results_df, use_container_width=True, hide_index=True)
                
        except Exception as card_error:
            st.error(f"Error parsing race card file {card_file.name}: {card_error}")
else:
    st.info("Ready. Drop your upcoming SIM race files in the area above to check for bets.")
