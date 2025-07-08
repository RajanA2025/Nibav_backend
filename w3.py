
# w2.py
from sentence_transformers import SentenceTransformer, util

# Load once
model = SentenceTransformer("all-MiniLM-L6-v2")

# Precompute embeddings globally
question_embeddings = None
raw_questions = []  # To keep lowercase copy

# Fallback keyword → full question mapping
keyword_fallback = {
    "noise": "is it noisy?",
    "warranty": "how long is the warranty?",
    "safety": "what safety features are included?",
    "installation": "how long does installation take?",
    "space": "how much space does it need?",
    "power": "what happens in a power cut?",
    "maintenance": "how often does it need maintenance?",
    "cost": "what does a nibav lift cost?",
    "custom": "can i customise the colour or finish?",
}


def compute_question_embeddings(questions):
    global question_embeddings, raw_questions
    question_embeddings = model.encode(questions, convert_to_tensor=True)
    raw_questions = [q.lower().strip() for q in questions]


def get_answer(user_query, questions, concise, detailed):
    global question_embeddings, raw_questions

    user_query = user_query.lower().strip()

    # Keyword fallback (before semantic search)
    for keyword, full_q in keyword_fallback.items():
        if keyword in user_query:
            try:
                idx = raw_questions.index(full_q)
                return concise[idx], detailed[idx]
            except ValueError:
                pass  # If fallback fails, continue to semantic

    # Semantic matching
    query_embedding = model.encode(user_query, convert_to_tensor=True)
    scores = util.cos_sim(query_embedding, question_embeddings)[0]
    best_idx = scores.argmax().item()
    best_score = scores[best_idx].item()

    if best_score > 0.35:
        return concise[best_idx], detailed[best_idx]
    else:
        return None, None
