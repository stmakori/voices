from django.core.management.base import BaseCommand
from django.utils import timezone

from Voices.models import Article


ARTICLES = [
    {
        "title": "What Support Services Are Available for GBV Survivors?",
        "category": "support",
        "read_time": 6,
        "image": "articles/support-1.png",
        "content": """
<p class=\"intro\">Surviving gender based violence is only the beginning of a long journey. Access to the right support services, timely, compassionate, and comprehensive, can be the difference between a survivor being able to rebuild their life and remaining trapped in a cycle of danger and trauma.</p>
<p>GBV support services span several interconnected areas.</p>
<h2>Healthcare Services</h2>
<p>Healthcare services are often a survivor's first point of contact. Hospitals and clinics trained in GBV response can provide immediate medical care, treat injuries, test for sexually transmitted infections, provide emergency contraception, and collect forensic evidence if the survivor chooses to pursue legal action. Critically, healthcare workers should respond with empathy and without judgment. A poor initial response can deter survivors from seeking further help.</p>
<h2>Psychosocial Support</h2>
<p>Psychosocial support addresses the emotional and mental health consequences of GBV. Trained counselors and social workers can provide individual therapy, group support, and crisis intervention. Peer support groups, where survivors connect with others who have lived experience, are particularly powerful, reducing isolation and building resilience.</p>
<h2>Safe Houses and Shelters</h2>
<p>Safe houses and shelters provide emergency refuge for survivors who need to leave a dangerous situation. A good shelter is more than a roof: it offers safety, legal support, childcare, skills training, and a pathway toward independent living.</p>
<h2>Legal and Justice Services</h2>
<p>Legal and justice services help survivors navigate reporting, filing for protection orders, accessing courts, and pursuing accountability. Many survivors face significant barriers to accessing formal justice, including fear of retaliation, distrust of police, or lack of awareness of their rights, making dedicated legal aid services essential.</p>
<h2>Economic Support</h2>
<p>Economic support through cash transfers, livelihood training, and employment assistance helps survivors rebuild financial independence, reducing the risk of returning to abusive situations out of economic necessity.</p>
<div class=\"info-box\"><div class=\"info-title\">Key Message</div><p>No single service is sufficient on its own. Integrated, survivor centered approaches that connect these services are the gold standard of GBV response.</p></div>
""".strip(),
    },
    {
        "title": "How to Support a Survivor of GBV: A Guide for Friends and Family",
        "category": "support",
        "read_time": 6,
        "image": "articles/support-2.jpeg",
        "content": """
<p class=\"intro\">When someone you care about discloses that they are experiencing or have experienced gender based violence, your response in that moment matters enormously. Survivors often feel profound shame, fear, and uncertainty. The way those around them react can either open a door to healing, or close it.</p>
<h2>Listen Without Judgment</h2>
<p>Your first role is to hear what they are sharing without interrupting, questioning their account, or minimizing what they have been through. Avoid asking questions like \"what did you do to provoke it?\" or \"why did not you leave sooner?\" These questions, however well intentioned, place responsibility on the survivor and can cause significant harm.</p>
<h2>Believe Them</h2>
<p>False reports of GBV are statistically rare. When someone takes the enormous risk of disclosing abuse, the most important thing you can do is believe them. \"I believe you, and I am glad you told me\" can be among the most powerful sentences a survivor hears.</p>
<h2>Follow Their Lead</h2>
<p>Respect their choices, even if you disagree with them. Survivors are the experts on their own situation, including the risks they face. Pressuring someone to leave before they are ready, or to report when they are not, can increase danger and erode trust.</p>
<h2>Offer Practical Support</h2>
<p>Ask what they need. This might be help finding a shelter, accompanying them to a clinic, researching legal options, or simply being present. Sometimes the most supportive thing is just to check in regularly and remind them they are not alone.</p>
<h2>Know Your Limits</h2>
<p>Supporting a GBV survivor can be emotionally demanding. You do not need to have all the answers. Connect them with professional services and take care of your own wellbeing too.</p>
<div class=\"callout\"><p><strong>Key Message:</strong> Being a source of steady, non judgmental support can be life changing and sometimes life saving.</p></div>
""".strip(),
    },
    {
        "title": "The Importance of One Stop Centres in GBV Response",
        "category": "support",
        "read_time": 6,
        "image": "articles/support-3.jpeg",
        "content": """
<p class=\"intro\">In many countries, survivors of gender based violence must navigate a fragmented maze of services: visit the hospital for medical care, travel to the police station to report, find a different office for legal aid, and locate yet another organization for counseling. Each step requires courage, time, and resources. At each point, a survivor may encounter judgment, bureaucracy, or insensitivity that causes them to give up and go home.</p>
<h2>What One Stop Centres Do</h2>
<p>One Stop Centres (OSCs) are designed to break this cycle. By bringing essential services under one roof, medical care, psychosocial support, police assistance, legal aid, and shelter referrals, OSCs dramatically lower the barriers to help seeking.</p>
<h2>Why Integration Matters</h2>
<p>For a survivor who has just fled an abusive situation, the prospect of visiting multiple offices can be overwhelming and retraumatizing. Walking into a single, safe, survivor friendly space where trained professionals from different disciplines work together changes everything.</p>
<h2>Evidence From Practice</h2>
<p>Evidence from OSCs across Africa and Asia, including in Kenya where the government has invested in establishing them in public hospitals, shows that integrated service models increase the number of survivors accessing care, improve legal outcomes, and support better recovery. When a nurse, counselor, and legal officer can confer directly, the survivor receives consistent, coordinated support rather than conflicting advice.</p>
<h2>Survivor Centered Design</h2>
<p>Critically, quality OSCs are designed around the survivor's experience. Staff receive ongoing training in trauma informed care. Spaces are private and confidential. Children are accommodated. Services are available around the clock because crises do not keep office hours.</p>
<div class=\"warning-box\"><div class=\"warning-title\">Key Message</div><p>Scaling up and improving access to One Stop Centres is one of the most impactful investments a community or government can make in GBV response.</p></div>
""".strip(),
    },
]


class Command(BaseCommand):
    help = "Import support category GBV editorial articles"

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
                f"Imported support GBV articles. Created: {created}, Updated: {updated}"
            )
        )
