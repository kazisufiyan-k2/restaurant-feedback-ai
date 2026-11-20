"""
Reply generator + admin suggestion
==================================
Builds an English reply from the analysis (final label, star rating, aspects, dishes).
Many template variants are mixed, so different reviews get different replies.
Same review + same seed = same reply. New seed = new version (Regenerate button).
"""
import random
import zlib

# ---------------- greetings / sign-off ----------------
GREET_NAME = ["Hi {name},", "Dear {name},", "Hello {name},"]
GREET_ANON = ["Hi there,", "Hello,"]

# ---------------- short reviews ("good", "ok", "thanks") ----------------
SHORT = {
    "positive": ["Thank you so much! We're glad you liked it.",
                 "Thanks a lot! Happy you enjoyed it.",
                 "Thank you! It really means a lot to us.",
                 "Thanks for the love! Hope to see you again soon."],
    "neutral":  ["Thank you for your feedback! We'd love to hear what we could do better next time.",
                 "Thanks for sharing! Let us know how we can make your next order even better."],
    "negative": ["We're sorry to hear that. Please reply to this email and tell us what went wrong so we can fix it.",
                 "Sorry you weren't happy with your order. We'd really like to know more so we can make it right."],
}
SHORT_STAR = ["Thanks for the {r} stars!", "Thank you for the {r}-star rating!"]

# ---------------- openings ----------------
OPENINGS = {
    "positive": ["Thank you so much for your wonderful feedback!",
                 "Thanks a lot for taking the time to share this!",
                 "We really appreciate your kind words!",
                 "What a lovely review, thank you!",
                 "Thank you for choosing us and for the great feedback!"],
    "neutral":  ["Thank you for your feedback.",
                 "Thanks for sharing your experience with us.",
                 "We appreciate you taking the time to review us.",
                 "Thank you for your honest feedback."],
    "negative": ["We're really sorry to hear about your experience.",
                 "Thank you for letting us know, and we sincerely apologise.",
                 "We're sorry we let you down this time.",
                 "We apologise that your experience wasn't up to the mark."],
}
OPEN_STAR_POS = ["Thank you for the {r}-star rating and your kind words!",
                 "Thanks a lot for the {r} stars!",
                 "We're thrilled to get {r} stars from you, thank you!"]
OPEN_HIGH_STAR_COMPLAINT = ["Thank you for the {r}-star rating!",
                            "Thanks a lot for the {r} stars, we really appreciate it!",
                            "Thank you for rating us {r} stars!"]
BRIDGE_COMPLAINT = ["That said, we noticed a few things didn't go right, and we want to fix them.",
                    "We also want to address the points you raised.",
                    "We'd still like to make a couple of things right."]
LOW_STAR_NOTE = ["We noticed your rating was a bit lower than we'd hope. Please let us know what we could do better.",
                 "Your rating tells us something wasn't quite right. We'd love to hear what we can improve.",
                 "If anything stopped this from being a 5-star experience, please tell us so we can fix it."]

# ---------------- aspect lines ----------------
POS_ASPECT = {
    "taste":     ["We're delighted you enjoyed the food.", "Our kitchen team will be thrilled you loved the taste.",
                  "So happy the food hit the spot!", "It's great to hear you enjoyed every bite."],
    "delivery":  ["Glad your order reached you quickly.", "Happy to hear the delivery was smooth.",
                  "Great to know your order arrived on time."],
    "packaging": ["We're glad the packaging kept everything fresh and intact.",
                  "Happy to hear your order arrived well packed."],
    "quantity":  ["Happy to hear the portions were satisfying.", "Glad the portion size left you full and happy."],
    "price":     ["We're glad you found it great value for money.", "Happy to hear you felt it was worth it."],
    "service":   ["We'll pass your kind words on to our staff.",
                  "Our team will be happy to hear they made your visit special."],
    "ambience":  ["So glad you enjoyed the ambience.", "Happy you liked the vibe of the place."],
    "hygiene":   ["We take cleanliness very seriously, so this means a lot to us."],
}
POS_DISH = ["We're delighted you loved the {dish}!", "So glad the {dish} hit the spot!",
            "Our chefs will be thrilled to hear you enjoyed the {dish}.",
            "The {dish} is one of our favourites too, glad you liked it!"]

