from django.core.management.base import BaseCommand
from django.utils import timezone

from Voices.models import Article


ARTICLES = [
    {
        "title": "Know Your Legal Rights as a Survivor of GBV",
        "category": "legal",
        "read_time": 6,
        "image": "articles/legal-1.png",
        "content": """
<p class=\"intro\">Understanding your legal rights is one of the most empowering things a GBV survivor can do. The law exists to protect you, and knowing what it says gives you the ability to hold perpetrators accountable and to access the protection you deserve.</p>
<p>In many countries, gender based violence is covered by multiple layers of law: criminal law (which addresses assault, rape, harassment, and stalking), family law (which governs protection orders, divorce, child custody, and property rights), and specialized GBV legislation where it exists.</p>
<h2>Protection Orders</h2>
<p>Protection orders are among the most immediately useful legal tools available to survivors. Also called restraining orders or injunctions, they are court issued documents that legally prohibit a perpetrator from contacting or coming near a survivor. Violating a protection order is a criminal offense. In many jurisdictions, they can be obtained quickly, sometimes within hours, and do not require the survivor to press full criminal charges.</p>
<h2>The Right to Report</h2>
<p>The right to report is fundamental. Every survivor has the right to report GBV to law enforcement. While this process can be difficult, and not every survivor will choose it for valid reasons, it is important to know that police are legally obligated to receive your report.</p>
<h2>Medical and Forensic Evidence</h2>
<p>Medical evidence collected soon after an assault can be critical if you decide to pursue legal action later. Many hospitals that work with GBV survivors can collect and preserve forensic evidence, even if you are not yet certain you want to report.</p>
<h2>Legal Aid Access</h2>
<p>Legal aid services can help survivors who cannot afford a lawyer. Knowing where to find free or subsidized legal support is essential. Contact your nearest GBV support organization or legal aid office.</p>
<div class=\"info-box\"><div class=\"info-title\">Key Message</div><p>You have rights. You deserve protection. And you do not have to navigate the legal system alone.</p></div>
""".strip(),
    },
    {
        "title": "Understanding Protection Orders: What They Are and How to Get One",
        "category": "legal",
        "read_time": 6,
        "image": "articles/legal-2.jpeg",
        "content": """
<p class=\"intro\">For many survivors of gender based violence, a protection order is a critical first step toward safety. Understanding what it is, how it works, and how to obtain one can make an enormous practical difference.</p>
<p>A protection order is a legal document issued by a court that restricts a perpetrator's behavior toward a survivor. Depending on the jurisdiction and circumstances, it can prohibit the perpetrator from contacting or approaching the survivor; require the perpetrator to leave a shared home; restrict access to shared children; and prevent the perpetrator from harassing or threatening the survivor in person, by phone, or online.</p>
<h2>Why It Matters</h2>
<p>Violating a protection order is a criminal offense that can result in arrest, fines, or imprisonment. This is why obtaining one, even when a survivor does not wish to pursue a full criminal case, can provide meaningful protection.</p>
<h2>How to Apply</h2>
<p>In most countries, applications for protection orders are made at a magistrate court or family court. You do not typically need a lawyer to apply, though legal aid can be helpful. You will be asked to describe the violence or threats you have experienced. In urgent situations, an emergency or interim protection order can often be granted the same day, before a full hearing takes place.</p>
<h2>What You Will Need</h2>
<p>A description of incidents of violence or threats (written if possible), any supporting evidence (photos of injuries, threatening messages, witness information), and identification documents.</p>
<div class=\"warning-box\"><div class=\"warning-title\">Important Note</div><p>A protection order is a legal tool, not a physical barrier. If you are in immediate danger, your safety plan should include a support network, a safe place to go, and emergency contacts.</p></div>
<div class=\"callout\"><p><strong>Key Message:</strong> Know your rights, and use every tool available to protect yourself.</p></div>
""".strip(),
    },
    {
        "title": "Gaps in GBV Law: Why Legal Reform Still Matters",
        "category": "legal",
        "read_time": 7,
        "image": "articles/legal-3.jpeg",
        "content": """
<p class=\"intro\">Laws alone do not stop gender based violence. But the absence of strong, comprehensive legislation, or the existence of laws that actively discriminate against women, makes survivors dramatically more vulnerable. Understanding the state of GBV law, and where gaps remain, is essential for anyone working toward a more just world.</p>
<p>In recent decades, significant progress has been made. Many countries have criminalized domestic violence, marital rape, sexual harassment, and FGM, acts that were previously either legal or widely tolerated under the law. International frameworks such as CEDAW (the Convention on the Elimination of All Forms of Discrimination Against Women) and the UN Declaration on the Elimination of Violence Against Women set important global standards.</p>
<h2>Major Gaps Persist</h2>
<p>Marital rape is still not criminalized in a significant number of countries, reflecting a deeply embedded legal assumption that marriage constitutes permanent consent. In practice, this leaves many survivors with no legal recourse.</p>
<p>Economic violence, the deliberate control of a partner's finances and access to resources, is rarely addressed explicitly in law, despite being one of the most common mechanisms abusers use to trap survivors.</p>
<p>Technology facilitated GBV, including non consensual sharing of intimate images and cyber stalking, has outpaced legislation in most jurisdictions. Survivors increasingly find that online abuse is treated as a lesser harm, or not addressed by law at all.</p>
<h2>Implementation Gaps</h2>
<p>Implementation gaps are perhaps the most critical challenge. Even where strong laws exist, enforcement is often weak. Police may lack training in GBV response, prosecutors may be reluctant to pursue cases, and survivors may face hostility within the justice system.</p>
<div class=\"info-box\"><div class=\"info-title\">Key Message</div><p>Legal reform is not the end of the work, but it is a necessary foundation. Advocacy for better laws, better enforcement, and a more survivor centered justice system remains urgently necessary.</p></div>
""".strip(),
    },
]


class Command(BaseCommand):
    help = "Import legal category GBV editorial articles"

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

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported legal GBV articles. Created: {created}, Updated: {updated}"
            )
        )
