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
    # ── 1. EMERGENCY / INJURY ────────────────────────────────────────────────
    "hit by a car":     "trauma",
    "hit by car":       "trauma",
    "run over":         "trauma",
    "swallowed":        "foreign_body",
    "ate something":    "foreign_body",
    "swallow":          "foreign_body",
    "poison":           "poisoning",
    "chocolate":        "poisoning",
    "toxic":            "poisoning",
    "rat poison":       "poisoning",
    "fell from":        "fall_injury",
    "fall":             "fall_injury",
    "cant stand":       "collapse",
    "can't stand":      "collapse",
    "cannot stand":     "collapse",
    "not moving":       "collapse",
    "unresponsive":     "collapse",
    "cold and":         "collapse",

    # ── 2. GENERAL ILLNESS / SYMPTOMS ────────────────────────────────────────
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
    "not eating":   "loss_of_appetite",
    "won't eat":    "loss_of_appetite",
    "will not eat": "loss_of_appetite",
    "wont eat":     "loss_of_appetite",
    "no appetite":  "loss_of_appetite",
    "anorexia":     "loss_of_appetite",
    "refusing food":"loss_of_appetite",
    "not eaten":    "loss_of_appetite",
    "lethargy":     "lethargy",
    "lethargic":    "lethargy",
    "tired":        "lethargy",
    "weak":         "weakness",
    "weakness":     "weakness",
    "collapse":     "collapse",
    "losing weight":"weight_loss",
    "weight loss":  "weight_loss",
    "cough":        "coughing",
    "sneez":        "sneezing",
    "breath":       "breathing_difficulty",
    "wheez":        "breathing_difficulty",
    "panting":      "breathing_difficulty",
    "fever":        "fever",
    "hot":          "fever",
    "temperature":  "fever",
    "watery eyes":  "eye_issues",

    # ── 3. SKIN / EXTERNAL ──────────────────────────────────────────────────
    "scratch":      "skin_issues",
    "itching":      "skin_issues",
    "itch":         "skin_issues",
    "rash":         "skin_issues",
    "hair loss":    "hair_loss",
    "fur loss":     "hair_loss",
    "losing fur":   "hair_loss",
    "losing feather": "feather_loss",
    "feather loss": "feather_loss",
    "dandruff":     "skin_issues",
    "flea":         "parasites",
    "tick":         "parasites",
    "worm":         "parasites",
    "parasite":     "parasites",
    "white spot":   "ich_disease",

    # ── 4. LOCOMOTION / INJURY ───────────────────────────────────────────────
    "limp":         "limping",
    "limping":      "limping",
    "injur":        "injury",
    "wound":        "injury",
    "bleeding":     "bleeding",
    "blood":        "bleeding",
    "broken":       "fracture",
    "fracture":     "fracture",
    "broke":        "fracture",

    # ── 5. EYES / EARS / MOUTH ───────────────────────────────────────────────
    "eye":          "eye_issues",
    "discharge":    "discharge",
    "ear":          "ear_issues",
    "shaking head": "ear_issues",
    "tooth":        "dental_issues",
    "teeth":        "dental_issues",
    "dental":       "dental_issues",
    "gum":          "dental_issues",

    # ── 6. NEUROLOGICAL ─────────────────────────────────────────────────────
    "seizure":      "seizure",
    "tremor":       "tremor",
    "shaking":      "tremor",

    # ── 7. URINARY ──────────────────────────────────────────────────────────
    "urinat":       "urinary_issues",
    "pee":          "urinary_issues",
    "litter box":   "litter_box",
    "drink":        "excessive_thirst",
    "thirst":       "excessive_thirst",

    # ── 8. REPRODUCTIVE ─────────────────────────────────────────────────────
    "pregnant":     "pregnancy",
    "pregnancy":    "pregnancy",
    "in heat":      "in_heat",
    "spay":         "spay_neuter",
    "neuter":       "spay_neuter",

    # ── 9. BEHAVIOR ─────────────────────────────────────────────────────────
    "aggress":      "aggression",
    "biting":       "aggression",
    "depress":      "depression",
    "anxiety":      "anxiety",
    "barking":      "barking",
    "bark":         "barking",
    "hiding":       "hiding_behavior",
    "chewing":      "chewing_behavior",
    "chew everything": "chewing_behavior",

    # ── 10. SPECIES-SPECIFIC (BIRD) ─────────────────────────────────────────
    "bird":         "bird_general",
    "not flying":   "bird_wing",
    "wing":         "bird_wing",

    # ── 11. SPECIES-SPECIFIC (FISH) ─────────────────────────────────────────
    "fish":         "fish_general",
    "upside down":  "swim_bladder",
    "swim bladder": "swim_bladder",
    "flip":         "swim_bladder",
    "gasping":      "fish_gasping",
    "bottom of":    "fish_bottom",
    "staying at the bottom": "fish_bottom",

    # ── 12. VACCINATION / PREVENTIVE ────────────────────────────────────────
    "vaccin":       "vaccination",
    "immuniz":      "vaccination",
    "deworm":       "deworming",

    # ── 13. NUTRITION / FOOD ────────────────────────────────────────────────
    "feed":         "nutrition",
    "food":         "nutrition",
    "diet":         "nutrition",
    "human food":   "human_food_danger",

    # ── 14. MEDICATION ──────────────────────────────────────────────────────
    "medicine":     "medication_safety",
    "medication":   "medication_safety",
    "human medicine": "human_medicine_danger",
    "treat wound":  "wound_treatment",
    "infection":    "infection",
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

    # ═══════════════════════════════════════════════════════════════════════════
    # EMERGENCY / TRAUMA CASES
    # ═══════════════════════════════════════════════════════════════════════════
    "trauma": {
        "label": "Trauma / Hit by Car",
        "emoji": "🚨",
        "severity": "critical",
        "possible_causes": [
            "Vehicle accident",
            "Heavy impact or fall",
            "Blunt force injury",
        ],
        "first_aid": [
            "THIS IS A LIFE-THREATENING EMERGENCY",
            "Do NOT move your pet unnecessarily — there may be spinal injury",
            "Keep them warm and still with a blanket",
            "If bleeding, apply gentle pressure with a clean cloth",
            "Rush to the nearest vet clinic IMMEDIATELY",
            "Do not attempt home treatment",
        ],
        "see_vet_if": [
            "ANY trauma from a vehicle — ALWAYS see a vet immediately",
            "Even if your pet seems fine, internal injuries may be present",
            "Pale gums, rapid breathing, or inability to stand",
        ],
        "species": ["dog", "cat", "general"],
    },
    "foreign_body": {
        "label": "Swallowed Object / Foreign Body",
        "emoji": "⚠️",
        "severity": "critical",
        "possible_causes": [
            "Ingestion of toys, bones, or small objects",
            "Eating sharp items (needles, glass, wood splinters)",
            "String or thread (especially dangerous for cats)",
        ],
        "first_aid": [
            "Do NOT induce vomiting — sharp objects can cause more damage coming back up",
            "Do NOT pull on strings hanging from mouth (could be attached to intestines)",
            "Note what your pet swallowed and when",
            "Go to the vet immediately for X-ray",
        ],
        "see_vet_if": [
            "Pet swallowed anything sharp — EMERGENCY",
            "Vomiting, gagging, or drooling after swallowing",
            "Abdomen is swollen or painful",
            "Pet stops eating or drinking",
        ],
        "species": ["dog", "cat", "general"],
    },
    "poisoning": {
        "label": "Poisoning / Toxic Ingestion",
        "emoji": "☠️",
        "severity": "critical",
        "possible_causes": [
            "Chocolate (toxic to dogs and cats)",
            "Rat poison / pesticides",
            "Human medications (paracetamol, ibuprofen)",
            "Toxic plants (lilies for cats, sago palm)",
            "Cleaning chemicals",
            "Xylitol (sugar-free gum)",
            "Grapes / raisins / onions / garlic",
        ],
        "first_aid": [
            "THIS IS AN EMERGENCY — Go to vet IMMEDIATELY",
            "Do NOT wait for symptoms to appear",
            "Bring the packaging or substance if possible",
            "Do NOT induce vomiting unless instructed by a vet",
            "Note the time of ingestion and estimated amount",
        ],
        "see_vet_if": [
            "ANY suspected poisoning — GO TO VET NOW",
            "Vomiting, tremors, seizures, or collapse",
            "Drooling, difficulty breathing, or pale gums",
        ],
        "species": ["dog", "cat", "general"],
    },
    "fall_injury": {
        "label": "Fall Injury",
        "emoji": "⬇️",
        "severity": "high",
        "possible_causes": [
            "Fall from height (balcony, window, tree)",
            "Jump from furniture (small pets)",
            "Accidental drop",
        ],
        "first_aid": [
            "Keep your pet warm and still — do not force movement",
            "Check for visible injuries, swelling, or deformity",
            "If your pet cannot walk or is in pain, do not force it",
            "Dalhin agad sa vet for emergency check",
        ],
        "see_vet_if": [
            "ANY fall from a significant height — always see a vet",
            "Limping, crying, or inability to move",
            "Bleeding from nose, mouth, or ears",
            "Fast breathing or lethargy after the fall",
        ],
        "species": ["dog", "cat", "bird", "general"],
    },
    "collapse": {
        "label": "Collapse / Cannot Stand",
        "emoji": "🆘",
        "severity": "critical",
        "possible_causes": [
            "Spinal injury",
            "Severe weakness or dehydration",
            "Poisoning",
            "Heart failure",
            "Low blood sugar",
            "Neurological emergency",
        ],
        "first_aid": [
            "THIS IS AN EMERGENCY",
            "Do NOT force your pet to move or stand",
            "Support with a towel sling if needed for transport",
            "Keep warm and rush to vet immediately",
            "Check for breathing and heartbeat",
        ],
        "see_vet_if": [
            "Pet cannot stand — EMERGENCY, go to vet NOW",
            "Loss of consciousness or unresponsiveness",
            "Pale or blue gums",
            "Known toxin exposure",
        ],
        "species": ["dog", "cat", "rabbit", "hamster", "general"],
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # BEHAVIOR PROBLEMS
    # ═══════════════════════════════════════════════════════════════════════════
    "barking": {
        "label": "Excessive Barking",
        "emoji": "🐕",
        "severity": "low",
        "possible_causes": [
            "Boredom or lack of exercise",
            "Anxiety or fear (separation anxiety, noise phobia)",
            "Territorial behavior",
            "Seeking attention",
            "Pain or discomfort",
            "Hearing changes in older dogs",
        ],
        "first_aid": [
            "Ensure adequate daily exercise (walks, play)",
            "Provide mental stimulation (puzzle toys, training)",
            "Create a comfortable, quiet sleeping area",
            "Avoid yelling — it can worsen the behavior",
            "Consider calming aids (music, pheromone diffusers)",
        ],
        "see_vet_if": [
            "Barking is sudden and unusual (may indicate pain)",
            "Accompanied by pacing, destruction, or other anxiety signs",
            "Your dog also seems hurt or unwell",
        ],
        "species": ["dog"],
    },
    "aggression": {
        "label": "Sudden Aggression",
        "emoji": "😾",
        "severity": "medium",
        "possible_causes": [
            "Pain or hidden injury",
            "Fear or stress",
            "Territorial behavior",
            "Hormonal changes (intact animals)",
            "Neurological issues",
            "Redirected aggression",
        ],
        "first_aid": [
            "Do NOT punish — it can make aggression worse",
            "Give your pet space and remove triggers",
            "Observe what causes the aggressive behavior",
            "Keep children and other pets safe",
            "Consult a vet to rule out medical causes",
        ],
        "see_vet_if": [
            "Sudden aggression with no obvious trigger",
            "Accompanied by other symptoms (lethargy, not eating)",
            "Biting or attacking family members",
            "Aggression worsening over time",
        ],
        "species": ["dog", "cat", "general"],
    },
    "hiding_behavior": {
        "label": "Hiding / Withdrawal",
        "emoji": "🙈",
        "severity": "medium",
        "possible_causes": [
            "Stress or environmental changes",
            "Pain or illness",
            "Fear (new people, loud noises)",
            "New pet or family member in the home",
            "Post-trauma recovery",
        ],
        "first_aid": [
            "Observe muna — could be stress or illness",
            "Create a safe, quiet space for your pet",
            "Do not force interaction — let them come to you",
            "Maintain regular feeding and routine",
            "Monitor for other symptoms (not eating, lethargy)",
        ],
        "see_vet_if": [
            "Hiding for more than 2 days with reduced eating",
            "Accompanied by other symptoms",
            "Your pet is also grooming excessively or not grooming at all",
            "Sudden behavior change with no clear cause",
        ],
        "species": ["dog", "cat", "general"],
    },
    "chewing_behavior": {
        "label": "Destructive Chewing",
        "emoji": "🦴",
        "severity": "low",
        "possible_causes": [
            "Teething (puppies under 6 months)",
            "Boredom or lack of stimulation",
            "Separation anxiety",
            "Dental pain or gum issues",
            "Nutritional deficiency",
        ],
        "first_aid": [
            "Provide appropriate chew toys",
            "Increase daily exercise and mental enrichment",
            "Puppy-proof your home (remove valuable items from reach)",
            "Use bitter apple spray on furniture",
            "Reward good chewing behavior (positive reinforcement)",
        ],
        "see_vet_if": [
            "Chewing on non-food items obsessively (pica)",
            "Bleeding gums or broken teeth",
            "Swallowing pieces of objects (foreign body risk)",
        ],
        "species": ["dog"],
    },
    "litter_box": {
        "label": "Litter Box Avoidance",
        "emoji": "🚽",
        "severity": "medium",
        "possible_causes": [
            "Urinary tract infection (UTI)",
            "Stress or territorial marking",
            "Dirty or unsuitable litter box",
            "Pain when urinating or defecating",
            "New litter type disliked by cat",
            "Location of litter box (too noisy or hard to access)",
        ],
        "first_aid": [
            "Rule out medical causes first — this may be a UTI",
            "Clean litter box daily (cats are very particular)",
            "Ensure one litter box per cat, plus one extra",
            "Try different litter types",
            "Place box in a quiet, accessible location",
        ],
        "see_vet_if": [
            "Straining to urinate (EMERGENCY — possible blockage)",
            "Blood in urine",
            "Crying when using litter box",
            "Sudden change in litter box habits",
        ],
        "species": ["cat"],
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # BIRD-SPECIFIC
    # ═══════════════════════════════════════════════════════════════════════════
    "bird_general": {
        "label": "Bird Health Concern",
        "emoji": "🐦",
        "severity": "medium",
        "possible_causes": [
            "Respiratory infection",
            "Nutritional deficiency",
            "Stress from environment changes",
            "Parasites (mites, lice)",
            "Egg binding (female birds)",
        ],
        "first_aid": [
            "Keep your bird in a warm, quiet environment",
            "Ensure fresh water and food are available",
            "Observe for loss of appetite, fluffed feathers, or labored breathing",
            "Birds hide illness well — any change in behavior is significant",
            "Consult an avian vet if symptoms persist",
        ],
        "see_vet_if": [
            "Open-beak breathing (EMERGENCY for birds)",
            "Fluffed up and not moving for extended time",
            "Discharge from eyes, nose, or beak",
            "Not eating for more than a few hours",
        ],
        "species": ["bird"],
    },
    "bird_wing": {
        "label": "Wing Injury / Cannot Fly",
        "emoji": "🦅",
        "severity": "high",
        "possible_causes": [
            "Wing fracture or sprain",
            "Collision with window or wall",
            "Attack by another animal",
            "Feather damage",
            "Illness causing weakness",
        ],
        "first_aid": [
            "Do NOT force movement or try to set the wing yourself",
            "I-place muna sa cage to prevent stress and further injury",
            "Keep the cage in a warm, dark, quiet area",
            "Do not wrap the wing tightly — birds need to breathe with their chest",
            "Visit an avian vet immediately",
        ],
        "see_vet_if": [
            "Wing is drooping or at an odd angle",
            "Bird is in visible pain or distress",
            "Cannot perch or balance properly",
            "Any suspected fracture",
        ],
        "species": ["bird"],
    },
    "feather_loss": {
        "label": "Feather Loss / Plucking",
        "emoji": "🪶",
        "severity": "medium",
        "possible_causes": [
            "Normal molting (seasonal — usually gradual)",
            "Stress-related plucking (boredom, anxiety, loneliness)",
            "Nutritional deficiency (low protein or vitamins)",
            "Parasites (feather mites, lice)",
            "Skin infection (bacterial or fungal)",
        ],
        "first_aid": [
            "Check for bald patches or irritated skin (not just normal molting)",
            "Ensure a varied, balanced diet with pellets, fruits, and vegetables",
            "Provide enrichment (toys, foraging activities, social interaction)",
            "Keep environment clean and stress-free",
        ],
        "see_vet_if": [
            "Bald spots with red or irritated skin",
            "Excessive plucking (bird pulling its own feathers repeatedly)",
            "Also losing appetite or lethargic",
            "Feather loss is sudden and widespread",
        ],
        "species": ["bird"],
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # FISH-SPECIFIC
    # ═══════════════════════════════════════════════════════════════════════════
    "fish_general": {
        "label": "Fish Health Concern",
        "emoji": "🐟",
        "severity": "medium",
        "possible_causes": [
            "Poor water quality (ammonia, nitrite spikes)",
            "Incorrect temperature or pH",
            "Overfeeding",
            "Bacterial or parasitic infection",
            "Stress from overcrowding or tank mates",
        ],
        "first_aid": [
            "Test water parameters immediately (pH, ammonia, nitrite, nitrate)",
            "Do a 25-50% water change with dechlorinated water",
            "Check water temperature — should match species requirements",
            "Do not overfeed — feed only what fish eat in 2 minutes",
            "Observe for spots, fin damage, or abnormal swimming",
        ],
        "see_vet_if": [
            "Multiple fish dying in short period",
            "Visible parasites, fungus, or open sores",
            "Fish not responding to water changes",
        ],
        "species": ["fish"],
    },
    "swim_bladder": {
        "label": "Swim Bladder Disorder / Flipping",
        "emoji": "🐠",
        "severity": "medium",
        "possible_causes": [
            "Swim bladder disease (most common cause of upside-down swimming)",
            "Overfeeding or constipation",
            "Poor water quality",
            "Bacterial infection",
            "Genetic deformity (especially in fancy goldfish)",
        ],
        "first_aid": [
            "Fast the fish for 24-48 hours",
            "After fasting, feed a small piece of peeled, boiled pea",
            "Check water quality agad — do a partial water change",
            "Lower the water level slightly to reduce stress",
            "Maintain consistent water temperature",
        ],
        "see_vet_if": [
            "Fish cannot right itself after 3 days of treatment",
            "Also showing signs of infection (red spots, fin rot)",
            "Multiple fish affected (may be water quality issue)",
        ],
        "species": ["fish"],
    },
    "fish_gasping": {
        "label": "Fish Gasping at Surface",
        "emoji": "🫧",
        "severity": "high",
        "possible_causes": [
            "Low oxygen levels in water",
            "Ammonia poisoning (most dangerous)",
            "High water temperature (reduces oxygen)",
            "Overcrowding",
            "Gill disease or parasites",
        ],
        "first_aid": [
            "Do an IMMEDIATE 50% water change with dechlorinated water",
            "Add an air pump or airstone to increase oxygen",
            "Check water temperature — cool down if too high",
            "Test for ammonia and nitrite — treat if elevated",
            "Reduce feeding temporarily",
        ],
        "see_vet_if": [
            "Multiple fish gasping (tank-wide issue)",
            "Red or inflamed gills",
            "Fish not responding to water changes within hours",
        ],
        "species": ["fish"],
    },
    "fish_bottom": {
        "label": "Fish Sitting at Bottom",
        "emoji": "🐟",
        "severity": "medium",
        "possible_causes": [
            "Stress from poor water quality",
            "Illness or infection",
            "Bullying from tank mates",
            "Swim bladder issues",
            "Old age or exhaustion",
        ],
        "first_aid": [
            "Test water parameters immediately",
            "Do a partial water change",
            "Check for bullying — isolate if needed",
            "Observe for other symptoms (spots, fin damage, bloating)",
            "Ensure proper water temperature",
        ],
        "see_vet_if": [
            "Fish lying on side and not responding to stimuli",
            "Visible spots, sores, or fin rot",
            "Multiple fish affected simultaneously",
        ],
        "species": ["fish"],
    },
    "ich_disease": {
        "label": "Ich Disease / White Spots",
        "emoji": "⚪",
        "severity": "medium",
        "possible_causes": [
            "Ichthyophthirius multifiliis (Ich) — common protozoan parasite",
            "Introduced through new fish or contaminated equipment",
            "Stress from temperature changes or poor water quality",
        ],
        "first_aid": [
            "Isolate affected fish if possible",
            "Raise water temperature gradually to 28-30°C (speeds up parasite life cycle)",
            "Add aquarium salt (1 tablespoon per 5 gallons)",
            "Use commercial Ich treatment medication",
            "Treat the entire tank, not just the affected fish",
        ],
        "see_vet_if": [
            "White spots spreading rapidly",
            "Fish becoming lethargic or not eating",
            "Not responding to treatment after 7 days",
        ],
        "species": ["fish"],
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # VACCINATION / PREVENTIVE CARE
    # ═══════════════════════════════════════════════════════════════════════════
    "vaccination": {
        "label": "Vaccination Information",
        "emoji": "💉",
        "severity": "low",
        "possible_causes": [],
        "first_aid": [
            "Puppies/kittens: Start vaccines at 6-8 weeks of age",
            "Core vaccines for DOGS: Rabies, Distemper, Parvovirus, Hepatitis",
            "Core vaccines for CATS: Rabies, FVRCP (Feline Viral Rhinotracheitis, Calicivirus, Panleukopenia)",
            "Adult pets need annual boosters or every 3 years depending on vaccine type",
            "Even indoor cats need core vaccines — they can be exposed through windows, visitors, or escaped moments",
            "Ask your VetSync vet for a personalized vaccination schedule",
        ],
        "see_vet_if": [
            "Your pet has never been vaccinated",
            "You're unsure if vaccines are up to date",
            "Pet shows swelling, vomiting, or lethargy after vaccination (rare reaction)",
        ],
        "species": ["dog", "cat", "general"],
    },
    "deworming": {
        "label": "Deworming Information",
        "emoji": "🐛",
        "severity": "low",
        "possible_causes": [],
        "first_aid": [
            "Puppies/kittens: Deworm every 2-4 weeks until 12 weeks old, then monthly until 6 months",
            "Adult pets: Deworm every 3-6 months depending on lifestyle",
            "Outdoor pets or those with flea exposure need more frequent deworming",
            "Use vet-approved dewormers — human dewormers are NOT safe for pets",
            "Signs of worms: scooting, visible worms in stool, bloated belly, weight loss",
        ],
        "see_vet_if": [
            "Visible worms in stool or around the anus",
            "Pet is losing weight despite eating well",
            "Vomiting worms",
            "Young puppy/kitten with bloated belly",
        ],
        "species": ["dog", "cat", "general"],
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # NUTRITION / FOOD
    # ═══════════════════════════════════════════════════════════════════════════
    "nutrition": {
        "label": "Pet Nutrition & Feeding",
        "emoji": "🍖",
        "severity": "low",
        "possible_causes": [],
        "first_aid": [
            "Feed age-appropriate commercial pet food (puppy/kitten vs adult vs senior)",
            "Puppies: 3-4 times/day. Adult dogs: 2 times/day",
            "Kittens: 3-4 times/day. Adult cats: 2 times/day",
            "Always provide fresh, clean water",
            "Avoid: chocolate, grapes, raisins, onions, garlic, xylitol, alcohol, caffeine",
            "BIRDS: Seeds, pellets, fruits (apple, banana), vegetables. Avoid avocado and chocolate",
            "Treats should be less than 10% of daily food intake",
        ],
        "see_vet_if": [
            "Pet is overweight or underweight",
            "You need a specific diet plan for a health condition",
            "Pet has food allergies or sensitivities",
        ],
        "species": ["dog", "cat", "bird", "general"],
    },
    "human_food_danger": {
        "label": "Human Food Safety for Pets",
        "emoji": "🚫",
        "severity": "medium",
        "possible_causes": [],
        "first_aid": [
            "DANGEROUS foods for pets: Chocolate, grapes, raisins, onions, garlic, xylitol (sugar-free gum), avocado, macadamia nuts, alcohol, caffeine",
            "SAFE in small amounts: Plain cooked chicken, plain rice, carrots, pumpkin, blueberries",
            "CATS: Avoid dairy (most cats are lactose intolerant), raw fish, and raw eggs",
            "DOGS: No cooked bones (can splinter), no fatty scraps",
            "When in doubt, DO NOT give it to your pet",
        ],
        "see_vet_if": [
            "Pet ate any toxic food — go to vet IMMEDIATELY",
            "Vomiting, diarrhea, or tremors after eating human food",
        ],
        "species": ["dog", "cat", "general"],
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # REPRODUCTION
    # ═══════════════════════════════════════════════════════════════════════════
    "in_heat": {
        "label": "Pet in Heat / Estrus",
        "emoji": "💕",
        "severity": "medium",
        "possible_causes": [],
        "first_aid": [
            "Keep your pet indoors and away from other animals",
            "Use pet diapers if needed for dogs in heat",
            "Increase supervision — pets in heat will try to escape",
            "Be patient — behavioral changes (vocalization, restlessness) are normal",
            "Consider spaying/neutering to prevent unwanted pregnancies and health risks",
        ],
        "see_vet_if": [
            "Prolonged heat cycle (more than 3 weeks for dogs)",
            "Unusual discharge (green, foul-smelling — may indicate pyometra)",
            "Your pet is distressed or in pain",
            "You want to discuss spaying/neutering",
        ],
        "species": ["dog", "cat", "general"],
    },
    "spay_neuter": {
        "label": "Spaying / Neutering",
        "emoji": "✂️",
        "severity": "low",
        "possible_causes": [],
        "first_aid": [
            "Generally recommended at around 6 months of age",
            "Benefits: Prevents unwanted litters, reduces cancer risk, decreases roaming and aggression",
            "For large dog breeds, your vet may recommend waiting until 12-18 months",
            "Recovery is typically 7-14 days with proper care",
            "Book an appointment with your VetSync vet to discuss the best timing",
        ],
        "see_vet_if": [
            "You want to schedule the procedure",
            "Your pet is in heat and you want to discuss timing",
            "Post-surgery concerns (swelling, discharge, lethargy beyond 48 hours)",
        ],
        "species": ["dog", "cat", "rabbit", "general"],
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # MEDICATION / TREATMENT
    # ═══════════════════════════════════════════════════════════════════════════
    "medication_safety": {
        "label": "Medication Safety for Pets",
        "emoji": "💊",
        "severity": "medium",
        "possible_causes": [],
        "first_aid": [
            "NEVER give human medication to pets without vet approval",
            "Paracetamol (Tylenol) is TOXIC to cats — even one tablet can be fatal",
            "Ibuprofen is TOXIC to both dogs and cats",
            "Always use vet-prescribed medications at the correct dosage",
            "Store medications securely — pets can chew through bottles",
            "When in doubt, call your VetSync vet before giving any medication",
        ],
        "see_vet_if": [
            "You accidentally gave human medication to your pet — EMERGENCY",
            "Pet is showing side effects from medication",
            "You need guidance on safe pet medications",
        ],
        "species": ["dog", "cat", "general"],
    },
    "human_medicine_danger": {
        "label": "Human Medicine for Pets — DANGER",
        "emoji": "⛔",
        "severity": "high",
        "possible_causes": [],
        "first_aid": [
            "NO. Most human medications are DANGEROUS or FATAL to pets",
            "Paracetamol/Tylenol: TOXIC — especially to cats (one tablet can be fatal)",
            "Ibuprofen/Advil: TOXIC — causes kidney failure and stomach ulcers in pets",
            "Aspirin: TOXIC to cats, potentially dangerous for dogs without vet guidance",
            "Only give medications your vet has specifically prescribed for YOUR pet",
        ],
        "see_vet_if": [
            "If you already gave human medicine to your pet — go to vet IMMEDIATELY",
            "Vomiting, lethargy, or collapse after taking any medication",
        ],
        "species": ["dog", "cat", "general"],
    },
    "wound_treatment": {
        "label": "Home Wound Care",
        "emoji": "🩹",
        "severity": "medium",
        "possible_causes": [],
        "first_aid": [
            "For MINOR wounds only (small cuts, scratches):",
            "Clean gently with clean water or saline solution",
            "Apply pet-safe antiseptic (NOT hydrogen peroxide on deep wounds)",
            "Bandage loosely — do not wrap too tight",
            "Prevent licking with an e-collar (cone)",
            "For DEEP or LARGE wounds — go to vet immediately, do not attempt home treatment",
        ],
        "see_vet_if": [
            "Deep, large, or gaping wounds",
            "Animal bite wounds (high infection risk)",
            "Wound that is red, swollen, or has discharge (infected)",
            "Bleeding that doesn't stop within 10 minutes",
        ],
        "species": ["dog", "cat", "general"],
    },
    "infection": {
        "label": "Signs of Infection",
        "emoji": "🦠",
        "severity": "medium",
        "possible_causes": [
            "Bacterial infection from wounds",
            "Viral infection",
            "UTI or internal infection",
            "Post-surgical infection",
        ],
        "first_aid": [
            "Signs of infection: redness, swelling, discharge, warmth, or bad smell",
            "Do NOT self-treat with antibiotics — wrong dosage is dangerous",
            "Keep any wound areas clean and dry",
            "Monitor your pet's temperature if possible",
            "Visit your vet for proper diagnosis and treatment",
        ],
        "see_vet_if": [
            "Fever, lethargy, or loss of appetite with wound",
            "Discharge is green, yellow, or foul-smelling",
            "Area is hot, swollen, and painful",
            "Infection is spreading or not improving",
        ],
        "species": ["dog", "cat", "general"],
    },

    # ═══════════════════════════════════════════════════════════════════════════
    # OTHER COMMON CONDITIONS
    # ═══════════════════════════════════════════════════════════════════════════
    "weight_loss": {
        "label": "Weight Loss",
        "emoji": "📉",
        "severity": "medium",
        "possible_causes": [
            "Parasites (worms)",
            "Diabetes",
            "Kidney disease",
            "Hyperthyroidism (cats)",
            "Cancer",
            "Dental pain making eating difficult",
            "Stress or dietary issues",
        ],
        "first_aid": [
            "Monitor your pet's food intake carefully",
            "Weigh your pet weekly to track changes",
            "Ensure food is fresh and palatable",
            "Check teeth and mouth for pain or issues",
        ],
        "see_vet_if": [
            "Unexplained weight loss — always see a vet",
            "Losing weight despite eating normally",
            "Accompanied by increased thirst or urination",
            "Visible ribs or hip bones (body condition too thin)",
        ],
        "species": ["dog", "cat", "general"],
    },
    "sneezing": {
        "label": "Sneezing",
        "emoji": "🤧",
        "severity": "low",
        "possible_causes": [
            "Upper respiratory infection",
            "Allergies (dust, pollen)",
            "Foreign object in nose",
            "Dental disease (upper teeth roots near nasal passages)",
            "Feline herpesvirus (cats)",
        ],
        "first_aid": [
            "Monitor muna — occasional sneezing is normal",
            "Clean any nasal discharge gently with a damp cloth",
            "Ensure good ventilation in your home",
            "Keep your pet away from smoke, strong perfumes, or dusty areas",
        ],
        "see_vet_if": [
            "Sneezing with colored discharge (green/yellow)",
            "Persistent sneezing for more than a few days",
            "Also has eye discharge, coughing, or fever",
            "Bloody nasal discharge",
        ],
        "species": ["dog", "cat", "general"],
    },
    "hair_loss": {
        "label": "Hair/Fur Loss",
        "emoji": "🐩",
        "severity": "medium",
        "possible_causes": [
            "Allergies (food, environmental, flea allergy)",
            "Ringworm (fungal — can spread to humans)",
            "Mange (mites — sarcoptic or demodectic)",
            "Hormonal imbalance (thyroid, Cushing's)",
            "Stress-related over-grooming",
            "Bacterial skin infection",
        ],
        "first_aid": [
            "Check for patterns — circular patches may indicate ringworm",
            "Look for fleas or flea dirt in the fur",
            "Bathe with gentle, vet-approved shampoo",
            "Do not use human products on your pet",
        ],
        "see_vet_if": [
            "Circular bald patches (possible ringworm — also affects humans)",
            "Intense itching causing wounds",
            "Hair loss spreading to new areas",
            "Accompanied by skin redness, sores, or scaling",
        ],
        "species": ["dog", "cat", "general"],
    },
    "fracture": {
        "label": "Fracture / Broken Bone",
        "emoji": "🦴",
        "severity": "high",
        "possible_causes": [
            "Trauma (hit by car, fall from height)",
            "Animal fight",
            "Accidental step-on (small pets)",
            "Metabolic bone disease (poor nutrition in birds/reptiles)",
        ],
        "first_aid": [
            "Do NOT try to set the bone yourself",
            "Keep your pet still and calm — restrict movement",
            "Support the injured area carefully during transport",
            "Use a flat surface (board, towel) as a makeshift stretcher",
            "Go to vet immediately for X-ray and proper treatment",
        ],
        "see_vet_if": [
            "Limb at an unnatural angle — ALWAYS see a vet",
            "Swelling, bruising, or intense pain",
            "Pet cannot bear weight on the limb",
            "Any suspected broken bone",
        ],
        "species": ["dog", "cat", "bird", "general"],
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


def load_vet_med_articles():
    """
    Load vet_med dataset (HuggingFace: houck2040/vet_med) and extract
    short context snippets relevant to pet health topics.
    Since this dataset is veterinary articles (not Q&A), we pick paragraphs
    that mention health-related keywords for LLM grounding.
    """
    VET_MED_CSV = os.path.join(BASE_DIR, "raw", "vet_med_train.csv")
    snippets = []

    if not os.path.exists(VET_MED_CSV):
        print(f"[WARN] vet_med CSV not found: {VET_MED_CSV}")
        print("       Run: python dataset/scripts/download_vet_med.py")
        return snippets

    # Health-related terms to look for in the articles
    HEALTH_TERMS = {
        "disease", "infection", "vaccine", "treatment", "symptom", "parasite",
        "surgery", "diagnosis", "antibiotic", "virus", "bacteria", "cancer",
        "pneumonia", "arthritis", "dental", "obesity", "laminitis", "colic",
        "respiratory", "fever", "inflammation", "pain", "immune", "toxin",
        "allergy", "dermatitis", "clinical", "veterinarian", "emergency",
        "heartworm", "flea", "tick", "worm", "rabies", "parvovirus",
        "kidney", "liver", "pancreatitis", "diabetes",
    }

    with open(VET_MED_CSV, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            story = row.get("story", "").strip()
            if not story or len(story) < 80:
                continue

            # Only keep paragraphs that discuss health topics
            story_lower = story.lower()
            matched_terms = [t for t in HEALTH_TERMS if t in story_lower]
            if len(matched_terms) >= 2:
                # Truncate to a useful context size (max 500 chars)
                snippet = story[:500].strip()
                if len(story) > 500:
                    # Cut at last sentence boundary
                    last_period = snippet.rfind(".")
                    if last_period > 200:
                        snippet = snippet[:last_period + 1]
                snippets.append({
                    "text": snippet,
                    "keywords": matched_terms[:5],
                })

            if len(snippets) >= 300:
                break

    print(f"[OK] Loaded {len(snippets)} health-relevant snippets from vet_med dataset")
    return snippets


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

    # 4. Load vet_med article snippets for LLM grounding
    vet_med_snippets = load_vet_med_articles()

    # 5. Load VetCare Pro chatbot dataset
    vetcare_entries = load_vetcare_pro_csv()

    # 6. Build unified output
    output = {
        "keyword_map":      KEYWORD_MAP,
        "knowledge_base":   kb,
        "symptom_history":  clinical_data,
        "vet_med_snippets": vet_med_snippets,
        "vetcare_pro":      vetcare_entries,
        "metadata": {
            "version": "3.0",
            "generated": "2026-04-11",
            "total_entries": len(kb),
            "vetcare_pro_count": len(vetcare_entries),
            "vet_med_snippets_count": len(vet_med_snippets),
            "sources": [
                "Built-in expert knowledge base",
                "Animal disease spreadsheet - Sheet1.csv",
                "veterinary_clinical_data.csv",
                "houck2040/vet_med (HuggingFace)",
                "VetCare Pro Chatbot Dataset (vetcare_pro_chatbot.csv)",
            ],
        },
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[DONE] Knowledge base saved to: {OUT_JSON}")
    print(f"   Total KB entries      : {len(kb)}")
    print(f"   Symptom mappings      : {len(clinical_data)}")
    print(f"   Keyword triggers      : {len(KEYWORD_MAP)}")
    print(f"   Vet med snippets      : {len(vet_med_snippets)}")
    print(f"   VetCare Pro entries   : {len(vetcare_entries)}")


def load_vetcare_pro_csv():
    """Load VetCare Pro chatbot dataset for direct Q&A matching."""
    VETCARE_CSV = os.path.join(BASE_DIR, "raw", "vetcare_pro_chatbot.csv")
    entries = []

    if not os.path.exists(VETCARE_CSV):
        print(f"[WARN] VetCare Pro CSV not found: {VETCARE_CSV}")
        return entries

    with open(VETCARE_CSV, encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            user_input = row.get("user_input", "").strip()
            vet_response = row.get("vet_response", "").strip()
            if not user_input or not vet_response:
                continue

            entries.append({
                "input":      user_input.lower(),
                "response":   vet_response,
                "animal":     row.get("animal_type", "").strip().lower(),
                "category":   row.get("category", "").strip().lower(),
                "severity":   row.get("severity", "").strip().lower(),
                "diagnosis":  row.get("possible_diagnosis", "").strip(),
                "treatment":  row.get("recommended_treatment", "").strip(),
            })

    print(f"[OK] Loaded {len(entries)} entries from VetCare Pro chatbot dataset")
    return entries


if __name__ == "__main__":
    print("=" * 60)
    print("  VetSync ASTRID - Knowledge Base Builder")
    print("=" * 60)
    build_knowledge_base()

