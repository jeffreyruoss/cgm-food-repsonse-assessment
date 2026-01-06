"""Gemini AI integration for analysis and chat."""
import google.generativeai as genai
from config import GEMINI_API_KEY
import pandas as pd


def configure_gemini():
    """Configure Gemini API."""
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        return True
    return False


def get_gemini_model():
    """Get Gemini Flash model instance."""
    if not configure_gemini():
        return None
    return genai.GenerativeModel('gemini-2.0-flash')


def analyze_meal_with_ai(meal_data: dict) -> str:
    """
    Generate an AI assessment of a meal's glucose response.

    Args:
        meal_data: Dict with meal details and glucose response metrics

    Returns:
        AI-generated assessment text
    """
    model = get_gemini_model()
    if not model:
        return "Gemini API not configured. Please add your API key to .env"

    foods = meal_data.get('foods', [])
    foods_str = ', '.join(foods) if foods else 'Unknown'

    prompt = f"""You are a nutrition and glucose metabolism expert. Analyze this meal's glucose response:

## Meal Details:
- Meal: {meal_data.get('group_name', 'Unknown')}
- Foods: {foods_str}
- Time: {meal_data.get('meal_time', 'Unknown')}

## Macros:
- Carbs: {meal_data.get('carbs_g', 0):.1f}g
- Protein: {meal_data.get('protein_g', 0):.1f}g
- Fat: {meal_data.get('fat_g', 0):.1f}g
- Fiber: {meal_data.get('fiber_g', 0):.1f}g
- Sugar: {meal_data.get('sugar_g', 0):.1f}g

## Glucose Response:
- Baseline: {meal_data.get('baseline_glucose', 'N/A')} mg/dL
- Peak: {meal_data.get('peak_glucose', 'N/A')} mg/dL
- Rise: {meal_data.get('glucose_rise', 'N/A')} mg/dL
- Max Drop Velocity: {meal_data.get('max_drop_velocity', 'N/A')} mg/dL/min
- Total Drop from Peak: {meal_data.get('total_drop', 'N/A')} mg/dL
- Crash Detected: {'Yes' if meal_data.get('crash_detected', False) else 'No'}

Please provide a concise assessment (2-3 paragraphs) covering:
1. How well the meal composition supported stable glucose
2. What likely caused the glucose pattern observed
3. Specific suggestions to improve this meal for better glucose response

Focus on actionable insights. Be encouraging but honest."""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating analysis: {e}"


def analyze_crash_event(crash_event: dict, food_context: dict = None) -> str:
    """
    Ask Gemini to analyze why a crash happened.

    Args:
        crash_event: Dict with crash details (magnitude, velocity, times)
        food_context: Dict with meal info (macros, food name)

    Returns:
        AI-generated explanation
    """
    model = get_gemini_model()
    if not model:
        return "Gemini API not configured. Please add your API key to .env"

    prompt = f"""You are a nutrition and glucose metabolism expert. Analyze this glucose crash event:

## Crash Event Details:
- Start Time: {crash_event.get('start_time')}
- End Time: {crash_event.get('end_time')}
- Starting Glucose: {crash_event.get('start_glucose')} mg/dL
- Ending Glucose: {crash_event.get('end_glucose')} mg/dL
- Drop Magnitude: {crash_event.get('drop_magnitude'):.1f} mg/dL
- Drop Velocity: {crash_event.get('max_velocity'):.2f} mg/dL per minute
- Duration: {crash_event.get('duration_minutes'):.0f} minutes
"""

    if food_context:
        prompt += f"""
## Recent Food Consumed:
- Food: {food_context.get('food_name', 'Unknown')}
- Carbs: {food_context.get('carbs_g', 0):.1f}g
- Protein: {food_context.get('protein_g', 0):.1f}g
- Fat: {food_context.get('fat_g', 0):.1f}g
- Fiber: {food_context.get('fiber_g', 0):.1f}g
- Sugar: {food_context.get('sugar_g', 0):.1f}g
"""

    prompt += """
Please provide:
1. A clear explanation of why this crash likely occurred
2. The role of the macronutrients (if food data provided)
3. Specific suggestions to prevent similar crashes
4. Any warning signs to watch for

Keep the response concise and actionable."""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating analysis: {e}"


