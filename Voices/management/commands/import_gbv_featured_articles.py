from django.core.management.base import BaseCommand
from django.utils import timezone

from Voices.models import Article


ARTICLES = [
    {
        "title": "What to Do If You or Someone You Know Is Experiencing GBV",
        "category": "education",
        "read_time": 5,
        "image": "articles/gbv-image-4.jpg",
        "content": """
<p class=\"intro\">Gender-based violence can happen to anyone, regardless of age, background, or relationship status. Knowing what steps to take in the moment can make a critical difference, for yourself or for someone you care about.</p>
<h2>1. Prioritize Your Safety First</h2>
<p>If you are in immediate danger, your safety comes before anything else. Move to a safe location if you can. Call the police on <strong>999 or 112</strong>, or seek help from a neighbor, a trusted person, or a nearby institution. Do not wait to be certain before asking for help.</p>
<h2>2. Support a Survivor With Care</h2>
<p>If you are supporting someone else, the most important thing you can do is listen without judgment. Believe them. Do not pressure them into decisions before they are ready, and avoid questions that place blame, such as \"What did you do to provoke it?\" Your role is to offer a safe presence, not to investigate.</p>
<h2>3. Document What Happened</h2>
<p>Where it is safe to do so, document the incident. This includes taking photos of injuries, keeping records of threatening messages, and writing down dates and descriptions of what occurred. This information can be crucial if legal action is pursued later.</p>
<h2>4. Seek Medical Attention Promptly</h2>
<p>Seek medical care as soon as possible, ideally within 72 hours of a sexual assault. Post-exposure prophylaxis (PEP) for HIV and emergency contraception are time-sensitive. Health facilities with Gender Violence Recovery Centres (GVRCs), including Nairobi Women's Hospital branches in Nakuru and Naivasha, offer confidential and free medical and psychosocial services to survivors.</p>
<h2>5. Report to the Authorities</h2>
<p>In Kenya, GBV can be reported at any police station, through the DCI, or at the Gender Desk of your local police station. Survivors can report directly and do not need a third party to act on their behalf.</p>
<div class=\"callout\"><p><strong>Important:</strong> You do not need to have all the evidence before you report. Reporting starts a process. Support organizations can walk alongside you every step of the way.</p></div>
<h2>6. Access Legal and Psychosocial Support</h2>
<p>Organizations such as FIDA Kenya provide free legal aid to survivors, while counselling centers across Nakuru County offer a safe space to process trauma and begin recovery. You do not have to face this alone.</p>
<div class=\"info-box\"><div class=\"info-title\">Remember</div><p>GBV is never the survivor's fault. Help is available throughout Nakuru County, and healing is possible. Reaching out is an act of courage, not weakness.</p></div>
""".strip(),
    },
    {
        "title": "The Different Forms of Gender-Based Violence: Beyond Physical Harm",
        "category": "awareness",
        "read_time": 6,
        "image": "articles/gbv-image-5.jpg",
        "content": """
<p class=\"intro\">When most people think of gender-based violence, they picture physical assault. While physical violence is one of the most visible forms, GBV takes many shapes, and some of the most damaging leave no visible marks at all.</p>
<h2>Physical Violence</h2>
<p>Physical violence includes hitting, slapping, kicking, burning, or any act that causes bodily harm. It is the form most readily recognized and reported, yet even it is significantly underreported due to fear and social pressure.</p>
<h2>Sexual Violence</h2>
<p>Sexual violence includes rape, sexual assault, defilement of minors, forced marriage, and any sexual act carried out without informed consent. In Kenya, the Sexual Offences Act (2006) criminalizes these acts. Yet many cases go unreported because of stigma and fear of not being believed.</p>
<h2>Emotional and Psychological Abuse</h2>
<p>Psychological abuse involves behaviors designed to control, humiliate, or manipulate. This includes constant criticism, threats, isolation from friends and family, gaslighting, and public humiliation. Because it leaves no physical evidence, it is frequently dismissed. Its effects on mental health, however, can be severe and long-lasting.</p>
<h2>Economic Abuse</h2>
<p>Economic abuse occurs when a perpetrator controls another person's access to money and resources. This can include preventing a partner from working, taking their income, running up debt in their name, or withholding money for basic needs. Economic abuse is a common tool used to trap survivors in abusive situations, making it difficult to leave even when they want to.</p>
<div class=\"callout\"><p><strong>Did you know?</strong> Economic abuse often begins subtly, with one partner gradually taking over all financial decisions. Over time, the other person loses access to money entirely and becomes dependent on the abuser.</p></div>
<h2>Digital and Online Abuse</h2>
<p>Digital abuse is a growing form of GBV in which technology is used to harass, stalk, threaten, or humiliate. This includes sharing intimate images without consent, cyberstalking, monitoring someone's devices without permission, and sending threatening messages online. It can occur alongside physical abuse or entirely on its own.</p>
<h2>Cultural and Structural Violence</h2>
<p>Some forms of GBV are rooted in tradition or social norms, including female genital mutilation (FGM), forced early marriage, and widow inheritance. Because these practices are often normalized within communities, they are among the hardest to challenge. Naming them as violence is an important first step.</p>
<div class=\"info-box\"><div class=\"info-title\">Key Takeaway</div><p>Recognizing all forms of gender-based violence is the first step toward addressing them. If you or someone you know is experiencing any of these, support is available across Nakuru County and beyond.</p></div>
""".strip(),
    },
    {
        "title": "Understanding Protection Orders: A Legal Tool for GBV Survivors in Kenya",
        "category": "education",
        "read_time": 5,
        "image": "articles/gbv-image-6.jpg",
        "content": """
<p class=\"intro\">If you are experiencing gender-based violence, the law provides you with a powerful tool to protect yourself: a Protection Order. Many survivors are unaware this option exists or believe it is difficult to access. Here is what you need to know.</p>
<h2>What Is a Protection Order?</h2>
<p>A Protection Order is a court directive that legally prohibits an abuser from contacting, approaching, or harming a survivor. It can also restrict the abuser from entering the survivor's home, workplace, or any other specified location. Violating a Protection Order is a criminal offence under Kenyan law.</p>
<h2>Who Can Apply?</h2>
<p>Any person who has experienced or is at risk of domestic violence can apply. This includes a spouse, child, parent, or any person in a domestic relationship, as defined under the <strong>Protection Against Domestic Violence Act (2015)</strong>.</p>
<h2>How Do You Apply?</h2>
<p>You can apply at the Chief Magistrate's Court nearest to you. In Nakuru County, this is the Nakuru Law Courts along Court Road. The application process is free, and you do not need a lawyer to apply, though having one can be helpful. Organizations such as <strong>FIDA Kenya</strong> can guide survivors through the process at no cost.</p>
<div class=\"section-divider\"></div>
<h2>What Happens After You Apply?</h2>
<p>The court can issue a temporary Protection Order on the same day the application is made, without the abuser needing to be present, if the situation is urgent. A full hearing is then scheduled where both parties present their case before a final order is made.</p>
<h2>What If the Order Is Violated?</h2>
<p>Report the violation to the nearest police station immediately. Violations of a Protection Order can result in a fine, imprisonment, or both. Keep a record of any violations, including screenshots of messages, call logs, and witness accounts where possible.</p>
<div class=\"warning-box\"><div class=\"warning-title\">Important Safety Note</div><p>A Protection Order is a legal tool, not a physical barrier. Always have a safety plan in place alongside any legal action. Talk to a counsellor or case worker about planning for your security.</p></div>
<h2>Where to Get Help</h2>
<ul><li><strong>FIDA Kenya</strong> offers free legal aid to GBV survivors and can assist with Protection Order applications.</li><li><strong>Nakuru Law Courts</strong> (Court Road) is where applications are filed for Nakuru County residents.</li><li><strong>Midrift Human Rights Network</strong> provides legal rights guidance and community support.</li><li><strong>Nakuru Child Protection Centre</strong> (Kalewa Road) handles cases involving children.</li></ul>
<div class=\"info-box\"><div class=\"info-title\">Remember</div><p>For many survivors, a Protection Order is an important step toward reclaiming safety and control over their lives. You have a legal right to protection. Use it.</p></div>
""".strip(),
    },
    {
        "title": "Breaking the Silence: Why GBV Goes Unreported and What We Can Do About It",
        "category": "awareness",
        "read_time": 6,
        "image": "articles/gbv-image-7.jpg",
        "content": """
<p class=\"intro\">Statistics on gender-based violence represent only a fraction of what actually occurs. The majority of cases in Kenya and worldwide are never reported. Understanding why survivors stay silent is essential to building communities and systems where speaking up feels safe and possible.</p>
<h2>Fear of Retaliation</h2>
<p>Fear of making things worse is one of the most common barriers to reporting. When an abuser is a partner, family member, or person in authority, the threat of escalation can feel paralyzing. Many survivors have experienced increased violence following previous attempts to seek help, making the prospect of reporting feel more dangerous than staying silent.</p>
<h2>Stigma and Shame</h2>
<p>Survivors, particularly those who have experienced sexual violence, are often blamed for what happened to them. In many communities, a woman who leaves an abusive marriage is viewed as a failure rather than as someone exercising courage. This cultural pressure keeps many people trapped, not because they want to stay, but because leaving carries its own social cost.</p>
<h2>Economic Dependence</h2>
<p>When a partner controls finances, reporting abuse can feel like choosing between safety and survival. Many survivors, particularly women, cannot afford to leave an abusive relationship. Without access to money, housing, or employment, the path out feels closed even when the door is technically open.</p>
<div class=\"callout\"><p><strong>A note on economic freedom:</strong> Supporting survivors often means addressing practical needs first. Access to shelter, income, and financial independence can make the difference between leaving and staying in a dangerous situation.</p></div>
<h2>Lack of Trust in Institutions</h2>
<p>Survivors who have previously been dismissed, victim-blamed, or re-traumatized by police officers, health workers, or court officials are understandably reluctant to try again. Institutional mistrust is not irrational; it is a learned response to real experiences. Rebuilding that trust requires consistent, trauma-informed practice from every part of the response system.</p>
<h2>Not Recognizing It as Abuse</h2>
<p>This is more common than many realize. When violence is normalized within a family or community, when a child grows up watching it as a regular part of adult relationships, it can take years before a person understands that what they experienced was wrong and was not their fault. Awareness and education are not secondary to response; they are part of it.</p>
<h2>What Communities Can Do</h2>
<p>Communities carry significant power in shifting the culture around GBV. Practical actions include:</p>
<ul><li>Believing survivors when they speak, without requiring proof as a condition of support.</li><li>Refusing to normalize abusive behavior or make excuses for perpetrators.</li><li>Holding institutions accountable for how they treat survivors who come forward.</li><li>Supporting organizations that work with survivors on the ground in Nakuru County.</li><li>Talking openly about GBV in homes, schools, and places of worship.</li></ul>
<div class=\"warning-box\"><div class=\"warning-title\">The core truth</div><p>Silence protects perpetrators. Speaking, in whatever way feels safe, begins to dismantle their power. Every conversation that names GBV as unacceptable shifts the culture, one community at a time.</p></div>
<div class=\"info-box\"><div class=\"info-title\">If You Need Support</div><p>Help is available across Nakuru County. Whether you need a safe house, a counsellor, legal advice, or simply someone to talk to, reach out to any resource listed on our Resources Map.</p></div>
""".strip(),
    },
]


class Command(BaseCommand):
    help = "Import featured GBV editorial articles"

    def handle(self, *args, **options):
        created = 0
        updated = 0
        for payload in ARTICLES:
            article, was_created = Article.objects.get_or_create(
                title=payload["title"],
                defaults={
                    "author": "Voices Against Violence Editorial Team",
                    "category": payload["category"],
                    "content": payload["content"],
                    "image": payload["image"],
                    "published": True,
                    "read_time": payload["read_time"],
                    "views": 0,
                },
            )
            if was_created:
                created += 1
                continue

            changed = False
            for field in ["author", "category", "content", "image", "published", "read_time"]:
                value = payload[field]
                if getattr(article, field) != value:
                    setattr(article, field, value)
                    changed = True
            if changed:
                article.updated_at = timezone.now()
                article.save()
                updated += 1

        self.stdout.write(self.style.SUCCESS(
            f"Imported featured GBV articles. Created: {created}, Updated: {updated}"
        ))
