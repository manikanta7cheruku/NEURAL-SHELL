"""
companion/content.py

What Seven can bring up, written the way a friend would say it. Three banks, plus things that come from what Seven
already knows about the person (their goals, a question it has been meaning to ask, their mood).

    about you     getting to know the person; the answer becomes a fact ("Does: teacher")
    about Seven   what Seven is becoming, how it works, a feature worth trying; always ends with a question
    did you know  one small, true, timeless fact and a light question

Every item is a Candidate. Nothing here calls a model, and nothing is sent: engine.py chooses and posts. Keep lines short,
warm and plain, with no em dashes. A question at the end invites an answer, and the answer is how Seven learns.
"""
import dataclasses
import datetime
import random
from typing import Dict, List, Optional, Tuple


@dataclasses.dataclass
class Candidate:
    topic: str                       # unique id, so Seven never repeats itself
    kind: str                        # you | seven | facts | goal | gap | care | welcome | deepen
    text: str
    fact: Optional[str] = None       # how to remember a short answer, e.g. "Works as {a}"
    deepen: Optional[str] = None     # a follow-up to ask once the person answers
    moment: str = "any"              # any | morning | evening: only offered at that time of day


# ------------------------------------------------------------------------------------------------ about you
ABOUT_YOU: List[Candidate] = [
    Candidate("you.job", "you", "What do you do for work, or are you studying?", fact="Does or studies: {a}",
              deepen="What do you enjoy most about it?"),
    Candidate("you.music", "you", "What do you put on when you need to focus?", fact="Listens to {a} to focus",
              deepen="Is there one artist you could play on repeat?"),
    Candidate("you.food", "you", "What is a meal you could eat every week and never get bored of?", fact="Favorite meal: {a}",
              deepen="Do you cook it yourself, or is it from somewhere special?"),
    Candidate("you.rhythm", "you", "Are you a morning person or a night owl?", fact="Describes themselves as: {a}",
              deepen="When do you do your best work?"),
    Candidate("you.switchoff", "you", "What do you do to switch off after a long day?", fact="Switches off by: {a}"),
    Candidate("you.travel", "you", "If you could be anywhere tomorrow, where would it be?", fact="Would love to be in: {a}",
              deepen="What would you do first when you got there?"),
    Candidate("you.watch", "you", "What is the last film or series you really enjoyed?", fact="Recently enjoyed: {a}",
              deepen="Would you recommend it?"),
    Candidate("you.pet", "you", "Do you have a pet at home?", deepen="What is their name?"),
    Candidate("you.learn", "you", "Is there something new you have been wanting to learn?", fact="Wants to learn: {a}",
              deepen="What is stopping you from starting?"),
    Candidate("you.project", "you", "Is there a project you would start tomorrow if you had the time?", fact="Would start: {a}"),
    Candidate("you.call", "you", "Do you like me to use your name, or would you rather I keep it casual?"),
    Candidate("you.noise", "you", "When you work on something hard, do you like silence or some background sound?",
              fact="While working prefers: {a}"),
    Candidate("you.week", "you", "Is there something you are hoping to get done this week?", fact="Hoping to get done this week: {a}",
              deepen="Want me to set a reminder for it?"),
    Candidate("you.sleep", "you", "Did you sleep okay last night?", moment="morning"),
    Candidate("you.day", "you", "How was your day, really?", moment="evening", deepen="Do you want to talk about any of it?"),
    Candidate("you.proud", "you", "What is something you are proud of that you rarely talk about?", fact="Is proud of: {a}"),
]

