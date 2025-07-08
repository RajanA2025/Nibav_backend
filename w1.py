# w1.py
import pandas as pd

def load_faq(csv_path):
    df = pd.read_csv(csv_path)
    questions = df["Question"].fillna("").tolist()
    concise_answers = df["Concise Answer (bot default)"].fillna("").tolist()
    detailed_answers = df['Details if user asks "Tell me more"'].fillna("").tolist()
    return questions, concise_answers, detailed_answers