NEG_ASPECT = {
    "taste":     ["We're sorry the food didn't meet your expectations. We've shared this with our kitchen team.",
                  "Sorry the food wasn't up to the mark. Our chefs are looking into it.",
                  "We're sorry about the taste this time and have passed your feedback to the kitchen."],
    "delivery":  ["We apologise for the delay in delivery and are looking into it with our delivery partner.",
                  "Sorry your order took longer than expected. We're working on faster deliveries.",
                  "We're sorry about the late delivery. That's not the experience we want for you."],
    "packaging": ["Sorry about the packaging issue. We're reviewing how we pack our orders.",
                  "We apologise for the packaging problem and are working on sturdier packing."],
    "quantity":  ["We hear you on the portion size and will review it with our team.",
                  "Thanks for flagging the quantity. We're reviewing our portion sizes."],
    "price":     ["Thank you for your honest feedback on pricing. We'll take it into account.",
                  "We understand your concern about the price and will keep it in mind."],
    "service":   ["We're sorry about the service you received. That's not our standard, and we'll address it with our team.",
                  "We apologise for the service experience and are speaking with our staff about it."],
    "ambience":  ["Sorry the ambience didn't match your expectations. We'll work on it.",
                  "Thanks for the feedback on our space. We're looking at ways to improve it."],
    "hygiene":   ["We're extremely sorry. Hygiene is our top priority, and we're investigating this immediately.",
                  "We're truly sorry. We take hygiene very seriously and have started checking this right away."],
}
NEG_DISH = ["We're sorry the {dish} didn't meet your expectations. Our kitchen team is looking into it.",
            "Sorry the {dish} wasn't up to the mark this time. We've shared your feedback with our chefs."]

GENERIC_MID = {
    "positive": ["It means a lot to our team.", "Feedback like this makes our day."],
    "neutral":  ["Your feedback helps us improve.", "We're always working to get better."],
    "negative": ["This isn't the experience we want for our customers.",
                 "We hold ourselves to a higher standard than this."],
}

# ---------------- closings ----------------
CLOSINGS = {
    "positive": ["We look forward to serving you again soon!", "Hope to see you again soon!",
                 "Can't wait to serve you again!", "See you next time!"],
    "mixed":    ["We hope to make your next order perfect!",
                 "We'll make sure your next experience is even better."],
    "neutral":  ["We'd love to know what we could do better to make your next order great.",
                 "We hope to give you an even better experience next time.",
                 "We hope to impress you on your next visit."],
    "negative": ["Please reply to this email so we can make it right.",
                 "We'd love the chance to make it up to you on your next order.",
                 "Please share your order details by replying here, and we'll sort it out."],
    "hygiene":  ["Please reply to this email with your order details. Our manager will personally get in touch with you."],
}


def _fmt_rating(r):
    return int(r) if float(r).is_integer() else r


