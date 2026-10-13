"""Writes data/tickets.json: 100 made-up support tickets about Claude.

Every ticket is fictional. Names, emails and order numbers are invented.
Each one gets a channel and an arrival time over one week so the inbox
simulator can replay them in order.
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path

random.seed(7)

# (channel, plan, name, subject, body)
RAW = [
    # --- plan changes going down ---
    ("email", "Max 20x", "Priya N.", "Downgrade to Max 5x?", "I'm on Max 20x and honestly I'm using maybe a quarter of it. How do I move down to the $100 tier? I don't see a downgrade button anywhere in Settings > Billing, only Cancel."),
    ("web_form", "Max 5x", "Tom Becker", "switch back to pro", "Hi, I upgraded to Max last month for a project that's done now. I want to go back to Pro. If I cancel do I lose everything and have to sign up again? I don't want to lose my projects."),
    ("in_app", "Max 20x", "Lena Ortiz", "When does a downgrade kick in", "If I go from 20x to 5x today, does it take effect now or at my renewal on the 28th? And do I get any money back for the difference?"),
    ("email", "Pro (annual)", "Daniel Kim", "Annual to monthly", "I bought Pro annual by mistake, wanted monthly. I found the article for monthly to annual but not the other way around. Can I switch to monthly at renewal?"),
    ("web_form", "Max 5x", "Chiara Russo", "Lower my plan", "Money's tight this month. I'd like to drop from Max to Pro for a while and come back later. What's the process and will my usage limits drop right away?"),
    ("email", "Max 20x", "Marcus Hill", "Downgrade + monthly API credits", "Planning to go from Max 20x to Max 5x. What happens to the $200 in monthly API credits I claimed? Do they get cut to $100 immediately or next cycle?"),
    ("in_app", "Max 5x", "Sofia Petrov", "can't find how to downgrade", "Settings only lets me upgrade or cancel. Is downgrading even possible or do I need to cancel and wait for the period to end?"),
    ("email", "Max 20x", "James O'Connor", "Prorated credit on downgrade?", "When I upgraded you prorated me. If I downgrade mid-cycle, is that prorated too or do I just keep 20x until renewal?"),
    ("web_form", "Max 5x", "Aiko Tanaka", "Downgrading on iPhone", "I subscribed on the iOS app. How do I move from Max to Pro there? Is it Apple's subscription screen or yours?"),
    ("email", "Max 20x", "Nadia Hassan", "Will downgrading delete Claude Code history", "I want to drop to Pro. Will I lose my Claude Code sessions or Cowork tasks? I use them a lot but not at the 20x level anymore."),
    ("in_app", "Max 5x", "Ben Carter", "pro vs max downgrade", "Is there a fee to downgrade? And if I downgrade and then need Max again next month, do I pay the full upgrade price?"),
    ("email", "Pro (annual)", "Grace Liu", "Annual Pro, want to go monthly and maybe cancel", "Annual renewal is in two weeks. I want monthly billing going forward instead of another year. What do I click so I don't get charged $200+ again?"),
    ("web_form", "Max 20x", "Oliver Smith", "Downgrade request", "Please downgrade my account from Max 20x to Max 5x effective at my next billing date. Thanks."),

    # --- usage limits ---
    ("in_app", "Pro", "Hannah Wright", "Limit hit after 10 messages??", "I hit my usage limit after what felt like ten messages. I'm on Pro. Is something wrong with my account?"),
    ("email", "Max 5x", "Ravi Patel", "Weekly limit vs 5-hour limit", "I keep seeing a weekly limit warning even though my 5-hour window reset. How do these two limits work together?"),
    ("web_form", "Pro", "Emily Davis", "When does my limit reset", "Says I'm out until 3pm. Is that my local time? And does the reset happen at the same time every day?"),
    ("in_app", "Pro", "Lucas Moreau", "Usage burns fast with files", "When I attach PDFs my usage drains much faster. Is that expected? Any tips to stretch it?"),
    ("email", "Max 20x", "Fatima Zahra", "Claude Code eating my chat limits", "I use Claude Code during the day and then can't chat at night. Do they share the same limit?"),
    ("web_form", "Pro", "Kevin Nguyen", "Out of usage, can I pay for more", "I'm out of usage in the middle of a deadline. Is there a way to pay for extra usage without upgrading to Max?"),
    ("in_app", "Free", "Isabel Gomez", "Free limit", "How many messages do I get on free? It cut me off pretty quickly today."),
    ("email", "Pro", "Noah Fischer", "Long chats use more?", "Someone told me long conversations use up limits faster. True? Should I start new chats more often?"),
    ("in_app", "Pro", "Grace Obi", "Does model choice affect limits", "Do I burn through my limit faster on Opus than on Sonnet? Should I switch models to make it last?"),
    ("web_form", "Max 5x", "Mei Chen", "What's a limit reset", "I got a notification about a 'limit reset' I can use. What is that and how do I use it?"),

    # --- refunds ---
    ("email", "Pro", "Alex Turner", "Refund please", "I was charged for renewal yesterday but meant to cancel. Can I get a refund? I haven't used it since."),
    ("web_form", "Max 5x", "Julia Novak", "Refund for iOS purchase", "Bought Max on my iPhone by accident, meant to get Pro. Can you refund it?"),
    ("email", "Pro", "Samuel Adeyemi", "EU refund within 14 days", "I'm in Germany and subscribed 5 days ago. I understand I can get a refund within 14 days. How?"),
    ("in_app", "Max 20x", "Chloe Martin", "Refund after upgrading to Team", "Our company moved us to a Team plan. Do I get a refund for the rest of my Max month or do I need to ask?"),
    ("email", "Pro", "Victor Hugo Lima", "Refund, I disputed the charge", "I opened a dispute with my bank but now I'd rather just get a refund from you. What do I do?"),
    ("web_form", "Pro", "Laura Schmidt", "Charged on Android", "I was charged through Google Play and want a refund. I deleted the app already."),
    ("email", "Max 5x", "Ahmed Karim", "Can't log in to request refund", "I lost access to the email I signed up with but I'm still being charged. How do I get a refund?"),

    # --- login emails ---
    ("in_app", "Free", "Zoe Clark", "No login email", "I keep requesting the login link and nothing arrives. Checked spam."),
    ("email", "Pro", "Pedro Alves", "Magic link goes nowhere", "I click the login link on my phone and it shows a code instead of logging me in. What do I do with the code?"),
    ("web_form", "Team", "Rachel Green", "Work email not getting login link", "Our company email never receives the Claude login link. Personal Gmail works fine."),
    ("email", "Pro", "Dmitri Volkov", "Set a password?", "I'd rather have a password than the email link every time. Where do I set one?"),
    ("in_app", "Pro", "Sara Lindqvist", "Google login broken", "Continue with Google just loops back to the login page. Tried two browsers."),
    ("web_form", "Free", "Yusuf Demir", "Hide My Email account", "I signed up with Apple's hide my email and now I can't log in on my laptop."),
    ("email", "Max 5x", "Anna Kowalski", "Login link expired", "Every time I get the email the link says it's expired. Is there a time limit?"),

    # --- Claude Code billing to API ---
    ("email", "Max 20x", "Chris Walker", "Claude Code charging my API account", "I have Max but Claude Code keeps telling me my credit balance is too low and wants API credits. Why isn't it using my subscription?"),
    ("web_form", "Pro", "Elena Popescu", "Claude Code says invalid API key", "I logged in with my Pro account but Claude Code says Invalid API key. I did set an API key months ago for something else."),
    ("in_app", "Max 5x", "Jordan Lee", "Unexpected Console charges", "I got a Console bill for Claude Code usage but I thought Max covered Claude Code. Did I set something up wrong?"),
    ("email", "Max 20x", "Hiroshi Sato", "Switch Claude Code from API to subscription", "How do I make Claude Code use my Max plan instead of the API key in my environment?"),
    ("web_form", "Pro", "Amelia Brooks", "Claude Code login confusion", "When I run /login it asks Claude account or Console account. Which one uses my Pro plan?"),
    ("email", "Max 5x", "Mateo Fernandez", "ANTHROPIC_API_KEY overriding", "I think my ANTHROPIC_API_KEY env var is overriding my subscription login in Claude Code. How do I check which one it's using?"),
    ("in_app", "Max 20x", "Olivia Brown", "Claude Code usage not on Max", "My /status shows API usage billing. I want Max. Help."),

    # --- missing / deleted chats ---
    ("email", "Pro", "William Taylor", "All my chats are gone", "I logged in this morning and my sidebar is empty. Months of conversations. Where did they go?"),
    ("in_app", "Pro", "Ines Duarte", "Accidentally deleted a chat", "I deleted a conversation by mistake. It had a lot of work in it. Can you restore it?"),
    ("web_form", "Team", "Paul Robinson", "Chats missing after joining Team", "After my company added me to the Team plan I can't see my old chats. Are they deleted?"),
    ("email", "Max 5x", "Keiko Yamamoto", "Recover deleted project", "I deleted a project and all its chats yesterday. Is there a trash or undo?"),
    ("in_app", "Free", "Liam Murphy", "conversation disappeared mid-session", "I was in a long chat, refreshed the page, and the whole conversation is gone from history."),
    ("email", "Pro", "Maria Gonzalez", "Chats missing on mobile", "My chats show on the website but the iPhone app shows none. Same email."),
    ("web_form", "Pro", "Ethan Cooper", "Can support recover deleted chats", "You keep data for 30 days after deletion per your article. So can you bring back a chat I deleted 2 days ago?"),
    ("in_app", "Max 20x", "Aisha Bello", "History search not finding old chat", "I know I had a chat about my thesis outline but it's not in my list anymore. Did it get archived somewhere?"),

    # --- account security / 2FA ---
    ("email", "Pro", "George Adams", "Two-factor authentication", "Does Claude support 2FA? I can't find a setting for it and I store work material here."),
    ("web_form", "Max 5x", "Sophie Laurent", "Unknown sessions on my account", "I see a session from a city I've never been to. How do I kick it out?"),
    ("email", "Pro", "Henry Wilson", "Account hacked?", "There are chats in my history I didn't write. I think someone got into my email. What should I do on the Claude side?"),
    ("in_app", "Max 20x", "Lily Zhang", "Authenticator app", "Can I add an authenticator app or passkey to my Claude account?"),
    ("email", "Team", "Robert King", "MFA for our Team plan", "Our security policy requires MFA. Can we enforce MFA for everyone on our Team plan without buying Enterprise SSO?"),
    ("web_form", "Pro", "Eva Novotna", "Log out everywhere", "I logged in on a library computer and forgot to log out. How do I sign out of all devices?"),

    # --- phone verification ---
    ("in_app", "Free", "Mohammed Ali", "Phone number used too many times", "It says my number has already been used. I only have one account."),
    ("web_form", "Free", "Jasmine Reed", "No SMS code", "Never get the verification code text. Waited 20 minutes."),
    ("email", "Free", "Arjun Mehta", "Google Voice number rejected", "My only number is Google Voice and it's rejected. Any workaround?"),
    ("in_app", "Free", "Clara Hoffmann", "Change phone number", "I'm changing carriers and getting a new number. How do I update the phone on my account?"),
    ("web_form", "Free", "Tyler Jackson", "Code doesn't work", "I get the code but it says invalid."),
    ("email", "Free", "Nora Berg", "Skip phone verification", "I don't have a mobile phone. Can I verify another way?"),

    # --- API rate limits ---
    ("email", "API", "DevOps @ Brightloop", "Constant 429s", "We're getting 429 rate_limit_error on about 10% of requests at peak. How do we get a higher tier?"),
    ("web_form", "API", "Kai Andersen", "What tier am I on", "How do I see my current rate limit tier and what it takes to move up?"),
    ("email", "API", "Platform team @ Quillstack", "Rate limit headers", "Which response headers tell us how many tokens we have left in the current window?"),
    ("web_form", "API", "Rosa Jimenez", "Higher limits for launch", "We're launching next month and expect 10x traffic. Who do we talk to for custom limits?"),
    ("email", "API", "Ian Fletcher", "Batch API and rate limits", "Do Message Batches count against our normal rate limits?"),

    # --- API overloaded ---
    ("email", "API", "Backend @ Lumenstack", "529 overloaded errors", "We get 529 overloaded_error a few times an hour. Is this on our side? Should we retry?"),
    ("web_form", "API", "Felix Wagner", "overloaded vs rate limited", "What's the difference between a 429 and a 529 and should our retry logic treat them differently?"),
    ("email", "API", "Ops @ Northwind Apps", "Status page", "Is there a status page we can subscribe to for API incidents?"),
    ("web_form", "API", "Mila Ivanova", "Timeouts on long requests", "Long requests time out after 10 minutes with the Python SDK. Should we stream?"),

    # --- Primary Owner gone ---
    ("email", "Team", "Office Manager @ Delta Design", "Our admin left the company", "The person who set up our Team plan left and we can't reach her. Nobody else can see billing. How do we take over the account?"),
    ("web_form", "Team", "Carlos Mendes", "Primary Owner unreachable", "Our Primary Owner's email was deactivated when he left. We need to change the card before renewal. What proof do you need from us?"),
    ("email", "Team", "IT @ Hollis & Grant", "Transfer ownership without old owner", "Your article says the current Primary Owner has to transfer ownership. Ours passed away last month. What's the process?"),
    ("web_form", "Team", "Megan Price", "Locked out of billing", "I'm an Admin but not Owner. Owner is gone. Can you promote me?"),
    ("email", "Team", "Finance @ Arcadia Labs", "Former employee is Primary Owner", "A former employee is still listed as Primary Owner and invoices go to their inbox. How do we fix this?"),

    # --- vendor paperwork ---
    ("email", "Team", "Accounts Payable @ Pinecrest", "W-9 request", "To add Anthropic as a vendor we need a signed W-9. Where can we download it?"),
    ("web_form", "Team", "Procurement @ Velo Health", "Security questionnaire", "We need your SOC 2 report and to complete our vendor security questionnaire. Where do we get these?"),
    ("email", "API", "Finance @ Brightloop", "Vendor onboarding forms", "Our AP team needs a W-9 and bank details letter on letterhead before paying invoices. Who sends these?"),
    ("web_form", "Team", "Legal @ Orbit Media", "DPA", "Where can we view and sign your Data Processing Addendum?"),
    ("email", "Team", "AP @ Kestrel Co", "W-8BEN-E / tax residency", "We're outside the US and need Anthropic's tax residency certificate for withholding. Can you provide one?"),

    # --- App Store to web billing ---
    ("email", "Pro (iOS)", "Rebecca Stone", "Move billing from Apple to website", "I subscribed through the iPhone app but I need proper invoices for my employer. How do I move my subscription to web billing?"),
    ("in_app", "Max 5x (iOS)", "Diego Ramos", "iOS price higher than web", "I noticed the App Store price is higher. Can I switch my existing subscription to the web price without losing anything?"),
    ("web_form", "Pro (Android)", "Hana Kim", "Google Play to card", "I pay through Google Play and want to pay with my company card on the website instead. Steps?"),
    ("email", "Pro (iOS)", "Matt Fraser", "Apple subscription and invoice", "Can you send me an invoice with VAT for my Apple subscription?"),
    ("in_app", "Max 20x (iOS)", "Yara Haddad", "Switch from App Store", "If I cancel on Apple and resubscribe on the web, will there be a gap where I'm on free?"),

    # --- invoices ---
    ("email", "Pro", "Freelancer Joel Park", "Company name on invoice", "I need my company name on invoices instead of my personal name. How?"),
    ("web_form", "Team", "Accounts @ Tidewater", "Add VAT ID", "Where do we add our VAT number so it appears on invoices?"),
    ("email", "Pro", "Ruth Okafor", "Fix past invoice", "Last month's invoice has the wrong address. Can you reissue it?"),
    ("web_form", "Max 5x", "Stefan Braun", "Two receipts this month", "Why did I get two receipts in the same month?"),

    # --- Claude Code install ---
    ("email", "Pro", "Andre Silva", "claude: command not found", "Installed Claude Code on my Mac and the terminal says command not found."),
    ("web_form", "Max 5x", "Priyanka Rao", "Claude Code on Windows", "Install fails on Windows 11. Do I need WSL?"),
    ("in_app", "Max 5x", "Wen Li", "VS Code extension sign in", "The Claude Code extension in VS Code keeps asking me to sign in again every morning. Is there a way to stay logged in?"),
    ("in_app", "Pro", "Tobias Klein", "Update Claude Code", "How do I update Claude Code to the latest version? Mine seems old."),

    # --- API credits ---
    ("email", "API", "Startup @ Fernlabs", "Bought credits, still credit balance too low", "We bought $50 in credits 20 minutes ago and the API still returns 'Your credit balance is too low'. Does it take time to apply?"),
    ("web_form", "API", "Noor Siddiqui", "Credits not showing", "Paid for credits, card was charged, but Console shows $0 balance."),
    ("email", "API", "Dev @ Marlow", "Auto-reload", "How do I set up auto-reload so we never run out of credits in production?"),
    ("web_form", "API", "Owen Hughes", "Credit expiration", "Do purchased API credits expire? We bought a lot upfront."),
]

DOMAINS = ["gmail.com", "outlook.com", "icloud.com", "proton.me", "yahoo.com"]


def email_for(name: str) -> str:
    if "@" in name:
        team, org = name.split("@")
        return f"{team.strip().split()[0].lower()}@{org.strip().lower().replace(' ', '').replace('&', '')}.example"
    first = name.split()[0].lower().strip(".")
    return f"{first}.{random.randint(10, 99)}@{random.choice(DOMAINS)}"


def main():
    order = list(range(len(RAW)))
    random.shuffle(order)  # tickets arrive mixed together, like a real queue
    start = datetime(2026, 10, 5, 7, 0)
    t = start
    tickets = []
    for n, i in enumerate(order, 1):
        channel, plan, name, subject, body = RAW[i]
        t += timedelta(minutes=random.randint(15, 105))
        if t.hour >= 22:
            t = (t + timedelta(days=1)).replace(hour=7, minute=random.randint(0, 50))
        tickets.append({
            "id": f"TCK-{1000 + n}",
            "received_at": t.isoformat(timespec="minutes") + "Z",
            "channel": channel,
            "from_name": name,
            "from_email": email_for(name),
            "plan": plan,
            "subject": subject,
            "body": body,
            "status": "new",
        })
    out = Path(__file__).parent / "tickets.json"
    out.write_text(json.dumps(tickets, indent=2))
    print(f"wrote {len(tickets)} tickets to {out}")


if __name__ == "__main__":
    main()
