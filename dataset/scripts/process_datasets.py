# -*- coding: utf-8 -*-
"""
VetSync - ASTRID Chatbot Dataset Processor
==========================================
Reads the existing veterinary CSV datasets and builds a structured
knowledge_base.json that the /api/chat endpoint will use to answer
real pet health questions (vomiting, limping, etc.)

Run from the project root:
    python dataset/scripts/process_datasets.py
"""

import csv
import json
import os
import re

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DISEASE_CSV  = os.path.join(BASE_DIR, "Animal disease spreadsheet - Sheet1.csv")
CLINICAL_CSV = os.path.join(BASE_DIR, "veterinary_clinical_data.csv")
OUT_DIR      = os.path.join(BASE_DIR, "processed")
OUT_JSON     = os.path.join(OUT_DIR, "knowledge_base.json")

os.makedirs(OUT_DIR, exist_ok=True)

# ── Symptom keyword → canonical key mapping ──────────────────────────────────
# Maps common words users might type to disease/symptom categories
KEYWORD_MAP = {
    # Digestive
    "vomit":        "vomiting",
    "throwing up":  "vomiting",
    "throw up":     "vomiting",
    "nausea":       "vomiting",
    "diarrhea":     "diarrhea",
    "loose stool":  "diarrhea",
    "loose stools": "diarrhea",
    "watery stool": "diarrhea",
    "constipat":    "constipation",
    "bloat":        "bloating",
    "stomach":      "stomach_pain",
    "abdominal":    "stomach_pain",
    # Eating
    "not eating":   "loss_of_appetite",
    "won't eat":    "loss_of_appetite",
    "will not eat": "loss_of_appetite",
    "wont eat":     "loss_of_appetite",
    "no appetite":  "loss_of_appetite",
    "anorexia":     "loss_of_appetite",
    "refusing food":"loss_of_appetite",
    # Energy
    "lethargy":     "lethargy",
    "lethargic":    "lethargy",
    "tired":        "lethargy",
    "weak":         "weakness",
    "weakness":     "weakness",
    "collapse":     "collapse",
    # Respiratory
    "cough":        "coughing",
    "sneez":        "sneezing",
    "breath":       "breathing_difficulty",
    "wheez":        "breathing_difficulty",
    "panting":      "breathing_difficulty",
    # Skin / External
    "scratch":      "skin_issues",
    "itching":      "skin_issues",
    "itch":         "skin_issues",
    "rash":         "skin_issues",
    "hair loss":    "hair_loss",
    "fur loss":     "hair_loss",
    "dandruff":     "skin_issues",
    "flea":         "parasites",
    "tick":         "parasites",
    "worm":         "parasites",
    "parasite":     "parasites",
    # Locomotion
    "limp":         "limping",
    "limping":      "limping",
    "injur":        "injury",
    "wound":        "injury",
    "bleeding":     "bleeding",
    "blood":        "bleeding",
    "broken":       "fracture",
    "fracture":     "fracture",
    # Temperature / General
    "fever":        "fever",
    "hot":          "fever",
    "temperature":  "fever",
    # Eyes / Ears / Mouth
    "eye":          "eye_issues",
    "discharge":    "discharge",
    "ear":          "ear_issues",
    "tooth":        "dental_issues",
    "teeth":        "dental_issues",
    "dental":       "dental_issues",
    "gum":          "dental_issues",
    # Neurological
    "seizure":      "seizure",
    "tremor":       "tremor",
    "shaking":      "tremor",
    # Urinary
    "urinat":       "urinary_issues",
    "pee":          "urinary_issues",
    "drink":        "excessive_thirst",
    "thirst":       "excessive_thirst",
    # Reproductive
    "pregnant":     "pregnancy",
    "pregnancy":    "pregnancy",
    # Behaviour
    "aggress":      "aggression",
    "biting":       "aggression",
    "depress":      "depression",
    "anxiety":      "anxiety",
}

