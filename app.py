import streamlit as st
import pandas as pd
import json
import re

# Set wide layout for dense betting grids
st.set_page_config(layout="wide", page_title="SIM Horse Predictor")

st.title("🏇 SIM Horse Racing High-Pace Predictor")

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
        # 1. Parse Distance & Surface using flexible text scanning
        race_dist = "7" 
        race_surf = "Dirt" 
        
        dist_match = re.search(r"(\d+)\s*furlongs", pasted_text, re.IGNORECASE)
        if dist_match:
            race_dist = dist_match.group(1)
            
        if "turf" in pasted_text.lower():
            race_surf = "Turf"
        elif "all weather" in pasted_text.lower() or "aw" in pasted_text.lower():
            race_surf = "AW"
            
        st.subheader(f"官方 Live Prediction Grid ({race_dist} Furlongs, {race_surf})")
        
        # 2. Chop up text precisely at the horse delimiter dash marker
        chunks = pasted_text.split("- ")
        calc_rows = []
        post_position_counter = 1
        
        for chunk in chunks:
            if "Life " not in chunk:
                continue
                
            chunk_lines = [line.strip() for line in chunk.split("\n") if line.strip()]
            if not chunk_lines:
                continue
                
            # Isolate the clean horse name block line
            raw_name = chunk_lines[0].replace("**", "")
            # Split tabs out cleanly to avoid list manipulation object crashes
            if "\t" in raw_name:
                raw_name = raw_name.split("\t")[0]
            clean_name = re.sub(r"\(.*?\)", "", raw_name).strip()
            
            # Skip invalid lines that are part of old race descriptions
            if "Broke" in clean_name or len(clean_name) > 30 or not clean_name:
                continue
                
            peak_val = 0
            life_val = 0
            workout_seconds = []
            
            for line in chunk_lines:
                if "Life " in line:
                    metrics_line = line.replace(",", "").replace("$", "")
                    numbers = re.findall(r"\d+", metrics_line)
                    if len(numbers) >= 5:
                        peak_val = int(numbers[-2])
                        life_val = int(numbers[-1])
                
                # Scan lines for workout timestamps like 0:35.09 or 0:23.23
                clocks = re.findall(r"\d+:\d{2}\.\d{2}", line)
                for clock in clocks:
                    minutes, seconds = clock.split(":")
                    total_secs = (int(minutes) * 60) + float(seconds)
                    workout_seconds.append(total_secs)
            
            # --- MODEL SCORE ENGINE ---
            score = 0
            
            # Route A: For experienced horses with real historical figures
            if peak_val > 0 or life_val > 0:
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
            
            # Route B: For raw unrun horses, grade speed via workout clock timings
            else:
                if workout_seconds:
                    fastest_work = min(workout_seconds)
                    score = max(10, 100 - (fastest_work * 1.5)) 
                else:
                    score = 25.0  # Fallback middle index
                    
            calc_rows.append({
                "PP": post_position_counter,
                "Horse Name": clean_name,
                "Peak Rating": peak_val if peak_val > 0 else "Maiden (Unrated)",
                "Life Fig": life_val if life_val > 0 else "Unrated",
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
            st.warning("No valid horse data blocks identified. Make sure you copy the past performance records fully.")
            
    except Exception as parse_err:
        st.error(f"Error parsing race calculation grid: {parse_err}")
else:
    st.info("Waiting for data entry. Paste your copied SIM race performance text block above.")
