"""CSV parsing utilities for Libre CGM and Cronometer data."""
import pandas as pd
from datetime import datetime
from io import StringIO


def parse_libre_csv(file_content: str) -> pd.DataFrame:
    """
    Parse FreeStyle Libre CSV export.

    Libre exports typically have:
    - Device timestamp
    - Record Type (0=historic glucose, 1=scan, etc.)
    - Historic Glucose mg/dL
    """
    try:
        # Libre CSVs often have header rows to skip
        # Try to find the actual data start
        lines = file_content.strip().split('\n')

        # Find the header row (contains 'Device Timestamp' or similar)
        header_idx = 0
        for i, line in enumerate(lines):
            if 'Device Timestamp' in line or 'Timestamp' in line:
                header_idx = i
                break

        # Read the CSV starting from the header
        df = pd.read_csv(
            StringIO('\n'.join(lines[header_idx:])),
            parse_dates=True
        )

        # Normalize column names
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')

        # Find timestamp and glucose columns
        timestamp_col = None
        glucose_col = None

        for col in df.columns:
            if 'timestamp' in col and timestamp_col is None:
                timestamp_col = col
            if 'glucose' in col and 'historic' in col:
                glucose_col = col
            elif 'glucose' in col and glucose_col is None:
                glucose_col = col

        if timestamp_col is None or glucose_col is None:
            raise ValueError("Could not identify timestamp or glucose columns")

        # Create standardized dataframe
        result = pd.DataFrame({
            'timestamp': pd.to_datetime(df[timestamp_col]),
            'glucose_mg_dl': pd.to_numeric(df[glucose_col], errors='coerce')
        })

        # Drop rows with missing glucose values
        result = result.dropna(subset=['glucose_mg_dl'])
        result = result.sort_values('timestamp').reset_index(drop=True)

        return result

    except Exception as e:
        raise ValueError(f"Error parsing Libre CSV: {e}")


def parse_cronometer_csv(file_content: str) -> pd.DataFrame:
    """
    Parse Cronometer CSV export.

    Cronometer exports typically have:
    - Day, Time columns
    - Group (meal grouping like "Breakfast", "Lunch", etc.)
    - Food Name
    - Energy (kcal), Protein, Carbs, Fat, Fiber, Sugar, etc.
    """
    try:
        df = pd.read_csv(StringIO(file_content))

        # Normalize column names
        df.columns = df.columns.str.strip().str.lower().str.replace(' ', '_')

        # Find and combine date/time columns
        if 'day' in df.columns and 'time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['day'] + ' ' + df['time'])
            df['day'] = pd.to_datetime(df['day']).dt.date
        elif 'date' in df.columns and 'time' in df.columns:
            df['timestamp'] = pd.to_datetime(df['date'] + ' ' + df['time'])
            df['day'] = pd.to_datetime(df['date']).dt.date
        elif 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            df['day'] = df['timestamp'].dt.date
        else:
            raise ValueError("Could not identify date/time columns")

        # Map common column variations
        column_mapping = {
            'food_name': ['food_name', 'food', 'name', 'description'],
            'calories': ['energy_(kcal)', 'calories', 'kcal', 'energy'],
            'protein_g': ['protein_(g)', 'protein', 'protein_g'],
            'carbs_g': ['carbs_(g)', 'carbohydrates_(g)', 'carbs', 'carbohydrates', 'carbs_g'],
            'fat_g': ['fat_(g)', 'fat', 'total_fat', 'fat_g'],
            'fiber_g': ['fiber_(g)', 'fiber', 'dietary_fiber', 'fiber_g'],
            'sugar_g': ['sugars_(g)', 'sugar_(g)', 'sugars', 'sugar', 'sugar_g'],
        }

        result_data = {
            'timestamp': df['timestamp'],
            'day': df['day'],
        }

        # Preserve group column
        if 'group' in df.columns:
            result_data['group'] = df['group']
        else:
            result_data['group'] = 'Uncategorized'

        for target_col, possible_names in column_mapping.items():
            for name in possible_names:
                if name in df.columns:
                    result_data[target_col] = pd.to_numeric(df[name], errors='coerce')
                    break
            if target_col not in result_data:
                result_data[target_col] = 0.0

        # Get food name
        for name_col in ['food_name', 'food', 'name', 'description']:
            if name_col in df.columns:
                result_data['food_name'] = df[name_col]
                break

        result = pd.DataFrame(result_data)
        result = result.sort_values('timestamp').reset_index(drop=True)

        return result

    except Exception as e:
        raise ValueError(f"Error parsing Cronometer CSV: {e}")