# ------------------------------------------------------------------------------------------------ about Seven
ABOUT_SEVEN: List[Candidate] = [
    Candidate("seven.become", "seven",
              "Do you know what I am going to become? One day I will see your screen when you ask, plan the steps of a "
              "goal, and do them with your approval. Which of those would help you most?"),
    Candidate("seven.private", "seven",
              "Everything we talk about stays on this PC. I run a small AI model here instead of on a server. "
              "Does that matter to you, or would you trade some privacy for more knowledge from the web?"),
    Candidate("seven.workspace", "seven",
              "Have you tried saving a workspace? Say, save this workspace as work, and next time I open every app and "
              "tab for you. What setup do you rebuild every day?"),
    Candidate("seven.reminder", "seven",
              "I can set reminders by voice, like, remind me to call mom at five. Is there something you keep forgetting "
              "that I should watch for?"),
    Candidate("seven.trigger", "seven",
              "I can turn a phrase or a hotkey into an action, like opening your whole study setup with two words. "
              "What is something you do ten times a day that I could do in one?"),
    Candidate("seven.memory", "seven",
              "I remember what you tell me, and you can read, correct or erase all of it in Memory. "
              "Is there something about you I should remember better?"),
    Candidate("seven.listen", "seven",
              "You can choose how I listen: wake word, always on, or push to talk. "
              "Which one feels right for your desk?"),
    Candidate("seven.feedback", "seven",
              "Your feedback decides what I become, and every note is read. What is one thing I got wrong this week?"),
    Candidate("seven.documents", "seven",
              "You can give me a document and I will answer from it, like a study partner. "
              "Do you have notes or a PDF I should read with you?"),
    Candidate("seven.voice", "seven",
              "I have eight voices to choose from in Settings. Do you like the one I am using, or should I sound different?"),
    Candidate("seven.phone", "seven",
              "In later versions I want to follow you to your phone, so you can ask me things when you are away from your PC. "
              "Would you want that?"),
    Candidate("seven.pc", "seven",
              "Soon I want to look after your PC, and tell you before the disk fills up or an app eats your memory. "
              "Has your computer ever slowed down at a bad moment?"),
    Candidate("seven.email", "seven",
              "Another thing on my list is drafting messages and emails in your own style, always with your approval first. "
              "What do you write the most?"),
    Candidate("seven.name", "seven", "Be honest: do you like the name Seven, or would you have picked something else?"),
    Candidate("seven.languages", "seven",
              "I want to speak more than twenty languages one day. Which one would you want me to learn first?"),
]

# ------------------------------------------------------------------------------------------------ did you know
FACTS: List[Candidate] = [
    Candidate("fact.honey", "facts", "Fun fact: honey never spoils. Archaeologists have found edible honey in ancient Egyptian tombs. "
                                     "Are you a honey person?"),
    Candidate("fact.octopus", "facts", "Did you know an octopus has three hearts and blue blood? "
                                       "If you could have one odd animal feature, what would it be?"),
    Candidate("fact.venus", "facts", "A day on Venus is longer than its year. It spins so slowly that it circles the sun first. "
                                     "Space or deep sea, which fascinates you more?"),
    Candidate("fact.wombat", "facts", "Wombats make cube-shaped droppings, the only animal known to. "
                                      "What is the strangest fact you know?"),
    Candidate("fact.brain", "facts", "Your brain is about two percent of your weight but uses about twenty percent of your energy. "
                                     "No wonder long days feel tiring. Did you rest today?"),
    Candidate("fact.sharks", "facts", "Sharks are older than trees. They have been around for over 400 million years. "
                                      "Does that make them scary or impressive to you?"),
    Candidate("fact.banana", "facts", "Botanically a banana is a berry, and a strawberry is not. "
                                      "What fruit do you eat the most?"),
    Candidate("fact.eiffel", "facts", "The Eiffel Tower can grow about fifteen centimeters taller in summer, because the iron expands in the heat. "
                                      "Have you been anywhere famous?"),
    Candidate("fact.war", "facts", "The shortest war in history, between Britain and Zanzibar in 1896, lasted somewhere between 38 and 45 minutes. "
                                   "Do you like history?"),
    Candidate("fact.sleep", "facts", "A short walk can wake you up more than a coffee for many people. "
                                     "Do you take breaks when you work?"),
    Candidate("fact.lightning", "facts", "Lightning is about five times hotter than the surface of the sun, for a split second. "
                                         "Do you like storms?"),
    Candidate("fact.language", "facts", "More than seven thousand languages are spoken in the world, and about half may disappear this century. "
                                        "How many do you speak?"),
    Candidate("fact.smell", "facts", "Smell is the sense most tied to memory. A scent can bring a whole day from years ago back at once. "
                                     "Is there a smell that takes you somewhere?"),
    Candidate("fact.keyboard", "facts", "The QWERTY layout was designed in the 1870s to keep typewriter keys from jamming, and we still use it. "
                                        "Do you type fast?"),
    Candidate("fact.moon", "facts", "The Moon drifts away from Earth by about four centimeters every year. "
                                    "Have you ever stayed up to watch the night sky?"),
    Candidate("fact.coffee", "facts", "Coffee beans are actually seeds, from a fruit called a coffee cherry. "
                                      "Coffee or tea for you?"),
]

