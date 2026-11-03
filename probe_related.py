import json
import memory_vectors as mv

mv.embedder(force=True)
e = mv.embedder().encode


def s(a, b):
    return mv.cosine(e([a])[0], e([b])[0])


# Related but distinct: same subject, different predicate. This is the band where a false merge
# would silently drop one fact and leave the survivor describing an utterance it never recorded.
related = [
    ("My sister works at TCS.", "My sister lives in Pune."),
    ("I take sugar in my tea.", "I take two sugars in my tea."),
    ("My sister works at TCS.", "My brother works at TCS."),
    ("I live in Pune.", "I work in Pune."),
    ("I like filter coffee.", "I drink filter coffee."),
    ("My GPU is an RTX 3080.", "My GPU is an RTX 4090."),
    ("I run 5 km every morning.", "I run 10 km every morning."),
    ("My birthday is in June.", "My sister's birthday is in June."),
    ("I prefer short answers.", "I prefer short replies."),
    ("The app builds with a shared venv.", "The app builds with a local venv."),
    ("My laptop charger is 180W.", "My laptop charger is 200W."),
    ("I live in Pune with my dog Mochi.", "I live in Pune with my cat Mochi."),
    ("My name is Gaurav.", "My name is Gaurav Sharma."),
    ("I like filter coffee.", "I like black coffee."),
    ("I run 5 km every morning.", "I walk 5 km every morning."),
]
# Genuine near-duplicates, for reference
genuine = [
    ("My name is Gaurav.", "My name is now Gaurav."),
    ("I am living in Pune now with Mochi.", "I moved to Pune last month, Mochi came with me."),
    ("My sister works at TCS.", "My sister is employed at TCS."),
]
print("related-but-distinct (the danger band):")
for a, b in related:
    print("  %.4f  %-38s vs %-38s" % (s(a, b), a, b))
print("genuine near-duplicates (reference):")
for a, b in genuine:
    print("  %.4f  %-38s vs %-38s" % (s(a, b), a, b))
print("max related:", round(max(s(a, b) for a, b in related), 4))
print("min genuine:", round(min(s(a, b) for a, b in genuine), 4))
print("threshold:", mv.NEAR_DUPLICATE_THRESHOLD)