def predict_crash_timing(meal_data: dict, historical_crashes: list = None) -> str:
    """
    Predict when a crash might occur based on meal composition and history.
    """
    model = get_gemini_model()
    if not model:
        return "Gemini API not configured. Please add your API key to .env"

    prompt = f"""You are a glucose metabolism expert. Based on this meal, predict potential glucose crash timing:

## Meal Details:
- Food: {meal_data.get('food_name', 'Unknown')}
- Carbs: {meal_data.get('carbs_g', 0):.1f}g
- Protein: {meal_data.get('protein_g', 0):.1f}g
- Fat: {meal_data.get('fat_g', 0):.1f}g
- Fiber: {meal_data.get('fiber_g', 0):.1f}g
- Sugar: {meal_data.get('sugar_g', 0):.1f}g
- Protein to Carb Ratio: {meal_data.get('protein_g', 0) / max(meal_data.get('carbs_g', 1), 1):.2f}
"""

    if historical_crashes:
        prompt += f"""
## Historical Pattern (from similar meals):
- Average crashes occurred at: {historical_crashes} minutes after eating
"""

    prompt += """
Please provide:
1. Estimated time to glucose peak (in minutes)
2. Risk assessment for reactive hypoglycemia (Low/Medium/High)
3. If at risk, estimated time when crash might occur
4. Specific timing for when to check glucose levels
5. Quick snack suggestions if a crash is likely

Be specific with timing and keep response concise."""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating prediction: {e}"


def analyze_symptom_mapping(symptom: str, symptom_time: str, glucose_data: list) -> str:
    """
    Analyze glucose data around the time a symptom occurred.
    """
    model = get_gemini_model()
    if not model:
        return "Gemini API not configured. Please add your API key to .env"

    # Format glucose data for context
    glucose_summary = "\n".join([
        f"- {g['timestamp']}: {g['glucose_mg_dl']} mg/dL (velocity: {g.get('velocity_smoothed', 'N/A')} mg/dL/min)"
        for g in glucose_data[-20:]  # Last 20 readings around symptom time
    ])

    prompt = f"""You are a glucose metabolism and symptom expert. Analyze the connection between this symptom and glucose patterns:

## Symptom Reported:
- Symptom: {symptom}
- Time Reported: {symptom_time}

## Glucose Data Around Symptom Time:
{glucose_summary}

Please provide:
1. Analysis of glucose behavior leading up to the symptom
2. Whether the glucose pattern explains the symptom
3. The likely physiological mechanism
4. Recommendations to prevent this in the future
5. When to be concerned and seek medical attention

Be empathetic but evidence-based in your response."""

    try:
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error generating analysis: {e}"


def chat_with_context(
    user_message: str,
    chat_history: list = None,
    glucose_context: str = None,
    food_context: str = None
) -> str:
    """
    General chat with Gemini including glucose/food context.
    """
    model = get_gemini_model()
    if not model:
        return "Gemini API not configured. Please add your API key to .env"

    system_prompt = """You are a helpful AI assistant specialized in continuous glucose monitoring (CGM) data analysis and reactive hypoglycemia management. You have access to the user's glucose and food data.

Key things to remember:
- Be supportive and understanding about glucose management challenges
- Provide evidence-based advice
- Always recommend consulting healthcare providers for medical decisions
- Focus on patterns and actionable insights
- Remember previous conversations when context is provided
"""

    context = ""
    if glucose_context:
        context += f"\n## Recent Glucose Data:\n{glucose_context}\n"
    if food_context:
        context += f"\n## Recent Food Logs:\n{food_context}\n"

    history_text = ""
    if chat_history:
        history_text = "\n## Previous Conversation:\n"
        for msg in chat_history[-10:]:  # Last 10 messages
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            history_text += f"{role.upper()}: {content}\n"

    full_prompt = f"""{system_prompt}
{context}
{history_text}

USER: {user_message}

Please respond helpfully and concisely."""

    try:
        response = model.generate_content(full_prompt)
        return response.text
    except Exception as e:
        return f"Error generating response: {e}"
