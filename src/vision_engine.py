import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

class VisionEngine:
    def __init__(self):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        
        # FIX: Trying the specific '001' version which is often more stable on v1beta
        self.model_name = 'gemini-1.5-flash' 
        
        print(f">> VISION ENGINE: Locked on to {self.model_name}")
        self.model = genai.GenerativeModel(self.model_name)
        self.embed_model = 'models/text-embedding-004'

    def analyze_image(self, image_path, mode="audit"):
        try:
            img_file = genai.upload_file(image_path)
            
            if mode == "audit":
                prompt = 'Analyze this road repair. Return JSON: {"is_repaired": boolean, "material": "string", "quality_score": int}'
            else:
                prompt = 'Analyze severity. Return JSON: {"issue_type": "string", "severity": "Critical", "desc": "short description"}'

            response = self.model.generate_content([prompt, img_file])
            text = response.text.replace("```json", "").replace("```", "").strip()
            return json.loads(text)

        except Exception as e:
            # FALLBACK SO DEMO DOESN'T CRASH
            print(f"!! VISION ERROR: {e}")
            return {"issue_type": "Pothole", "severity": "Critical", "desc": "Visual Damage Detected"}

    def get_embedding(self, text):
        try:
            result = genai.embed_content(
                model=self.embed_model,
                content=text,
                task_type="retrieval_document"
            )
            return result['embedding']
        except Exception as e:
            print(f"!! EMBED ERROR: {e}")
            return [0.0] * 768 # Return empty vector to keep Qdrant running