def group_foods_into_meals(food_df: pd.DataFrame) -> pd.DataFrame:
    """
    Group individual food items into meals based on Day + Group.

    A meal is all foods with the same Group on the same day.
    Returns aggregated meal data with combined macros and list of foods.
    """
    if food_df.empty:
        return pd.DataFrame()

    # Ensure we have required columns
    if 'group' not in food_df.columns:
        food_df['group'] = 'Uncategorized'
    if 'day' not in food_df.columns:
        food_df['day'] = food_df['timestamp'].dt.date

    meals = []

    # Group by day and group name
    for (day, group), group_df in food_df.groupby(['day', 'group']):
        # Get the earliest timestamp as meal time
        meal_time = group_df['timestamp'].min()

        # Aggregate macros
        total_calories = group_df['calories'].sum()
        total_protein = group_df['protein_g'].sum()
        total_carbs = group_df['carbs_g'].sum()
        total_fat = group_df['fat_g'].sum()
        total_fiber = group_df['fiber_g'].sum()
        total_sugar = group_df['sugar_g'].sum()

        # List of foods in this meal (names only, for backward compatibility)
        food_list = group_df['food_name'].tolist()

        # List of foods with timestamps for display
        foods_with_times = [
            {'name': row['food_name'], 'timestamp': row['timestamp']}
            for _, row in group_df.sort_values('timestamp').iterrows()
        ]

        meals.append({
            'day': day,
            'group': group,
            'meal_time': meal_time,
            'foods': food_list,
            'foods_with_times': foods_with_times,
            'food_count': len(food_list),
            'calories': total_calories,
            'protein_g': total_protein,
            'carbs_g': total_carbs,
            'fat_g': total_fat,
            'fiber_g': total_fiber,
            'sugar_g': total_sugar,
        })

    result = pd.DataFrame(meals)
    if result.empty:
        return result
    result = result.sort_values('meal_time').reset_index(drop=True)
    return result


def merge_meals_with_glucose(
    glucose_df: pd.DataFrame,
    meals_df: pd.DataFrame,
    tolerance_minutes: int = 15
) -> pd.DataFrame:
    """
    Merge glucose readings with grouped meals based on timestamps.

    For each meal, find glucose readings within the tolerance window
    and in the hours following the meal. Includes meals with partial
    or no glucose data.
    """
    if meals_df.empty:
        return pd.DataFrame()

    if glucose_df.empty:
        # Return meals with no glucose data
        merged_events = []
        for _, meal_row in meals_df.iterrows():
            merged_events.append({
                'day': meal_row['day'],
                'group': meal_row['group'],
                'meal_time': meal_row['meal_time'],
                'foods': meal_row['foods'],
                'food_count': meal_row['food_count'],
                'calories': meal_row.get('calories', 0),
                'protein_g': meal_row.get('protein_g', 0),
                'carbs_g': meal_row.get('carbs_g', 0),
                'fat_g': meal_row.get('fat_g', 0),
                'fiber_g': meal_row.get('fiber_g', 0),
                'sugar_g': meal_row.get('sugar_g', 0),
                'glucose_readings': [],
                'peak_glucose': None,
                'min_glucose': None,
                'baseline_glucose': None,
                'data_coverage_minutes': 0,
                'data_complete': False,
                'minutes_until_complete': None,
            })
        return pd.DataFrame(merged_events)

    import numpy as np

    # Ensure glucose is sorted for efficient searching
    glucose_df = glucose_df.sort_values('timestamp')
    latest_glucose_time = glucose_df['timestamp'].max()

    merged_events = []
    for _, meal_row in meals_df.iterrows():
        meal_time = meal_row['meal_time']
        meal_start_search = meal_time - pd.Timedelta(minutes=tolerance_minutes)
        meal_end_time = meal_time + pd.Timedelta(hours=3)

        # Efficiently find indices using pandas searchsorted (handles Timestamp objects better than numpy)
        start_idx = glucose_df['timestamp'].searchsorted(meal_start_search)
        end_idx = glucose_df['timestamp'].searchsorted(meal_end_time, side='right')

        related_glucose = glucose_df.iloc[start_idx:end_idx].copy()

        # Calculate data coverage - use overall latest glucose time to determine completeness
        data_complete = latest_glucose_time >= meal_end_time

        if not related_glucose.empty:
            last_reading_time = related_glucose['timestamp'].max()
            data_coverage_minutes = (last_reading_time - meal_time).total_seconds() / 60
        else:
            data_coverage_minutes = 0

        # Calculate minutes until data would be complete (if not complete)
        if data_complete:
            minutes_until_complete = 0
        else:
            # How many more minutes of data do we need?
            minutes_until_complete = max(0, (meal_end_time - latest_glucose_time).total_seconds() / 60)

        # Calculate time from meal for each reading
        if not related_glucose.empty:
            related_glucose['minutes_from_meal'] = (
                (related_glucose['timestamp'] - meal_time).dt.total_seconds() / 60
            ).round(1)

        merged_events.append({
            'day': meal_row['day'],
            'group': meal_row['group'],
            'meal_time': meal_time,
            'foods': meal_row['foods'],
            'foods_with_times': meal_row.get('foods_with_times', []),
            'food_count': meal_row['food_count'],
            'calories': meal_row.get('calories', 0),
            'protein_g': meal_row.get('protein_g', 0),
            'carbs_g': meal_row.get('carbs_g', 0),
            'fat_g': meal_row.get('fat_g', 0),
            'fiber_g': meal_row.get('fiber_g', 0),
            'sugar_g': meal_row.get('sugar_g', 0),
            'glucose_readings': related_glucose.to_dict('records') if not related_glucose.empty else [],
            'peak_glucose': related_glucose['glucose_mg_dl'].max() if not related_glucose.empty else None,
            'min_glucose': related_glucose['glucose_mg_dl'].min() if not related_glucose.empty else None,
            'baseline_glucose': related_glucose['glucose_mg_dl'].iloc[0] if not related_glucose.empty else None,
            'data_coverage_minutes': data_coverage_minutes,
            'data_complete': data_complete,
            'minutes_until_complete': minutes_until_complete,
        })

    return pd.DataFrame(merged_events)
