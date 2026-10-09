"""Python port of the uploaded Java Naive Bayes emotion demo. Not an LLM."""
import math
import re
from collections import Counter

EXAMPLES = {
    'Happy': ['happy joyful excited delighted cheerful smile celebrate grateful', 'I am happy about my progress and feel proud', 'I had fun with friends today'],
    'Calm': ['calm peaceful relaxed settled comfortable content quiet', 'I feel calm and at ease', 'I enjoyed a quiet peaceful afternoon'],
    'Anxious': ['anxious worried nervous uneasy stressed overwhelmed panic', 'I worry about tomorrow and feel nervous', 'I feel anxious about my exam'],
    'Sad': ['sad unhappy down disappointed upset tearful grieving', 'I feel sad and want to cry', 'I am disappointed and feeling down'],
    'Angry': ['angry mad furious irritated frustrated annoyed resentful', 'I am angry about what happened', 'I feel frustrated and annoyed'],
    'Lonely': ['lonely isolated excluded disconnected alone left out', 'I feel lonely and left out', 'I miss having someone to talk to']}
# The uploaded frontend uses five spectrum categories; the backend model has six.
# This explicit mapping is only used after the user confirms the suggestion.
SPECTRUM = {'Happy': 'Great', 'Calm': 'Good', 'Anxious': 'Anxious', 'Sad': 'Low', 'Angry': 'Anxious', 'Lonely': 'Low'}

class LocalEmotionModel:
    def __init__(self):
        self.counts = {label: Counter(self.tokens(' '.join(samples))) for label, samples in EXAMPLES.items()}
        self.vocabulary = set().union(*(set(c) for c in self.counts.values()))
        self.totals = {label: sum(counts.values()) for label, counts in self.counts.items()}

    @staticmethod
    def tokens(text):
        return re.sub(r'[^a-z\s]', ' ', text.lower()).split()

    def predict(self, text):
        if len(text) > 4000: raise ValueError('Use up to 4000 characters.')
        known = [word for word in self.tokens(text) if word in self.vocabulary]
        if not known: return {'emotion': None, 'mood': None, 'relative_score': 0.0, 'known_tokens': 0}
        scores = {label: sum(math.log((counts.get(word, 0) + 1) / (self.totals[label] + len(self.vocabulary))) for word in known)
                  for label, counts in self.counts.items()}
        best = max(scores, key=scores.get)
        score = 1 / sum(math.exp(v - scores[best]) for v in scores.values())
        return {'emotion': best, 'mood': SPECTRUM[best], 'relative_score': score, 'known_tokens': len(known)}