# ── Built-in knowledge base (from dataset parsing + manual expert entries) ───
BUILTIN_KNOWLEDGE = {
    "vomiting": {
        "label": "Vomiting",
        "emoji": "🤢",
        "possible_causes": [
            "Dietary indiscretion (eating something bad)",
            "Gastritis (stomach inflammation)",
            "Parvovirus (dogs)",
            "Parasites",
            "Pancreatitis",
            "Kidney or liver disease",
            "Foreign object ingestion",
        ],
        "first_aid": [
            "Withhold food for 2–4 hours (water is okay in small amounts)",
            "After fasting, offer bland food: plain boiled chicken + rice",
            "Monitor for blood in vomit — if present, go to vet immediately",
            "Watch for signs of dehydration (dry gums, sunken eyes)",
        ],
        "see_vet_if": [
            "Vomiting lasts more than 24 hours",
            "Blood or unusual colour in vomit",
            "Your pet is also lethargic or in pain",
            "Unable to keep water down",
            "Vomiting + diarrhea together",
        ],
        "species": ["dog", "cat", "general"],
    },
    "diarrhea": {
        "label": "Diarrhea",
        "emoji": "💩",
        "possible_causes": [
            "Sudden diet change",
            "Food intolerance or allergy",
            "Parasites (roundworms, giardia)",
            "Bacterial infection",
            "Parvovirus (dogs)",
            "Stress or anxiety",
            "Inflammatory bowel disease",
        ],
        "first_aid": [
            "Provide fresh water to prevent dehydration",
            "Withhold food for a few hours, then offer bland diet",
            "Plain boiled chicken and white rice is ideal",
            "Do not give human anti-diarrheal medications",
        ],
        "see_vet_if": [
            "Diarrhea contains blood or is black/tarry",
            "Lasts more than 2 days",
            "Your pet is also vomiting or refusing water",
            "Pet is a young puppy or kitten",
            "Signs of dehydration",
        ],
        "species": ["dog", "cat", "general"],
    },
    "loss_of_appetite": {
        "label": "Loss of Appetite / Not Eating",
        "emoji": "🍽️",
        "possible_causes": [
            "Stress or anxiety",
            "Dental pain or mouth issues",
            "Nausea or digestive upset",
            "Fever or infection",
            "Kidney or liver disease",
            "Diabetes",
            "Picky eating or food change",
        ],
        "first_aid": [
            "Ensure your pet has fresh, clean water",
            "Try warming up their food slightly to enhance aroma",
            "Offer a small amount of bland food (boiled chicken)",
            "Remove food after 20 minutes, re-offer later",
            "Reduce stress in their environment",
        ],
        "see_vet_if": [
            "Not eating for more than 48 hours (dogs) or 24 hours (cats)",
            "Also has vomiting, diarrhea, or lethargy",
            "Noticeable weight loss",
            "Painful reaction when touching the abdomen",
        ],
        "species": ["dog", "cat", "general"],
    },
    "lethargy": {
        "label": "Lethargy / Tiredness",
        "emoji": "😴",
        "possible_causes": [
            "Fever or infection",
            "Pain or injury",
            "Anaemia",
            "Heart disease",
            "Kidney disease",
            "Poisoning",
            "Post-vaccination reaction (normal, temporary)",
        ],
        "first_aid": [
            "Ensure your pet is in a comfortable, quiet area",
            "Offer water frequently",
            "Check for signs of pain (whimpering, hunched posture)",
            "Take note of when it started and any recent changes",
        ],
        "see_vet_if": [
            "Lethargy lasts more than 24 hours",
            "Accompanied by vomiting, diarrhea, or difficulty breathing",
            "Your pet collapses or cannot stand",
            "Pale or white gums",
            "No response to usual stimuli",
        ],
        "species": ["dog", "cat", "general"],
    },
    "limping": {
        "label": "Limping / Lameness",
        "emoji": "🐾",
        "possible_causes": [
            "Sprain or strain",
            "Paw injury (cut, thorn, or burn)",
            "Fracture or broken bone",
            "Arthritis or joint disease",
            "Hip dysplasia (common in large dogs)",
            "Luxating patella (cats and small dogs)",
            "Ligament tear (cruciate ligament)",
        ],
        "first_aid": [
            "Limit your pet's movement — keep them calm and still",
            "Check the paw for cuts, thorns, or swelling",
            "Apply a cold compress (cloth-wrapped ice) for 10 mins if swollen",
            "Do not give human pain medications (toxic to pets)",
            "Carry your pet rather than letting them walk if in severe pain",
        ],
        "see_vet_if": [
            "Cannot bear any weight on the leg",
            "Limb appears deformed or at odd angle (fracture)",
            "Severe swelling or visible wound",
            "Limping lasts more than 24 hours",
            "Your pet cries out when you touch the leg",
        ],
        "species": ["dog", "cat", "general"],
    },
    "injury": {
        "label": "Injury / Wound",
        "emoji": "🩹",
        "possible_causes": [
            "Accident or trauma",
            "Animal bite or fight",
            "Laceration (cut)",
            "Burns",
            "Foreign object in wound",
        ],
        "first_aid": [
            "Stay calm — keep your pet calm too",
            "Control bleeding: apply gentle pressure with a clean cloth",
            "Do not remove deeply embedded objects (can cause more damage)",
            "Clean minor wounds gently with clean water or saline",
            "Cover the wound loosely with a clean bandage",
            "Take your pet to the vet as soon as possible",
        ],
        "see_vet_if": [
            "Deep or large wounds",
            "Uncontrolled bleeding (lasts more than 5 minutes of pressure)",
            "Animal bite wounds (high infection risk, often deeper than they look)",
            "Burns",
            "Suspected internal injury",
            "Any significant trauma",
        ],
        "species": ["dog", "cat", "general"],
    },
    "bleeding": {
        "label": "Bleeding",
        "emoji": "🩸",
        "possible_causes": [
            "External wound or laceration",
            "Internal injury",
            "Toxin / rat poison ingestion",
            "Clotting disorder",
        ],
        "first_aid": [
            "Apply firm, gentle pressure with a clean cloth for 5–10 minutes",
            "Do not remove cloth — if soaked through, add more on top",
            "Elevate the limb if possible",
            "Keep pet still and calm",
            "Head to the vet immediately for serious bleeding",
        ],
        "see_vet_if": [
            "Bleeding does not stop within 10 minutes of pressure",
            "Blood is gushing or pulsing",
            "Internal bleeding suspected (swollen abdomen, pale gums)",
            "Blood in urine, stool, or vomit",
            "ANY significant bleeding — this is an emergency",
        ],
        "species": ["dog", "cat", "general"],
    },
    "skin_issues": {
        "label": "Skin Problems / Itching",
        "emoji": "🐕",
        "possible_causes": [
            "Flea allergy dermatitis",
            "Environmental allergies (pollen, dust, mould)",
            "Food allergy",
            "Bacterial skin infection (pyoderma)",
            "Fungal infection (ringworm)",
            "Mange (mites)",
            "Contact dermatitis",
        ],
        "first_aid": [
            "Check for fleas — use a fine-toothed comb on white paper",
            "Bathe with a gentle, pet-safe shampoo",
            "Avoid harsh chemicals or human products on pet skin",
            "Prevent your pet from scratching — use an e-collar if needed",
            "Check food for potential allergens",
        ],
        "see_vet_if": [
            "Severe scratching causing wounds or hair loss",
            "Skin is red, raw, or has open sores",
            "Persistent symptoms despite home care",
            "Spreading rash or lesions",
            "Hair loss in patchy circles (possible ringworm — can spread to humans)",
        ],
        "species": ["dog", "cat", "general"],
    },
    "fever": {
        "label": "Fever / High Temperature",
        "emoji": "🌡️",
        "possible_causes": [
            "Bacterial or viral infection",
            "Inflammation",
            "Immune system reaction",
            "Toxin ingestion",
            "Post-vaccination reaction",
            "Heat stroke",
        ],
        "first_aid": [
            "Normal pet temperature: Dog 38–39.2°C | Cat 38–39.5°C",
            "Apply cool (not cold) wet cloths to paws and neck",
            "Ensure access to cool, fresh water",
            "Move pet to a cool, shaded area",
            "Do NOT give human fever medications (paracetamol/ibuprofen are TOXIC to pets)",
        ],
        "see_vet_if": [
            "Temperature above 40°C",
            "Fever lasts more than 24 hours",
            "Combined with vomiting, diarrhea, or lethargy",
            "Pet is unresponsive or breathing rapidly",
        ],
        "species": ["dog", "cat", "general"],
    },
    "coughing": {
        "label": "Coughing",
        "emoji": "😮‍💨",
        "possible_causes": [
            "Kennel cough (Bordetella) — common in dogs",
            "Upper respiratory infection",
            "Heart disease",
            "Collapsed trachea (small dogs)",
            "Allergies",
            "Foreign object in throat",
            "Parasites (lungworm, heartworm)",
        ],
        "first_aid": [
            "Keep your pet calm and reduce exercise",
            "Ensure good ventilation in your home",
            "Use a harness instead of collar to reduce throat pressure",
            "Humidify the air if dry",
            "Isolate from other pets (kennel cough is contagious)",
        ],
        "see_vet_if": [
            "Coughing is severe or non-stop",
            "Blood in cough",
            "Difficulty breathing or pale/blue gums",
            "Coughing lasts more than 7 days",
            "Swollen abdomen + cough (possible heart disease)",
        ],
        "species": ["dog", "cat", "general"],
    },
    "breathing_difficulty": {
        "label": "Difficulty Breathing",
        "emoji": "😮",
        "possible_causes": [
            "Respiratory infection",
            "Asthma (cats are prone to this)",
            "Heart failure",
            "Allergic reaction",
            "Chest trauma",
            "Heatstroke",
            "Foreign object obstruction",
        ],
        "first_aid": [
            "THIS IS AN EMERGENCY — act quickly",
            "Keep your pet calm and still",
            "Do not restrict the chest or press on the body",
            "Move to a cool, well-ventilated area if overheated",
            "Head to an emergency vet immediately",
        ],
        "see_vet_if": [
            "Any difficulty breathing — GO TO VET IMMEDIATELY",
            "Open-mouth breathing in cats (very serious sign)",
            "Blue, white, or pale gums (oxygen deprivation)",
            "Gasping or gurgling sounds",
        ],
        "species": ["dog", "cat", "general"],
    },
    "seizure": {
        "label": "Seizure / Convulsions",
        "emoji": "⚡",
        "possible_causes": [
            "Epilepsy",
            "Brain tumor",
            "Toxin/poison ingestion",
            "Low blood sugar (hypoglycaemia)",
            "Kidney or liver disease",
            "Heatstroke",
        ],
        "first_aid": [
            "STAY CALM — do not panic",
            "Do NOT put your hand in the pet's mouth",
            "Move away furniture to prevent injury",
            "Time the seizure — if over 5 minutes, go to emergency vet",
            "Keep the area quiet and dark",
            "After seizure, keep pet calm and quiet for 30–60 minutes",
        ],
        "see_vet_if": [
            "First-time seizure — ALWAYS see a vet",
            "Seizure lasts more than 5 minutes",
            "Multiple seizures in one day",
            "Pet does not recover within 30 minutes",
            "Known toxin ingestion",
        ],
        "species": ["dog", "cat", "general"],
    },
    "eye_issues": {
        "label": "Eye Problems",
        "emoji": "👁️",
        "possible_causes": [
            "Conjunctivitis (pink eye)",
            "Corneal ulcer or scratch",
            "Dry eye (keratoconjunctivitis sicca)",
            "Foreign body in eye",
            "Glaucoma",
            "Allergies",
            "Uveitis (eye inflammation)",
        ],
        "first_aid": [
            "Do not rub or touch the eye area",
            "Gently clean discharge with a damp clean cloth",
            "Prevent pet from scratching the eye (e-collar if needed)",
            "Do not apply human eye drops without vet advice",
        ],
        "see_vet_if": [
            "Squinting, pawing at eye, or excessive tearing",
            "Cloudy or opaque eye",
            "Visible injury to the eye",
            "Red, swollen eye",
            "Sudden vision problems",
        ],
        "species": ["dog", "cat", "general"],
    },
    "ear_issues": {
        "label": "Ear Problems",
        "emoji": "👂",
        "possible_causes": [
            "Ear mites (common in cats)",
            "Bacterial or yeast infection",
            "Allergies",
            "Foreign body in ear",
            "Ear polyp or tumour",
            "Water in ear (after bathing)",
        ],
        "first_aid": [
            "Check for redness, odour, or dark discharge",
            "Do not use cotton swabs deep in the ear canal",
            "Clean outer ear with a vet-approved ear cleaner and cotton ball",
            "Stop water from entering ears during baths",
            "Restrict head shaking if severe",
        ],
        "see_vet_if": [
            "Strong odour from the ear",
            "Dark or yellow discharge",
            "Head tilting or loss of balance",
            "Intense scratching at the ear causing wounds",
            "Pain when touching the ear",
        ],
        "species": ["dog", "cat", "general"],
    },
    "parasites": {
        "label": "Parasites (Fleas, Ticks, Worms)",
        "emoji": "🐛",
        "possible_causes": [
            "Exposure to infected animals",
            "Outdoor environment",
            "Contaminated soil",
            "Raw or undercooked meat",
            "Mosquito bites (heartworm)",
        ],
        "first_aid": [
            "Check fur with a fine-toothed comb on white paper",
            "Use vet-approved flea/tick treatments (not human products)",
            "Wash pet's bedding in hot water",
            "Treat ALL pets in the household simultaneously",
            "Vacuum home frequently and dispose of bag",
        ],
        "see_vet_if": [
            "Severe infestation",
            "Your pet is very young, old, or unwell",
            "Signs of anaemia (pale gums, weakness)",
            "Suspected intestinal worms",
            "Suspected heartworm",
        ],
        "species": ["dog", "cat", "general"],
    },
    "dental_issues": {
        "label": "Dental / Mouth Problems",
        "emoji": "🦷",
        "possible_causes": [
            "Plaque and tartar buildup",
            "Periodontal disease (gum disease)",
            "Broken or cracked tooth",
            "Oral ulcers",
            "Tooth abscess",
        ],
        "first_aid": [
            "Check for bad breath, drooling, or pawing at the mouth",
            "Do not force-open the mouth if your pet is in pain",
            "Offer soft food if eating seems painful",
            "Avoid hard toys or bones in suspected dental pain",
        ],
        "see_vet_if": [
            "Difficulty eating or dropping food",
            "Blood from the mouth",
            "Swollen face or jaw",
            "Broken or missing teeth",
            "Heavy drooling that is unusual",
        ],
        "species": ["dog", "cat", "general"],
    },
    "urinary_issues": {
        "label": "Urinary Problems",
        "emoji": "💧",
        "possible_causes": [
            "Urinary tract infection (UTI)",
            "Bladder stones",
            "Kidney disease",
            "Diabetes",
            "Feline lower urinary tract disease (FLUTD) in cats",
            "Prostate issues (intact male dogs)",
        ],
        "first_aid": [
            "Ensure constant access to fresh, clean water",
            "Monitor frequency and appearance of urination",
            "Note any straining, blood, or crying when urinating",
            "Do not restrict water — dehydration worsens kidney issues",
        ],
        "see_vet_if": [
            "Straining to urinate with little or no output (EMERGENCY — possible blockage)",
            "Blood in urine",
            "Frequent urination with small amounts",
            "Crying or pain when urinating",
            "Sudden incontinence",
        ],
        "species": ["dog", "cat", "general"],
    },
    "excessive_thirst": {
        "label": "Excessive Thirst / Drinking",
        "emoji": "🚰",
        "possible_causes": [
            "Diabetes mellitus",
            "Kidney disease",
            "Cushing's disease (dogs)",
            "Hyperthyroidism (cats)",
            "Liver disease",
            "Medications (steroids)",
        ],
        "first_aid": [
            "Note how much water your pet drinks per day",
            "Check if increased thirst is paired with increased urination",
            "Do NOT restrict water — your pet needs it",
        ],
        "see_vet_if": [
            "Noticeably drinking more than usual",
            "Also urinating much more",
            "Weight loss despite eating normally",
            "Lethargy or vomiting alongside increased thirst",
        ],
        "species": ["dog", "cat", "general"],
    },
    "pregnancy": {
        "label": "Pregnancy / Whelping",
        "emoji": "🐣",
        "possible_causes": [],
        "first_aid": [
            "Confirm pregnancy with a vet (ultrasound is most reliable)",
            "Provide a quiet, comfortable nesting area",
            "Increase food intake gradually in later stages",
            "Ensure fresh water is always available",
            "Avoid stressful environments and rough play",
        ],
        "see_vet_if": [
            "Signs of labour lasting more than 2 hours with no birth",
            "Green or black discharge before any puppy/kitten is born",
            "Extreme distress or collapse",
            "Retained placenta",
            "Mother rejecting offspring",
        ],
        "species": ["dog", "cat", "general"],
    },
    "weakness": {
        "label": "Weakness / Collapse",
        "emoji": "😮",
        "possible_causes": [
            "Anaemia",
            "Low blood sugar",
            "Heart problems",
            "Severe infection or sepsis",
            "Toxin ingestion",
            "Neurological issues",
        ],
        "first_aid": [
            "Keep your pet still and calm",
            "Do not give food or water if unconscious",
            "Check gums — pale or white gums = emergency",
            "Keep warm with a blanket",
            "Go to emergency vet immediately",
        ],
        "see_vet_if": [
            "Any collapse — GO TO VET IMMEDIATELY",
            "Pet cannot stand or walk",
            "Pale, blue, or white gums",
            "Loss of consciousness",
        ],
        "species": ["dog", "cat", "general"],
    },
}


