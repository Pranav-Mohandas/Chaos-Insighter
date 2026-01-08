import json
import time
from datetime import datetime
import requests

class InsightsGenerator:
    def __init__(self, groq_client, model_name="llama-3.1-8b-instant"):
        self.groq_client = groq_client
        self.model_name = model_name
        self.transcript_buffer = []
        self.last_insight_generation = 0
    
    def update_transcript(self, text):
        """Add new transcript text to buffer"""
        self.transcript_buffer.append(text)
        print(f"Updated transcript buffer: {len(self.transcript_buffer)} segments")
    
    def should_generate_insights(self):
        """Not used in end-only approach - always return False"""
        return False  # Never generate during recording in Method 1
    
    def generate_final_insights(self):
        """Generate simple insights from entire session"""
        if not self.transcript_buffer:
            print("No transcript data available for insights generation")
            return None
        
        try:
            # Combine all transcript segments
            full_transcript = " ".join(self.transcript_buffer)
            print(f"Generating insights from {len(self.transcript_buffer)} transcript segments ({len(full_transcript)} characters)")
            
            # Improved prompt with stricter JSON formatting
            simplified_prompt = f"""
            Analyze this audio transcript and extract key insights. Return ONLY valid JSON without any additional text, explanations, or formatting.

            TRANSCRIPT:
            {full_transcript}

            Extract 5-8 meaningful insights focusing on:
            - Important information shared
            - Key learnings or takeaways
            - Notable points discussed
            - Valuable knowledge mentioned

            Response format (ONLY this JSON, nothing else):
            {{"insights": ["insight 1", "insight 2", "insight 3", "insight 4", "insight 5"]}}
            """
            
            response = self.groq_client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": simplified_prompt}],
                temperature=0.1,  # Lower temperature for more consistent formatting
                max_tokens=400    # Reduced tokens to prevent rambling
            )
            
            insights_text = response.choices[0].message.content.strip()
            print(f"Raw AI response: {insights_text}")
            
            # Try to extract JSON if response contains extra text
            insights_data = None
            
            # Method 1: Try direct JSON parsing
            try:
                insights_data = json.loads(insights_text)
            except json.JSONDecodeError:
                # Method 2: Look for JSON within the response
                import re
                json_match = re.search(r'\{.*\}', insights_text, re.DOTALL)
                if json_match:
                    try:
                        insights_data = json.loads(json_match.group())
                    except json.JSONDecodeError:
                        pass
            
            # Method 3: Fallback - extract insights from text manually
            if not insights_data or 'insights' not in insights_data:
                print("Fallback: Manually extracting insights from response")
                # Extract numbered or bulleted items from the response
                lines = insights_text.split('\n')
                manual_insights = []
                for line in lines:
                    line = line.strip()
                    if line and (line.startswith('-') or line.startswith('*') or 
                            any(line.startswith(f"{i}.") for i in range(1, 10))):
                        # Clean up the line
                        cleaned = re.sub(r'^[-*\d\.\s]+', '', line).strip()
                        if cleaned and len(cleaned) > 10:  # Only include substantial insights
                            manual_insights.append(cleaned)
                
                if manual_insights:
                    insights_data = {"insights": manual_insights[:8]}  # Limit to 8
                else:
                    insights_data = {"insights": ["Session contained valuable information but insights could not be extracted in the expected format"]}
            
            print(f"✅ Generated {len(insights_data.get('insights', []))} insights")
            return insights_data
            
        except Exception as e:
            print(f"Insights generation error: {e}")
            return {"insights": [f"Error generating insights: {str(e)}"]}

        
    def get_latest_insights(self):
            """Legacy method - not used in end-only approach"""
            return None
        
    def clear_buffer(self):
            """Clear the transcript buffer"""
            self.transcript_buffer = []
            print("Transcript buffer cleared")
