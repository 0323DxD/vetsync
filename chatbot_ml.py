import pandas as pd
import numpy as np
import os
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
from datasets import load_dataset
import json
import glob
import re

class AstridHybridML:
    def __init__(self, dataset_path):
        self.dataset_path = dataset_path
        self.is_ready = False
        
        # Load ML Models
        # This acts as our A. BASE MODEL
        self.tfidf_vectorizer = TfidfVectorizer(stop_words='english')
        # This acts as our B. ADVANCED SEMANTIC MODEL
        print("Loading SentenceTransformer (all-MiniLM-L6-v2)...")
        self.st_model = SentenceTransformer('all-MiniLM-L6-v2')
        print("Model loaded successfully.")

        self.knowledge_base = []
        self.tfidf_matrix = None
        self.st_embeddings = None
        
        # Cache Paths
        self.cache_dir = os.path.join(self.dataset_path, "processed")
        self.kb_cache = os.path.join(self.cache_dir, "knowledge_base.json")
        self.embeddings_cache = os.path.join(self.cache_dir, "embeddings.npy")
        
        if self._load_cache():
            print(f"Astrid Hybrid ML loaded from cache (Instant Mode) with {len(self.knowledge_base)} items.")
            self.is_ready = True
        else:
            print("No cache found or invalid cache. Initializing knowledge base (this may take a minute on first run)...")
            self.load_datasets()
            self._save_cache()

    def load_datasets(self):
        """Loads and normalizes all requested datasets into a unified knowledge base."""
        # 1. Clinical Data (CSVs)
        clinical_path = os.path.join(self.dataset_path, "clinical")
        if os.path.exists(clinical_path):
            csv_files = glob.glob(os.path.join(clinical_path, "*.csv"))
            for csv_file in csv_files:
                try:
                    basename = os.path.basename(csv_file)
                    df = pd.read_csv(csv_file).fillna("")
                    
                    # Schema-specific logic
                    if "Symptoms" in df.columns and "Description" in df.columns:
                        # Animal disease spreadsheet schema
                        for _, row in df.iterrows():
                            if str(row["Description"]).strip():
                                self.knowledge_base.append({
                                    "condition": row.get("Unnamed: 0", "Unknown Condition"),
                                    "text_corpus": f"{row.get('Symptoms', '')} {row.get('Description', '')} {row.get('Similar Conditions', '')}".lower(),
                                    "severity": "Moderate",
                                    "recommendation": row.get("Treatment", "Seek veterinary care."),
                                    "source": f"Clinical: {basename}"
                                })
                    elif "Species" in df.columns and "Behavior_Change" in df.columns:
                        # Animal_Vet.csv schema
                        for _, row in df.iterrows():
                            behavior = row.get("Behavior_Change", "")
                            if behavior and behavior != "Normal":
                                self.knowledge_base.append({
                                    "condition": f"{row.get('Species', 'Animal')} showing {behavior}",
                                    "text_corpus": f"{row.get('Species', '')} {row.get('Breed', '')} {behavior} {row.get('Discharge_Type', '')} {row.get('Appetite_Change', '')}".lower(),
                                    "severity": "Moderate",
                                    "recommendation": "Monitor behavior and check for other signs of distress.",
                                    "source": f"Clinical: {basename}"
                                })
                    elif "symptoms1" in df.columns:
                        # animal_conditions.csv schema
                        for _, row in df.iterrows():
                            symptoms = " ".join([str(row.get(f'symptoms{i}', '')) for i in range(1,6)])
                            is_dangerous = row.get("Dangerous", "No") == "Yes"
                            self.knowledge_base.append({
                                "condition": "Reported Condition in " + str(row.get("AnimalName", "Animal")),
                                "text_corpus": symptoms.lower(),
                                "severity": "Critical" if is_dangerous else "Low",
                                "recommendation": "Immediate veterinary consultation recommended." if is_dangerous else "Monitor symptoms.",
                                "source": f"Clinical: {basename}"
                            })
                except Exception as e:
                    print(f"Error loading {csv_file}: {e}")

        # 2. Knowledge Base (Markdown Docs)
        docs_path = os.path.join(self.dataset_path, "knowledge_base")
        if os.path.exists(docs_path):
            md_files = glob.glob(os.path.join(docs_path, "*.md"))
            for md_file in md_files:
                try:
                    basename = os.path.basename(md_file)
                    with open(md_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        # Extract headings as conditions
                        sections = re.split(r'^#\s+', content, flags=re.MULTILINE)
                        for section in sections:
                            if section.strip():
                                lines = section.strip().split('\n')
                                title = lines[0].strip()
                                body = " ".join(lines[1:]).strip()
                                if body:
                                    self.knowledge_base.append({
                                        "condition": title if title else basename,
                                        "text_corpus": body.lower(),
                                        "severity": "Low",
                                        "recommendation": "Refer to clinical bibliography for more research context.",
                                        "source": f"Docs: {basename}"
                                    })
                except Exception as e:
                    print(f"Error loading {md_file}: {e}")

        # 3. Agents Logic (Notebooks)
        agents_path = os.path.join(self.dataset_path, "agents")
        if os.path.exists(agents_path):
            nb_files = glob.glob(os.path.join(agents_path, "*.ipynb"))
            for nb_file in nb_files:
                try:
                    with open(nb_file, "r", encoding="utf-8") as f:
                        nb = json.load(f)
                        for cell in nb.get("cells", []):
                            if cell.get("cell_type") == "code":
                                source = "".join(cell.get("source", []))
                                # Look for emergency_types dictionary
                                if "emergency_types =" in source:
                                    # Very simplified extraction for this specific notebook
                                    self.knowledge_base.append({
                                        "condition": "Stuck/Trapped Animal",
                                        "text_corpus": "pigeon stuck behind ac box trapped caught",
                                        "severity": "Medium",
                                        "recommendation": "If safe, try to free it gently or call for help.",
                                        "source": "Agent: Emergency Response"
                                    })
                                    self.knowledge_base.append({
                                        "condition": "Starvation/Dehydration",
                                        "text_corpus": "hungry thirsty dehydrated starving",
                                        "severity": "High",
                                        "recommendation": "Offer small sips of water if safe and call animal care.",
                                        "source": "Agent: Emergency Response"
                                    })
                                    self.knowledge_base.append({
                                        "condition": "Threat/Aggression",
                                        "text_corpus": "attacked aggressive bitten threat",
                                        "severity": "Medium",
                                        "recommendation": "Keep distance and call animal control.",
                                        "source": "Agent: Emergency Response"
                                    })
                except Exception as e:
                    print(f"Error loading {nb_file}: {e}")

        # 4. Hugging Face Dataset (karenwky/pet-health-symptoms-dataset)
        try:
            print("Fetching Hugging Face Dataset (karenwky/pet-health-symptoms-dataset)...")
            hf_ds = load_dataset("karenwky/pet-health-symptoms-dataset", split="train")
            for item in hf_ds:
                text = item.get("text", "")
                condition = item.get("condition", "Unknown Condition")
                if text:
                    self.knowledge_base.append({
                        "condition": condition,
                        "text_corpus": text.lower(),
                        "severity": "Moderate",
                        "recommendation": "Consult a veterinarian for detailed diagnosis regarding these symptoms.",
                        "source": "HuggingFace (karenwky/pet-health-symptoms-dataset)"
                    })
            print(f"HF Dataset loaded: Added {len(hf_ds)} items.")
        except Exception as e:
            print(f"Warning: Could not load Hugging Face dataset: {e}")

        # Generate Dual Vectors
        if self.knowledge_base:
            corpus = [item["text_corpus"] for item in self.knowledge_base]
            
            # A. TF-IDF
            self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(corpus)
            
            # B. Sentence Transformers
            self.st_embeddings = self.st_model.encode(corpus, convert_to_tensor=True)
            self.st_embeddings_np = self.st_embeddings.cpu().numpy()
            
            self.is_ready = True
            print(f"Astrid Hybrid ML initialized with {len(self.knowledge_base)} knowledge items.")
        else:
            print("Warning: No dataset loaded. Astrid Smart Mode will be unavailable.")

    def _load_cache(self):
        """Loads items and embeddings from disk if they exist."""
        try:
            if os.path.exists(self.kb_cache) and os.path.exists(self.embeddings_cache):
                with open(self.kb_cache, "r", encoding="utf-8") as f:
                    self.knowledge_base = json.load(f)
                
                # Load embeddings
                self.st_embeddings_np = np.load(self.embeddings_cache)
                
                # Re-fit TF-IDF (necessary for vocabulary mapping)
                corpus = [item["text_corpus"] for item in self.knowledge_base]
                self.tfidf_matrix = self.tfidf_vectorizer.fit_transform(corpus)
                
                return True
        except Exception as e:
            print(f"Error loading cache: {e}")
        return False

    def _save_cache(self):
        """Saves current items and embeddings to disk."""
        try:
            if not os.path.exists(self.cache_dir):
                os.makedirs(self.cache_dir)
            
            with open(self.kb_cache, "w", encoding="utf-8") as f:
                json.dump(self.knowledge_base, f)
            
            np.save(self.embeddings_cache, self.st_embeddings_np)
            print("Knowledge base cache saved successfully.")
        except Exception as e:
            print(f"Error saving cache: {e}")

    def check_emergency_override(self, message):
        """CRITICAL PRIORITY: Check for immediate life-threatening keywords."""
        emergencies = [
            "severe bleeding", "heatstroke", "seizure", "seizures", "unconscious", 
            "unconsciousness", "breathing difficulty", "hit by", "fracture", "fractures", 
            "poison", "poisoning", "bitten by snake", "broken wing", "broken leg",
            "broke wing", "broke its wing", "broke leg", "broken bone", "broken foot",
            "broken paw", "paralyzed", "not moving", "limping"
        ]
        msg_lower = message.lower()
        for em in emergencies:
            if em in msg_lower:
                return True
        return False

    def get_smart_response(self, message):
        if not self.is_ready or not message.strip():
            return self._fallback_response()

        if self.check_emergency_override(message):
            msg_lower = message.lower()
            rec = "SEEK IMMEDIATE VETERINARY CARE. This matches life-threatening or severe injury symptoms."
            if any(x in msg_lower for x in ["broke", "broken", "fracture"]):
                rec = "KEEP THE ANIMAL STILL. Do not attempt to reset the bone. Seek immediate veterinary care for this suspected fracture/injury."
            
            return {
                "mode": "smart",
                "possible_conditions": ["CRITICAL EMERGENCY / INJURY"],
                "severity": "Critical",
                "recommendation": rec,
                "confidence": 1.0,
                "sources": ["Emergency Override System"]
            }

        # 1. TF-IDF Scoring
        msg_tfidf = self.tfidf_vectorizer.transform([message.lower()])
        tfidf_scores = cosine_similarity(msg_tfidf, self.tfidf_matrix)[0]

        # 2. Sentence Transformer Scoring
        msg_st = self.st_model.encode([message.lower()])
        # Manual cosine similarity for ST
        # (A * B) / (|A| * |B|)
        st_scores = cosine_similarity(msg_st, self.st_embeddings_np)[0]

        # 3. Combined Scoring (50/50 weighting as required)
        combined_scores = (0.5 * tfidf_scores) + (0.5 * st_scores)

        # Get top matches
        top_indices = combined_scores.argsort()[-3:][::-1]
        
        results = []
        highest_conf = 0.0
        sources = set()
        severity = "Low"

        for idx in top_indices:
            score = float(combined_scores[idx])
            if score > 0.15: # Anti-hallucination threshold
                item = self.knowledge_base[idx]
                results.append(item["condition"])
                sources.add(item["source"])
                if score > highest_conf:
                    highest_conf = score
                if item["severity"] == "Critical":
                    severity = "Critical"
                elif item["severity"] == "Moderate" and severity != "Critical":
                    severity = "Moderate"

        if not results:
            return self._fallback_response()

        # Recommendation fallback logic based on top hit
        top_item = self.knowledge_base[top_indices[0]]
        rec = top_item["recommendation"]

        return {
            "mode": "smart",
            "possible_conditions": list(dict.fromkeys(results)), # unique
            "severity": severity,
            "recommendation": rec,
            "confidence": round(highest_conf, 2),
            "sources": list(sources)
        }

    def _fallback_response(self):
        return {
            "mode": "smart",
            "possible_conditions": ["Unknown"],
            "severity": "Unknown",
            "recommendation": "I cannot confidently identify the condition based on available veterinary data. Please consult a licensed veterinarian.",
            "confidence": 0.0,
            "sources": []
        }