def load_disease_csv():
    """Load the animal disease CSV and extract structured symptom–cause–advice data."""
    additions = {}
    if not os.path.exists(DISEASE_CSV):
        print(f"⚠  Disease CSV not found: {DISEASE_CSV}")
        return additions

    with open(DISEASE_CSV, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            disease_name = row.get("", "").strip()
            symptoms_raw = row.get("Symptoms", "").strip()
            advice_raw   = row.get("Advice/ Prevention", "").strip()
            treatment_raw= row.get("Treatment", "").strip()

            if not disease_name or not symptoms_raw:
                continue

            # Split symptoms and advice on ; or \n
            symptoms = [s.strip() for s in re.split(r"[;\n]", symptoms_raw) if s.strip()]
            advice   = [a.strip() for a in re.split(r"[;\n]", advice_raw)   if a.strip()]
            treatments = [t.strip() for t in re.split(r"[;\n]", treatment_raw) if t.strip()]

            # Determine species from disease name
            species = []
            name_lower = disease_name.lower()
            if "dog" in name_lower or "canine" in name_lower:
                species.append("dog")
            if "cat" in name_lower or "feline" in name_lower:
                species.append("cat")
            if not species:
                species = ["dog", "cat", "general"]

            # Create a slug key from disease name
            slug = re.sub(r"[^a-z0-9]+", "_", disease_name.lower()).strip("_")

            additions[slug] = {
                "label":           disease_name,
                "emoji":           "🏥",
                "possible_causes": symptoms,  # symptoms act as identifiers
                "first_aid":       advice[:5] if advice else [],
                "see_vet_if":      treatments[:3] if treatments else ["If condition persists or worsens"],
                "species":         species,
            }

    print(f"[OK] Loaded {len(additions)} entries from Animal Disease CSV")
    return additions


def load_clinical_csv():
    """Build symptom→possible_diagnoses map from the clinical CSV."""
    symptom_disease_map = {}
    if not os.path.exists(CLINICAL_CSV):
        print(f"⚠  Clinical CSV not found: {CLINICAL_CSV}")
        return symptom_disease_map

    with open(CLINICAL_CSV, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            medical_history = row.get("MedicalHistory", "").strip()
            for i in range(1, 6):
                symptom = row.get(f"Symptom_{i}", "").strip().lower()
                if not symptom:
                    continue
                if symptom not in symptom_disease_map:
                    symptom_disease_map[symptom] = set()
                if medical_history:
                    symptom_disease_map[symptom].add(medical_history)

    # Convert sets to sorted lists and pick top entries
    result = {k: sorted(list(v))[:5] for k, v in symptom_disease_map.items() if v}
    print(f"[OK] Loaded {len(result)} symptom entries from Clinical CSV")
    return result


def build_knowledge_base():
    """Merge all sources into the final knowledge_base.json."""
    kb = {}

    # 1. Start with built-in curated entries
    kb.update(BUILTIN_KNOWLEDGE)
    print(f"[OK] Built-in entries loaded: {len(kb)}")

    # 2. Add disease CSV entries (don't overwrite built-in)
    disease_data = load_disease_csv()
    for key, val in disease_data.items():
        if key not in kb:
            kb[key] = val

    # 3. Attach symptom->history map as metadata
    clinical_data = load_clinical_csv()

    # 4. Add keyword_map so the API can resolve user input
    output = {
        "keyword_map":    KEYWORD_MAP,
        "knowledge_base": kb,
        "symptom_history": clinical_data,
        "metadata": {
            "version": "1.0",
            "generated": "2026-04-10",
            "total_entries": len(kb),
            "sources": [
                "Built-in expert knowledge base",
                "Animal disease spreadsheet - Sheet1.csv",
                "veterinary_clinical_data.csv",
            ],
        },
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] Knowledge base saved to: {OUT_JSON}")
    print(f"   Total KB entries : {len(kb)}")
    print(f"   Symptom mappings : {len(clinical_data)}")
    print(f"   Keyword triggers : {len(KEYWORD_MAP)}")


if __name__ == "__main__":
    print("=" * 60)
    print("  VetSync ASTRID - Knowledge Base Builder")
    print("=" * 60)
    build_knowledge_base()
