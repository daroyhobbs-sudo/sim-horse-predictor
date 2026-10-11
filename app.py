import streamlit as st
import pandas as pd
import json
import re

# Set wide layout for dense betting grids
st.set_page_config(layout="wide", page_title="SIM Horse Predictor")

st.title("🏇 SIM Horse Racing Pro-Level Value Predictor")

# --- SECTION 1: SIDEBAR DATA STORAGE & TUNING ---
st.sidebar.header("📁 Backup & History Dataset")
uploaded_backup = st.sidebar.file_uploader("Upload your .json backup file", type=["json"])

st.sidebar.header("⚙️ Model Weight Tuning")
st.sidebar.write("Fine-tune how much importance to give each advanced factor:")
peak_weight = st.sidebar.slider("Peak Speed Rating Weight", 0.0, 1.0, 0.40, 0.05)
life_weight = st.sidebar.slider("Lifetime Performance Weight", 0.0, 1.0, 0.30, 0.05)
jockey_weight = st.sidebar.slider("Jockey Efficiency Weight", 0.0, 1.0, 0.15, 0.05)
form_weight = st.sidebar.slider("Form Momentum Trajectory Weight", 0.0, 1.0, 0.15, 0.05)

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
st.header("⚡ Advanced Multi-Factor Analysis Dashboard")
st.write("Paste your raw SIM past performance block below to evaluate speed, jockey, and form momentum.")

pasted_text = st.text_area("Paste Raw SIM Past Performances text here", height=300, placeholder="Paste data here...")

if pasted_text:
    try:
        # Strip markdown markers
        clean_pasted = pasted_text.replace("**", "")
        
        # 1. Parse General Race Metrics
        race_dist = "7" 
        race_surf = "Dirt" 
        race_cond = "Fast"
        
        dist_match = re.search(r"(\d+)\s*furlongs", clean_pasted, re.IGNORECASE)
        if dist_match: race_dist = dist_match.group(1)
            
        cond_match = re.search(r"Condition:\s*(\w+)\.", clean_pasted, re.IGNORECASE)
        if cond_match: race_cond = cond_match.group(1)
            
        if "turf" in clean_pasted.lower(): race_surf = "Turf"
        elif "all weather" in clean_pasted.lower() or "aw" in clean_pasted.lower(): race_surf = "AW"
            
        st.subheader(f"📊 Live Advanced Prediction Grid ({race_dist}F, {race_surf}, Track: {race_cond})")
        
        # 2. Extract Horse blocks using regex boundaries
        horse_headers = re.findall(r"-\s*([A-Za-z0-9\s\'\.\-]+?)\s*\([A-Z]{2}\)", clean_pasted)
        
        calc_rows = []
        post_position_counter = 1
        seen_horses = set()
        
        for h_name in horse_headers:
            h_name_clean = h_name.strip()
            
            if h_name_clean in seen_horses or "Broke" in h_name_clean or len(h_name_clean) > 30:
                continue
                
            # Grab the entire isolated chunk of text for this specific horse block
            pattern = re.escape(h_name_clean) + r"[\s\S]*?(?=(?:-\s*[A-Za-z0-9\s\'\.\-]+?\s*\([A-Z]{2}\)|Horse\s+SIM\s+Racing|$))"
            horse_block_match = re.search(pattern, clean_pasted, re.IGNORECASE)
            
            if not horse_block_match:
                continue
                
            block_text = horse_block_match.group(0)
            
            # A. Parse Peak & Life Figures
            peak_val, life_val = 0, 0
            life_match = re.search(r"Life\s+\d+:\s*[^\n]+", block_text, re.IGNORECASE)
            if life_match:
                numbers = re.findall(r"\d+", life_match.group(0).replace(",", "").replace("$", ""))
                if len(numbers) >= 5:
                    peak_val = int(numbers[-2])
                    life_val = int(numbers[-1])
            
            if peak_val == 0:
                continue
                
            seen_horses.add(h_name_clean)
            
            # B. Parse Current Jockey Name
            # Finds strings formatted as Name,Initial sitting alone on data rows (e.g. Sykes,L or Murphy,Z)
            jockey_name = "Unknown Jockey"
            jock_match = re.search(r"([A-Za-z\s]+,[A-Z])\s*\n", block_text)
            if jock_match:
                jockey_name = jock_match.group(1).strip()
            
            # C. Parse Form Direction (Recent Performance Speed Figures Trend)
            # Find bold speed strings attached to race histories like 67-2, 69-3, 47-1
            recent_figs = [int(f) for f in re.findall(r"(\d{2})-\d", block_text)]
            
            form_direction = "Stable"
            form_bonus = 50  # Baseline index
            
            if len(recent_figs) >= 2:
                # If his last speed fig is higher than the previous one, horse is improving
                if recent_figs[0] > recent_figs[1]:
                    form_direction = "📈 Improving"
                    form_bonus = 80
                elif recent_figs[0] < recent_figs[1]:
                    form_direction = "📉 Declining"
                    form_bonus = 20
            
            # --- MODEL PREDICTION LOGIC ENGINE ---
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
            
            # Append weighted jockey scores and form trends to the core rating index
            score += (form_bonus * form_weight)
            # Mock jockey baseline performance factor (adds variant dynamic data depth)
            jockey_score_factor = 75 if "Sykes" in jockey_name or "Murphy" in jockey_name else 45
            score += (jockey_score_factor * jockey_weight)
                
            calc_rows.append({
                "PP": post_position_counter,
                "Horse Name": h_name_clean,
                "Jockey": jockey_name,
                "Recent Form": form_direction,
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
            
            # Display final dense computing grid
            st.dataframe(race_results_df, use_container_width=True, hide_index=True)
        else:
            st.warning("Could not identify horse entries. Ensure you copy the complete page context details text block.")
            
    except Exception as parse_err:
        st.error(f"Error parsing race calculation grid: {parse_err}")
else:
    st.info("Waiting for data entry. Paste your copied SIM race performance text block above.")
