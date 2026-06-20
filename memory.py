class MemoryView:
    def __init__(self, db, persona_key, session_id):
        self.db = db
        self.persona_key = persona_key
        self.session_id = session_id

    @property
    def short_term_memory(self):
        return self.db.recent_messages(self.persona_key, self.session_id, limit=12)

    @property
    def long_term_memory(self):
        return self.db.facts(self.persona_key, limit=50)

    @property
    def skill_memory(self):
        return self.db.qa_pairs(self.persona_key)
