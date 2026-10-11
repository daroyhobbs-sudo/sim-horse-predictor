import streamlit as st
import pandas as pd
import json
import re

# Set wide layout for dense betting grids
st.set_page_config(layout="wide", page_title="SIM Horse Predictor")

st.title("🏇 SIM Horse Racing Ultra-Fast Paste Calculator")

# --- SECTION 1: SIDEBAR DATA STORAGE & TUNING ---
st.sidebar.header("📁 Backup & History Dataset")
uploaded_backup = st.sidebar.file_uploader("Upload your .json backup file", type=["json"])

st.sidebar.header("⚙️ Model Weight Tuning")
peak_weight = st.sidebar.slider("Peak Speed Rating Weight", 0.0, 1.0, 0.60, 0.05)
life_weight = st.sidebar.slider("Lifetime Performance Weight", 0.0, 1.0, 0.40, 0.05)

# Keep track of history across app refreshes
history_df = pd.DataFrame()
if uploaded_backup:
    try:
        raw_data = json.load(uploaded_backup)
        races_list = raw_data.get("races", [])
        all_past_horses = []
        valid_race_count = 0
        
        for r in races_list:
            track = r.get("track", "Unknown")
            dist = str(r.get("dist", "0"))
            surf = r.get("surf", "Unknown")
            winners = r.get("result", [])
            
            if winners and isinstance(winners, list) and len(winners) > 0:
                actual_winner_pp = winners[0]
                valid_race_count += 1
                
                for h in r.get("horses", []):
                    all_past_horses.append({
                        "track": track,
                        "dist": dist,
                        "surf": surf,
                        "horse_name": h.get("name"),
                        "pp": h.get("pp"),
                        "peak": pd.to_numeric(h.get("peak"), errors="coerce"),
                        "lifeFig": pd.to_numeric(h.get("lifeFig"), errors="coerce"),
                        "is_winner": 1 if str(h.get("pp")) == str(actual_winner_pp) else 0
                    })
        if all_past_horses:
            history_df = pd.DataFrame(all_past_horses)
            st.sidebar.success(f"✅ Loaded {valid_race_count} completed races from database!")
    except Exception as e:
        st.sidebar.error(f"Error reading JSON dataset: {e}")


# --- SECTION 2: PASTE BOX ENGINE ---
st.header("⚡ Instant-Paste Race Processing")
st.write("Press **Ctrl+A** on the SIM race page, copy everything, and paste it below for split-second calculations.")

# High-capacity text box for raw screen scraping
pasted_text = st.text_area("Paste Raw SIM Past Performances text here", height=300, placeholder="Paste data here...")

if pasted_text:
    try:
        # 1. Parse Race General Details using Regular Expressions
        race_track = "Unknown Track"
        race_dist = "0"
        race_surf = "Unknown Surface"
        
        # Look for pattern like: "Race 34 - 7 furlongs. Dirt."
        race_match = re.search(r"Race\s+\d+\s+-\s+(\d+)\s+furlongs\.\s+(\w+)\.", pasted_text)
        if race_match:
            race_dist = race_match.group(1)
            race_surf = race_match.group(2)
            
        # Look for track header like: "Last Resort Park (AK)"
        track_match = re.search(r"Day-\d+\s+\([\w:]+\)\s+([A-Za-z\s]+)\(", pasted_text)
        if track_match:
            race_track = track_match.group(1).strip()
            
        st.subheader(f"📊 Live Analysis: {race_track} ({race_dist} Furlongs, {race_surf})")
        
        # 2. Chunk text block by individual horse performance records
        # Horse records always start with a bold style bullet delimiter: "- Horse Name (STATE)"
        horse_blocks = re.split(r"\n\s*-\s*", pasted_text)
        
        calc_rows = []
        post_position_counter = 1
        
        for block in horse_blocks:
            # Skip introductory game header info before the first real horse marker
            if "Life " not in block or "Dirt:" not in block:
                continue
                
            lines = [line.strip() for line in block.split("\n") if line.strip()]
            if not lines:
                continue
                
            # Extract horse name from the very first header line of the chunk
            header_line = lines[0]
            name_clean = re.sub(r"\(.*?\)", "", header_line).strip() # Remove state initials
            
            # Extract Peak Rating and Life Figures out of the 'Life' metric line
            # Example structure: "Life 7: 1-3-2 $38,200 73 30"
            peak_val = 0
            life_val = 0
            for line in lines:
                if line.startswith("Life "):
                    metrics = line.split()
                    if len(metrics) >= 5:
                        # Grab the second-to-last item which represents the peak figure rating
                        peak_val = pd.to_numeric(metrics[-2], errors="coerce")
                        life_val = pd.to_numeric(metrics[-1], errors="coerce")
                    break
            
            # Safe assignment defaults
            peak_val = 0 if pd.isna(peak_val) else peak_val
            life_val = 0 if pd.isna(life_val) else life_val
            
            # --- DYNAMIC HISTORICAL MODEL CALCULATIONS ---
            score = 0
            if not history_df.empty:
                similar_races = history_df[(history_df["dist"].astype(str) == str(race_dist)) & (history_df["surf"] == race_surf)]
                
                if not similar_races.empty:
                    avg_peak_winner = similar_races[similar_races["is_winner"] == 1]["peak"].mean()
                    avg_life_winner = similar_races[similar_races["is_winner"] == 1]["lifeFig"].mean()
                    
                    avg_peak_winner = 0 if pd.isna(avg_peak_winner) else avg_peak_winner
                    avg_life_winner = 0 if pd.isna(avg_life_winner) else avg_life_winner
                    
                    if peak_val >= avg_peak_winner and avg_peak_winner > 0: score += (60 * peak_weight)
                    if life_val >= avg_life_winner and avg_life_winner > 0: score += (40 * life_weight)
                else:
                    score = (peak_val * peak_weight) + (life_val * life_weight)
            else:
                score = (peak_val * peak_weight) + (life_val * life_weight)
                
            calc_rows.append({
                "PP": post_position_counter,
                "Horse Name": name_clean,
                "Peak Rating": peak_val,
                "Life Fig": life_val,
                "Raw Rating Score": round(score, 1)
            })
            post_position_counter += 1
            
        if calc_rows:
            race_results_df = pd.DataFrame(calc_rows)
            
            # Distribute calculated probability percentages across the fields
            total_score = race_results_df["Raw Rating Score"].sum()
            if total_score > 0:
                race_results_df["Model Probability %"] = ((race_results_df["Raw Rating Score"] / total_score) * 100).round(1)
            else:
                race_results_df["Model Probability %"] = 0.0
                
            # Rank horses with highest ratings first
            race_results_df = race_results_df.sort_values(by="Model Probability %", ascending=False)
            
            # Assign clear overlay value highlights
            top_prob = race_results_df["Model Probability %"].max()
            race_results_df["Bet Signal"] = race_results_df["Model Probability %"].apply(
                lambda x: "🔥 VALUE CONTENDER" if x == top_prob and x > 0 else "PASS"
            )
            
            st.dataframe(race_results_df, use_container_width=True, hide_index=True)
        else:
            st.warning("Could not identify standard SIM horse rows. Make sure you copied the text completely.")
            
    except Exception as parse_err:
        st.error(f"Error parsing pasted data frame: {parse_err}")
else:
    st.info("Waiting for data. Go to your SIM race card page, select all text, copy it, and paste it in the box above.")
