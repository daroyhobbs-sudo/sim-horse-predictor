import streamlit as st
import pandas as pd
import json
import re

# Set wide layout for dense betting grids
st.set_page_config(layout="wide", page_title="SIM Horse Predictor")

st.title("🏇 SIM Horse Racing Indestructible Predictor")

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


# --- CORE PROCESSING FUNCTION ---
def process_raw_text(text_content):
    try:
        # 1. Parse Distance & Surface using flexible keyword scanning
        race_dist = "7" 
        race_surf = "Dirt" 
        
        dist_match = re.search(r"(\d+)\s*furlongs", text_content, re.IGNORECASE)
        if dist_match:
            race_dist = dist_match.group(1)
            
        if "turf" in text_content.lower():
            race_surf = "Turf"
        elif "all weather" in text_content.lower() or "aw" in text_content.lower():
            race_surf = "AW"
            
        st.subheader(f"📊 Live Prediction Grid ({race_dist} Furlongs, {race_surf})")
        
        # 2. Advanced Horse Block Extraction using standard text anchoring patterns
        # This finds any text string that sits right before a "Life [digits]:" signature block
        horse_matches = re.findall(r"(?:-\s*|\*\*\-\s*)([A-Za-z0-9\s\'\.\-\(\)]+?)\s+Life\s+(\d+):", text_content)
        
        calc_rows = []
        post_position_counter = 1
        
        for match in horse_matches:
            raw_name = match[0].strip()
            # Clean up residual jockey/breeding text if it rolled into the name capture group
            clean_name = raw_name.split("\n")[0].split("\t")[0].strip()
            clean_name = re.sub(r"\(.*?\)", "", clean_name).strip() # Remove state notation like (LA)
            
            # Find the exact metrics line for this horse to parse figures
            # We locate "Life [number]:" and grab everything up until the surface block
            metrics_search = re.search(clean_name + r".*?Life\s+\d+:[^\n]+", text_content, re.IGNORECASE)
            
            peak_val = 0
            life_val = 0
            
            if metrics_search:
                metrics_line = metrics_search.group(0).replace(",", "")
                # Find all chunks of integers inside this string
                numbers = re.findall(r"\d+", metrics_line)
                if len(numbers) >= 5:
                    # In the SIM layout: the second-to-last number is Peak, the last number is LifeFig
                    peak_val = int(numbers[-2])
                    life_val = int(numbers[-1])
            
            # --- MODEL CALCULATIONS ---
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
                "Horse Name": clean_name,
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
            st.warning("Could not identify horse blocks. Make sure you select the past performance history lines.")
            
    except Exception as parse_err:
        st.error(f"Error parsing data frame calculations: {parse_err}")


# --- SECTION 2: INPUT SELECTION ---
st.header("⚡ Live Race Entry Point")
input_method = st.radio("Choose how you want to input upcoming SIM race cards:", ["Option 1: Paste Raw Page Text", "Option 2: Upload HTML File(s)"])

if input_method == "Option 1: Paste Raw Page Text":
    pasted_text = st.text_area("Paste Raw SIM Past Performances text here", height=300, placeholder="Select all text on the SIM card, copy, and paste here...")
    if pasted_text:
        process_raw_text(pasted_text)

else:
    uploaded_files = st.file_uploader("Upload SIM Race HTML files", accept_multiple_files=True, type=["html", "htm", "txt"])
    if uploaded_files:
        st.success(f"Loaded {len(uploaded_files)} files. Extracting variables...")
        for file in uploaded_files:
            file_content = file.read().decode("utf-8")
            # Strip standard HTML formatting tags to extract pure raw content strings for processing
            clean_html_text = re.sub(r"<[^>]*>", "\n", file_content)
            process_raw_text(clean_html_text)
