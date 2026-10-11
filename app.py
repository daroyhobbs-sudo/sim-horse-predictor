import streamlit as st
import pandas as pd
import json
import re

# Set wide layout for dense betting grids
st.set_page_config(layout="wide", page_title="SIM Horse Predictor")

st.title("🏇 SIM Horse Racing Fast-Paste Predictor")

# --- SECTION 1: SIDEBAR DATA STORAGE & TUNING ---
st.sidebar.header("📁 Backup & History Dataset")
uploaded_backup = st.sidebar.file_uploader("Upload your .json backup file", type=["json"])

st.sidebar.header("⚙️ Model Weight Tuning")
st.sidebar.write("Adjust calculation weights manually:")
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
                actual_winner_pp = winners
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


# --- SECTION 2: INSTANT PASTE BOX ENGINE ---
st.header("⚡ Instant-Paste Race Processing")
st.write("Go to your SIM race card page, select all text, copy it, and paste it in the box below.")

pasted_text = st.text_area("Paste Raw SIM Past Performances text here", height=300, placeholder="Paste data here...")

if pasted_text:
    try:
        # Strip out markdown symbols right away
        clean_pasted = pasted_text.replace("**", "")
        
        # 1. Parse Distance & Surface using flexible text scanning
        race_dist = "7" 
        race_surf = "Dirt" 
        
        dist_match = re.search(r"(\d+)\s*furlongs", clean_pasted, re.IGNORECASE)
        if dist_match:
            race_dist = dist_match.group(1)
            
        if "turf" in clean_pasted.lower():
            race_surf = "Turf"
        elif "all weather" in clean_pasted.lower() or "aw" in clean_pasted.lower():
            race_surf = "AW"
            
        st.subheader(f"📊 Live Prediction Grid ({race_dist} Furlongs, {race_surf})")
        
        # 2. Match names strictly by catching lines ending with standard breeding indicators
        # Example format: "- Deep Feeling (LA)" followed by a name on the next line or tab
        # This regex matches the actual entry lines and ignores history note texts completely
        matches = re.findall(r"-\s*([A-Za-z0-9\s\'\.\-]+?)\s*\([A-Z]{2}\)", clean_pasted)
        
        calc_rows = []
        post_position_counter = 1
        seen_horses = set()  # Filters out duplicate loop entries
        
        for h_name in matches:
            h_name_clean = h_name.strip()
            
            # Skip historical lines or duplicate processing traps
            if h_name_clean in seen_horses or "Broke" in h_name_clean or len(h_name_clean) > 30:
                continue
                
            # Find the specific "Life" line that belongs *strictly* to this horse entry block
            pattern = re.escape(h_name_clean) + r"[\s\S]*?Life\s+\d+:\s*([^\n]+)"
            metric_match = re.search(pattern, clean_pasted, re.IGNORECASE)
            
            peak_val = 0
            life_val = 0
            
            if metric_match:
                metric_line = metric_match.group(1).replace(",", "").replace("$", "")
                numbers = re.findall(r"\d+", metric_line)
                if len(numbers) >= 2:
                    # In SIM layout: the second-to-last number is Peak, the last number is LifeFig
                    peak_val = int(numbers[-2])
                    life_val = int(numbers[-1])
            
            # Only add to grid if it has realistic horse baseline metrics 
            if peak_val > 0 or life_val > 0:
                seen_horses.add(h_name_clean)
                
                # --- MODEL PREDICTION LOGIC ---
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
                    "Horse Name": h_name_clean,
                    "Peak Rating": peak_val,
                    "Life Fig": life_val,
                    "Model Score": round(score, 1)
                })
                post_position_counter += 1
                
        if calc_rows:
            race_results_df = pd.DataFrame(calc_rows)
            total_score = race_results_df["Model Score"].sum()
            
            if total_score > 0:
                race_results_df["Win %"] = ((race_results_df["Model Score"] / total_score) * 100).round(1)
            else:
                race_results_df["Win %"] = 0.0
                
            race_results_df = race_results_df.sort_values(by="Win %", ascending=False)
            top_prob = race_results_df["Win %"].max()
            race_results_df["Bet Signal"] = race_results_df["Win %"].apply(
                lambda x: "🔥 VALUE CONTENDER" if x == top_prob and x > 0 else "PASS"
            )
            
            st.dataframe(race_results_df, use_container_width=True, hide_index=True)
        else:
            st.warning("Could not identify horse rows. Double check that your selection includes the lines with the horse names and 'Life' stats.")
            
    except Exception as parse_err:
        st.error(f"Error parsing race calculation grid: {parse_err}")
else:
    st.info("Waiting for data entry. Paste your copied SIM race performance text block above.")