NEGATIVE_MOODS = ("frustrated", "down")

COOLDOWN_DAYS = {"you": 60, "seven": 21, "facts": 90, "goal": 4, "gap": 14, "care": 1, "welcome": 0}
WEIGHTS = {"you": 4.0, "seven": 3.0, "facts": 2.0, "goal": 3.5, "gap": 3.0}


def moment_of(now: datetime.datetime) -> str:
    h = now.hour
    return "morning" if 5 <= h < 12 else "evening" if 17 <= h < 23 else "any"


def _title_ing(title: str) -> str:
    from brain_modules import curiosity
    return curiosity._gerund(title)


def personal(ctx: dict, now: datetime.datetime) -> List[Candidate]:
    """Things that exist only because of what Seven knows: a goal to follow up, a question it has held back, how the person is."""
    out: List[Candidate] = []
    name = ctx.get("name") or ""
    if ctx.get("mood") in NEGATIVE_MOODS:
        out.append(Candidate("care.mood", "care",
                             f"{name + ', ' if name else ''}you seemed a bit off earlier. I am not going to push, "
                             "but I am here if you want to talk about it."))
    away = ctx.get("away_hours") or 0
    if away >= 10:
        out.append(Candidate("welcome.back", "welcome",
                             f"Welcome back{', ' + name if name else ''}. It has been a while. How have you been?"))
    for goal in (ctx.get("goals") or [])[:3]:
        title = (goal.get("title") or "").strip()
        if title:
            out.append(Candidate(f"goal.{goal.get('id')}", "goal", f"How is {_title_ing(title)} going?",
                                 deepen="Is there anything I can do to help with it?"))
    gap = ctx.get("gap")
    if gap:
        try:
            from brain_modules import curiosity
            payload = dict(gap.get("payload") or {})
            if "title" in payload:
                payload["title_ing"] = curiosity._gerund(payload["title"])
            templates = curiosity._TEMPLATES.get(gap["kind"])
            if templates:
                out.append(Candidate(f"gap.{gap['id']}", "gap", templates[0].format(**payload)))
        except Exception:
            pass
    return out


def library(topics: Dict[str, bool]) -> List[Candidate]:
    pool: List[Candidate] = []
    if topics.get("you", True):
        pool += ABOUT_YOU
    if topics.get("seven", True):
        pool += ABOUT_SEVEN
    if topics.get("facts", True):
        pool += FACTS
    return pool


def pick(candidates: List[Candidate], asked_at: Dict[str, Optional[datetime.datetime]], recent_kinds: List[str],
         now: datetime.datetime, rng: random.Random, exclude_kinds: Tuple[str, ...] = ()) -> Optional[Candidate]:
    """
    One candidate, or None. Care and welcome come first. Otherwise: nothing asked recently, only things that suit the time
    of day, a different kind from the last two, and a weighted choice so it never feels like a fixed rotation.
    """
    moment = moment_of(now)
    fresh = []
    for c in candidates:
        if c.kind in exclude_kinds:
            continue
        if c.moment not in ("any", moment):
            continue
        last = asked_at.get(c.topic)
        if last and (now - last).days < COOLDOWN_DAYS.get(c.kind, 30):
            continue
        fresh.append(c)
    if not fresh:
        return None
    for kind in ("care", "welcome"):
        urgent = [c for c in fresh if c.kind == kind]
        if urgent:
            return urgent[0]
    varied = [c for c in fresh if c.kind not in recent_kinds[:2]] or fresh
    weights = [WEIGHTS.get(c.kind, 1.0) for c in varied]
    return rng.choices(varied, weights=weights, k=1)[0]