def generate_draft_reply(a: dict, customer_name=None, business_name=None, seed=None, text: str = "") -> str:
    rng = random.Random(seed if seed is not None else zlib.crc32(str(text).encode("utf-8")))
    final, text_label, rating = a["final_label"], a["text_label"], a.get("rating")
    pos = [k for k, v in a["aspects"].items() if v == "positive"]
    neg = [k for k, v in a["aspects"].items() if v == "negative"]
    if "hygiene" in neg:
        neg = ["hygiene"] + [x for x in neg if x != "hygiene"]
    pos_dishes = a.get("dishes", {}).get("positive", [])
    neg_dishes = a.get("dishes", {}).get("negative", [])
    r = _fmt_rating(rating) if rating is not None else None

    greeting = rng.choice(GREET_NAME).format(name=customer_name.strip()) if customer_name else rng.choice(GREET_ANON)
    sign = f"Warm regards,\n{business_name.strip()} Team" if business_name else "Warm regards,\nOur Restaurant Team"

    high_star_complaint = rating is not None and rating >= 4 and (text_label == "negative" or bool(neg))
    low_star_praise = rating is not None and rating <= 2 and text_label == "positive"

    # ---- short reviews ----
    if a.get("is_short") and not neg and not high_star_complaint and not low_star_praise:
        line = rng.choice(SHORT[final])
        if r is not None and final == "positive":
            line = rng.choice(SHORT_STAR).format(r=r) + " " + line
        return f"{greeting}\n\n{line}\n\n{sign}"

    lines = []
    # ---- opening ----
    if high_star_complaint:
        lines.append(rng.choice(OPEN_HIGH_STAR_COMPLAINT).format(r=r))
    elif final == "positive" and r is not None and rating >= 4:
        lines.append(rng.choice(OPEN_STAR_POS).format(r=r))
    elif low_star_praise:
        lines.append(rng.choice(OPENINGS["positive"]))
    else:
        lines.append(rng.choice(OPENINGS[final]))

    # ---- positive aspects ----
    used_dish = False
    for asp in pos[:2]:
        if asp == "taste" and pos_dishes and not used_dish:
            lines.append(rng.choice(POS_DISH).format(dish=pos_dishes[0]))
            used_dish = True
        else:
            lines.append(rng.choice(POS_ASPECT[asp]))

    # ---- negative aspects ----
    if neg and (high_star_complaint or final == "positive"):
        lines.append(rng.choice(BRIDGE_COMPLAINT))
    used_neg_dish = False
    for asp in neg[:3]:
        if asp == "taste" and neg_dishes and not used_neg_dish:
            lines.append(rng.choice(NEG_DISH).format(dish=neg_dishes[0]))
            used_neg_dish = True
        else:
            lines.append(rng.choice(NEG_ASPECT[asp]))

    if not pos and not neg:
        lines.append(rng.choice(GENERIC_MID[final]))

    # ---- rating note ----
    if low_star_praise:
        lines.append(rng.choice(LOW_STAR_NOTE))

    # ---- closing ----
    if "hygiene" in neg:
        key = "hygiene"
    elif low_star_praise:
        key = "neutral"
    elif neg and final != "negative":
        key = "mixed"
    else:
        key = final
    lines.append(rng.choice(CLOSINGS[key]))

    return f"{greeting}\n\n{' '.join(lines)}\n\n{sign}"


# ---------------- admin suggestion ----------------
ACTIONS = {
    "taste":     "Share with kitchen team, check recipe and freshness.",
    "delivery":  "Check delivery partner and dispatch time for this order.",
    "packaging": "Review packaging quality for this item.",
    "quantity":  "Review portion size vs price for this dish.",
    "price":     "Consider an offer or combo for this customer.",
    "service":   "Speak to the staff on duty. Consider service training.",
    "ambience":  "Check seating, music and cleanliness of the dining area.",
    "hygiene":   "URGENT: Inspect kitchen hygiene today. Contact the customer personally.",
}
RESPONSE_HOURS = {"urgent": 2, "high": 24, "medium": 48, "low": 72}


def generate_admin_suggestion(a: dict) -> dict:
    final, text_label, rating = a["final_label"], a["text_label"], a.get("rating")
    neg = [k for k, v in a["aspects"].items() if v == "negative"]
    emotions = a.get("emotions", [])
    reasons, actions = [], []

    is_negative = final == "negative" or text_label == "negative"
    angry = "anger" in emotions or "disgust" in emotions
    very_bad = (rating is not None and rating <= 1) or len(neg) >= 3
    if "hygiene" in neg or (is_negative and angry and very_bad):
        priority = "urgent"
        actions.append("Respond within 2 hours. Offer a refund or coupon.")
    elif is_negative:
        priority = "high"
        actions.append("Respond within 24 hours. Consider a discount coupon.")
    elif final == "neutral" or neg or a.get("rating_mismatch"):
        priority = "medium"
        actions.append("Thank the customer and ask what would make it a 5-star experience.")
    else:
        priority = "low"
        actions.append("Happy customer. Ask for a Google review or testimonial.")

    actions += [ACTIONS[x] for x in neg if x in ACTIONS]

    if a.get("rating_mismatch"):
        r = _fmt_rating(rating)
        if text_label == "negative":
            actions.append(f"Customer gave {r} stars but mentioned issues ({', '.join(neg) or 'see review'}). "
                           f"Fix these to keep this customer.")
            reasons.append("High rating but negative text")
        else:
            actions.append(f"Customer gave {r} stars but wrote positive words. Read the review and follow up.")
            reasons.append("Low rating but positive text")
    if a.get("conflict"):
        reasons.append("Model and VADER disagree")
    if a.get("confidence_level") == "low":
        reasons.append("Low model confidence")

    manual = bool(reasons)
    if manual:
        actions.append("Please read this review yourself before sending the reply.")

    return {"priority": priority, "respond_within_hours": RESPONSE_HOURS[priority],
            "actions": actions, "needs_manual_review": manual, "manual_review_reasons": reasons}
