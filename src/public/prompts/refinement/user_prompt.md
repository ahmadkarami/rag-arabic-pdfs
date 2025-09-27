User just asked:

{question}

Conversation history:

{history}

Chat summary:

{chatSummary}

---

Now:
- Update the `chatSummary` object only if new, important information has appeared in this turn.
- Rewrite the question clearly by resolving vague pronouns using the history and summary.
- Return the final JSON with the fields: "chatSummary" and "refinedQuery".
- Only return valid JSON. No extra text.