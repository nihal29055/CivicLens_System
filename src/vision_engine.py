import google.generativeai as genai
import os
import json
from dotenv import load_dotenv

load_dotenv()

class VisionEngine:
    def __init__(self):
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model_name = 'gemini-1.5-flash' 
        print(f">> VISION ENGINE: Locked on to {self.model_name}")
        self.model = genai.GenerativeModel(self.model_name)
        self.embed_model = 'models/text-embedding-004'

    def analyze_image(self, image_path, mode="audit"):
        try:
            if not os.path.exists(image_path):
                raise FileNotFoundError(f"Image file not found: {image_path}")

            img_file = genai.upload_file(image_path)
            
            if mode == "audit":
                prompt = (
                    'Analyze this road repair and visual details. '
                    'Return a JSON object containing:\n'
                    '- "is_repaired": boolean (true/false)\n'
                    '- "material": string (e.g. asphalt, concrete, dirt, etc.)\n'
                    '- "quality_score": integer between 1 and 100\n'
                    '- "visual_fingerprint": string (a highly detailed visual description of the repair site, textures, surroundings, lighting, and unique markers for duplicate checking)\n'
                    'Do not wrap it in markdown block. Return raw JSON.'
                )
            else:
                prompt = (
                    'Analyze the infrastructure issue and visual details in this image. '
                    'Return a JSON object containing:\n'
                    '- "issue_type": string (e.g., Pothole, Clogged Drain, Broken Pipe, Streetlight Out)\n'
                    '- "severity": string ("Critical", "Moderate", or "Low")\n'
                    '- "desc": string (a concise description of the issue)\n'
                    '- "visual_fingerprint": string (a highly detailed visual description of the visual scene, including the pothole/damage shape, road texture, cracks, surrounding environment, lighting, and any unique visual markers for duplicate checking)\n'
                    'Do not wrap it in markdown block. Return raw JSON.'
                )

            response = self.model.generate_content([prompt, img_file])
            text = response.text.strip()
            
            # Clean up markdown code block if present
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            
            return json.loads(text)

        except Exception as e:
            print(f"!! VISION ERROR: {e}")
            return {
                "issue_type": "Pothole",
                "severity": "Critical",
                "desc": "Visual Damage Detected (Fallback)",
                "visual_fingerprint": f"fallback_visual_fingerprint_for_{os.path.basename(image_path)}"
            }

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
            return [0.0] * 768

    def validate_civic_image(self, image_path):
        """
        Pre-screens an image to verify it shows a genuine civic/infrastructure issue.
        Returns a dict:
          {
            "is_civic_issue": bool,
            "confidence": "high" | "medium" | "low",
            "reason": str   # shown to user if rejected
          }
        Valid issues: pothole, road damage, water leakage, pipeline blockage,
                      drainage overflow, broken streetlight, garbage dumping,
                      electricity fault, tree fall, flooding, waterlogging.
        Invalid: selfies, food, pets, interiors, nature scenery, random objects, etc.
        """
        try:
            if not os.path.exists(image_path):
                return {"is_civic_issue": False, "confidence": "high", "reason": "Image file not found."}

            img_file = genai.upload_file(image_path)

            prompt = (
                "You are a strict civic issue validator for a government grievance system.\n"
                "Look at this image carefully and decide: does it show a REAL civic infrastructure problem?\n\n"
                "VALID civic issues (ACCEPT these):\n"
                "- Pothole or road surface damage\n"
                "- Cracked, broken or collapsed road\n"
                "- Water leakage or burst pipe on road/street\n"
                "- Pipeline blockage or overflow\n"
                "- Drainage or sewage overflow on road\n"
                "- Broken or non-functional streetlight\n"
                "- Illegal garbage dumping or overflowing bins\n"
                "- Fallen electricity pole or broken power lines\n"
                "- Tree fall blocking a road or public area\n"
                "- Waterlogging or flooding on public road\n"
                "- Damaged footpath or sidewalk\n\n"
                "INVALID (REJECT these):\n"
                "- Selfies, portraits, faces of people\n"
                "- Food, drinks, household items\n"
                "- Pets or animals in non-civic context\n"
                "- Indoor rooms, offices, homes\n"
                "- Nature scenery (hills, forests, clear sky)\n"
                "- Screenshots, memes, text images\n"
                "- Random objects not related to civic infrastructure\n"
                "- A clean, undamaged road or street (no issue visible)\n\n"
                "Return ONLY a JSON object with these fields:\n"
                '- "is_civic_issue": true or false\n'
                '- "confidence": "high", "medium", or "low"\n'
                '- "detected_issue": string (what you see, in 5-8 words)\n'
                '- "reason": string (one sentence explaining your decision)\n'
                "Return raw JSON only. No markdown."
            )

            response = self.model.generate_content([prompt, img_file])
            text = response.text.strip()

            # Strip markdown fences if present
            if text.startswith("```"):
                lines = text.split("\n")
                lines = [l for l in lines if not l.startswith("```")]
                text = "\n".join(lines).strip()

            result = json.loads(text)
            print(f">> VALIDATION: {result}")
            return result

        except Exception as e:
            print(f"!! VALIDATION ERROR: {e}")
            # On error, allow the image through (fail open) to avoid blocking real issues
            return {
                "is_civic_issue": True,
                "confidence": "low",
                "detected_issue": "Unknown (validation failed)",
                "reason": "Could not validate image. Processing anyway."
            }