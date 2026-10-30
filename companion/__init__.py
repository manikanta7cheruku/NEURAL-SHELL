"""
companion: Seven as a friend, not only an app.

Seven reaches out the way a new friend does: it asks about you, tells you things about itself and its future, shares a
small fact, checks in when you seem down, and follows up on what you told it. Everything lands in one place, Seven's own
chat thread, and is said aloud only when you are idle.

    settings.py    what the person chose (pace, quiet hours, voice, topics) and the maths that follows from it
    store.py       what was sent, asked and answered, so Seven never repeats itself or nags
    content.py     what Seven can bring up (about you, about Seven, a fact, care) written as a person would say it
    engine.py      choosing one thing to say, posting it to the thread, learning from the answer, asking back
    scheduler.py   when: not in quiet hours, not while you are busy, at a human pace, spoken only when you are idle

Nothing here runs a model: every line is written by a person, chosen by rules a person can read, and the answers go
into the same memory as everything else Seven learns. The chat thread itself is a normal conversation, so anything the
person asks in it is answered by the normal brain.
"""
