"""Crash analysis engine for detecting glucose velocity and danger zones."""
import pandas as pd
import numpy as np
from config import DANGER_ZONE_THRESHOLD


def calculate_glucose_velocity(glucose_df: pd.DataFrame, window_minutes: int = 15) -> pd.DataFrame:
    """
    Calculate the rate of glucose change (velocity) in mg/dL per minute.

    Args:
        glucose_df: DataFrame with 'timestamp' and 'glucose_mg_dl' columns
        window_minutes: Rolling window for smoothing

    Returns:
        DataFrame with added 'velocity' and 'is_danger_zone' columns
    """
    if glucose_df.empty:
        return glucose_df

    df = glucose_df.copy()
    df = df.sort_values('timestamp').reset_index(drop=True)

    # Calculate time differences in minutes
    df['time_diff_min'] = df['timestamp'].diff().dt.total_seconds() / 60

    # Calculate glucose difference
    df['glucose_diff'] = df['glucose_mg_dl'].diff()

    # Calculate velocity (mg/dL per minute)
    df['velocity'] = df['glucose_diff'] / df['time_diff_min']

    # Apply rolling average for smoothing
    window_size = max(1, window_minutes // 5)  # Assuming ~5 min intervals
    df['velocity_smoothed'] = df['velocity'].rolling(window=window_size, center=True, min_periods=1).mean()

    # Mark danger zones (rapid drops)
    df['is_danger_zone'] = df['velocity_smoothed'] <= -DANGER_ZONE_THRESHOLD

    # Clean up intermediate columns
    df = df.drop(columns=['time_diff_min', 'glucose_diff'], errors='ignore')

    return df


def detect_crash_events(glucose_df: pd.DataFrame) -> list[dict]:
    """
    Detect crash events where glucose drops rapidly.

    Returns list of crash events with:
    - start_time, end_time
    - start_glucose, end_glucose
    - drop_magnitude
    - average_velocity
    - duration_minutes
    """
    if glucose_df.empty:
        return []

    if 'velocity_smoothed' not in glucose_df.columns:
        glucose_df = calculate_glucose_velocity(glucose_df)

    # Use vectorized approach to find contiguous blocks of danger zones
    # A crash is a group of consecutive rows where is_danger_zone is True
    danger_mask = glucose_df['is_danger_zone'].fillna(False)

    # Identify where the danger zone status changes
    # shift(1) compares current row with previous row
    # cumsum() creates a unique ID for each contiguous block
    group_ids = (danger_mask != danger_mask.shift()).cumsum()

    # Filter for only danger zone blocks
    danger_blocks = glucose_df[danger_mask].copy()
    if danger_blocks.empty:
        return []

    danger_blocks['block_id'] = group_ids[danger_mask]

    crashes = []
    # Group by block_id and extract stats
    for _, block in danger_blocks.groupby('block_id'):
        if len(block) >= 2:
            start_row = block.iloc[0]
            end_row = block.iloc[-1]

            crashes.append({
                'start_time': start_row['timestamp'],
                'end_time': end_row['timestamp'],
                'start_glucose': start_row['glucose_mg_dl'],
                'end_glucose': end_row['glucose_mg_dl'],
                'drop_magnitude': start_row['glucose_mg_dl'] - end_row['glucose_mg_dl'],
                'average_velocity': block['velocity_smoothed'].mean(),
                'max_velocity': block['velocity_smoothed'].min(),  # Most negative
                'duration_minutes': (end_row['timestamp'] - start_row['timestamp']).total_seconds() / 60
            })

    return crashes


def analyze_meal_response(meal_event: dict) -> dict:
    """
    Analyze the glucose response to a specific meal.

    Returns detailed analysis including:
    - Duration of rise (time to peak)
    - Peak value
    - Duration of drop
    - Crash severity (if any)
    - Recovery time
    """
    glucose_readings = meal_event.get('glucose_readings', [])
    if not glucose_readings:
        return {}

    df = pd.DataFrame(glucose_readings)

    # Only calculate velocity if not already present to avoid redundant work
    if 'velocity_smoothed' not in df.columns:
        df = calculate_glucose_velocity(df)

    # Find peak
    peak_idx = df['glucose_mg_dl'].idxmax()
    peak_row = df.loc[peak_idx]
    baseline = df.iloc[0]['glucose_mg_dl']

    analysis = {
        'baseline_glucose': baseline,
        'peak_glucose': peak_row['glucose_mg_dl'],
        'glucose_rise': peak_row['glucose_mg_dl'] - baseline,
        'time_to_peak_minutes': peak_row['minutes_from_meal'],
        'max_drop_velocity': 0,
        'total_drop': 0,
        'drop_duration_minutes': None,
        'crash_detected': False
    }

    if 'velocity_smoothed' in df.columns:
        analysis['max_drop_velocity'] = df['velocity_smoothed'].min()

    # Analyze post-peak behavior
    post_peak = df.loc[peak_idx:]
    if len(post_peak) > 1:
        # Find lowest point after peak (nadir)
        nadir_idx = post_peak['glucose_mg_dl'].idxmin()
        nadir_row = post_peak.loc[nadir_idx]

        analysis['total_drop'] = peak_row['glucose_mg_dl'] - nadir_row['glucose_mg_dl']
        analysis['drop_duration_minutes'] = nadir_row['minutes_from_meal'] - peak_row['minutes_from_meal']

        crashes = detect_crash_events(post_peak)
        if crashes:
            worst_crash = max(crashes, key=lambda x: x['drop_magnitude'])
            analysis['crash_detected'] = True
            analysis['crash_start_minutes'] = (worst_crash['start_time'] - df.iloc[0]['timestamp']).total_seconds() / 60
            analysis['crash_magnitude'] = worst_crash['drop_magnitude']
            analysis['crash_velocity'] = worst_crash['max_velocity']

    # Calculate protein to carb ratio correlation
    meal_carbs = meal_event.get('carbs_g', 0)
    meal_protein = meal_event.get('protein_g', 0)
    if meal_carbs > 0:
        analysis['protein_carb_ratio'] = meal_protein / meal_carbs
    else:
        analysis['protein_carb_ratio'] = float('inf') if meal_protein > 0 else 0

    return analysis


def get_crash_summary_stats(crash_events: list[dict]) -> dict:
    """Get summary statistics for crash events."""
    if not crash_events:
        return {
            'total_crashes': 0,
            'avg_drop_magnitude': 0,
            'avg_duration': 0,
            'avg_velocity': 0,
        }

    return {
        'total_crashes': len(crash_events),
        'avg_drop_magnitude': np.mean([c['drop_magnitude'] for c in crash_events]),
        'max_drop_magnitude': max([c['drop_magnitude'] for c in crash_events]),
        'avg_duration': np.mean([c['duration_minutes'] for c in crash_events]),
        'avg_velocity': np.mean([c['average_velocity'] for c in crash_events]),
        'worst_velocity': min([c['max_velocity'] for c in crash_events]),
    }
