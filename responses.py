from random import choice, randint
from datetime import datetime


def get_response(user_input: str) -> str:
    lowered: str = user_input.lower()

    if not lowered.startswith("!"):
        return ""

    command = lowered[1:]

    if command == "":
        return "You didn't say anything!"
    elif command == "hello":
        return "Hello!"
    elif command == "goodbye":
        return "Goodbye!"
    elif command == "how are you":
        return "I'm fine, thanks for asking!"
    elif command == "what time is it":
        return "It's " + str(datetime.now().time()) + "!"
    elif command == "what day is it":
        return "It's " + str(datetime.now().date()) + "!"
    elif command == "what is your name":
        return "My name is NERDBOT!"
    elif command == "who are you":
        return "I'm a bot!"
    elif command == "roll":
        return f"You rolled a {randint(1, 6)}!"
    elif command == "commands":
        return "Available commands: hello, goodbye, how are you, what time is it, what day is it, what is your name, who are you, roll, joke, quote, play, im going to kill myself"
    elif command == "im going to kill myself":
        return "good choice!"
    elif command == "bad baak":
        return "bad baak is a really shit goal keeper who plays for the ALL BLACKZ"
    elif command == "joke":
        return choice(
            [
                "What do you call a group of Scavs with terrible aim? A 'Miss'-terious dance troupe in disguise!",
                "Why did the PMC cross the road? To chase after the ice cream truck... before being outsmarted by a stealthy squirrel sniper.",
                "What's the secret to thriving in Tarkov? Adopt a chicken as your mascot! (Especially if it lays golden eggs, then you're all set!)",
                "What do you call a player hooked on speed? A turbo-charged snail in a football jersey!",
                "Why did the goalkeeper dive the wrong way? He was mesmerized by a butterfly on the other side!",
                "What's the ultimate FIFA victory strategy? Play in clown shoes! (If you're losing by 5 goals, at least you'll win in style.)",
                "What do you call a Helldiver swamped by enemies? A cosmic bug zapper!",
                "Why did the Helldiver shoot his teammate? He mistook them for a space pizza delivery guy!",
                "How do you ensure survival in Helldivers 2? Start a dance party! (And make sure to lift your teammates' spirits!)",
                "What's a one-weapon Helldivers 2 player? A gourmet chef specializing in lead cuisine!",
                "What do you call a Battlebit player always caught by the same tank? An enthusiastic tank hugger!",
                "Why did the soldier toss a grenade at his feet? He was trying to pop popcorn for the squad!",
                "What's the Battlebit winning formula? Play hide-and-seek! (And don't forget to bring the snacks!)",
                "What do you call an early-game eliminee? A professional hide-and-seeker who's too good for this world!",
                "Why did the contestant trip on shoelaces? They were practicing their moonwalk!",
                "How do you clinch victory at The Finals? By unleashing the power of interpretative dance! (Don't forget your glitter cannon!)",
                "What do you call a repeatedly defeated demon? A celestial yo-yo!",
                "Why did the hero sell all their gear? They decided to start a new career in inter-dimensional real estate!",
                "What's the Diablo defeat strategy? Form a rock band! (And make sure your battle cry is in tune!)",
                "What do you call a soldier shot in the back? An unwilling participant in a surprise trust fall exercise!",
                "Why did the soldier reload a full gun? They were practicing for the intergalactic juggling championship!",
                "What's the Call of Duty winning strategy? Perfect your victory dance! (And remember, communication is key, especially when planning a group choreography!)",
            ]
        )
    elif command == "quote":
        return choice(
            [
                "The only way to do great work is to love what you do. - Steve Jobs",
                "Innovation distinguishes between a leader and a follower. - Steve Jobs",
                "The future belongs to those who believe in the beauty of their dreams. - Eleanor Roosevelt",
                "The only thing we have to fear is fear itself. - Franklin D. Roosevelt",
                "Success is not final, failure is not fatal: It is the courage to continue that counts. - Winston Churchill",
                "The greatest glory in living lies not in never falling, but in rising every time we fall. - Nelson Mandela",
                "The best way to predict the future is to create it. - Peter Drucker",
                "Believe you can and you're halfway there. - Theodore Roosevelt",
                "The only limit to our realization of tomorrow will be our doubts of today. - Franklin D. Roosevelt",
                "The future depends on what you do today. - Mahatma Gandhi",
            ]
        )
    elif command == "play":
        return "You should play - " + choice(
            [
                "diablonga: The Misadventures of a Demon with a Long Attention Span",
                "muff-divers 69: The Quest for the Perfect Muffin Recipe",
                "dees finals: The Ultimate Test of Mediocrity",
                "escape from scav: edging me off in the darkness: A Stealthy Escape from Awkward Situations",
                "Escape from Area: The Perilous Journey of an Introvert",
                "shartfilled: A Hilarious Adventure in Digestive Mishaps",
                "pocket batty: The Pocket-Sized Bat Hero",
                "fiFA20: The Chaotic World of Soccer with Fire-Breathing Players",
                "MylesWilson2-DanceMusicZone: The Epic Dance Battle of the Century",
                "Conor(is)Sick: The Unfortunate Tale of a Sickly Hero",
                "bowlcum: The Quirky Bowling Game with a Sticky Twist",
                "deesablo7: The Devilishly Funny Adventure of a Misunderstood Demon",
            ]
        )
    else:
        return (
            choice(
                [
                    "I don't understand!",
                    "I'm not sure what you mean!",
                    "I'm a bot, I don't understand!",
                    "I'm not programmed to understand that!",
                ]
            )
            + " Try !commands to see what commands are available!"
        )
