from django.core.management.base import BaseCommand
from django.utils import timezone

from Voices.models import Article


ARTICLES = [
    {
        "title": "Prevention Starts Before Violence Begins: A Community Approach",
        "category": "prevention",
        "read_time": 6,
        "image": "articles/prevention-1.jpeg",
        "content": """
<p class=\"intro\">The most effective strategy against gender based violence is preventing it before it occurs. Prevention is not a single program or campaign. It is a transformation of the social, cultural, economic, and institutional conditions that allow violence to happen and continue.</p>
<p>Effective GBV prevention operates at multiple levels.</p>
<h2>Individual Level</h2>
<p>At the individual level, prevention focuses on awareness and attitude change. Education programs that teach young people about consent, healthy relationships, gender equality, and conflict resolution help reduce abusive behavior. When boys and young men are engaged early and taught to value equality and reject controlling behavior, the norms that support GBV begin to weaken.</p>
<h2>Relationship Level</h2>
<p>At the relationship level, couples counseling, parenting programs, and peer support groups help people build non violent communication skills. These approaches also help individuals recognize early warning signs of abusive relationships before situations escalate.</p>
<h2>Community Level</h2>
<p>At the community level, local leaders such as religious figures, teachers, health workers, and elders play a key role. When these trusted individuals speak out against GBV, challenge harmful norms, and support survivors, community attitudes begin to shift. Bystander intervention training also empowers people to safely act when they witness concerning behavior.</p>
<h2>Structural Level</h2>
<p>At the structural level, prevention requires addressing root causes such as gender inequality, economic dependence, limited access to education, and weak legal protections. Policies that promote women's economic participation, close gender gaps, and keep girls in school help reduce the conditions that make GBV more likely.</p>
<div class=\"info-box\"><div class=\"info-title\">Key Message</div><p>Prevention is not passive. It requires every individual to reflect and ask what they are doing, or failing to do, that allows violence to continue.</p></div>
""".strip(),
    },
    {
        "title": "The Role of Education in Preventing Gender Based Violence",
        "category": "prevention",
        "read_time": 5,
        "image": "articles/prevention-2.jpeg",
        "content": """
<p class=\"intro\">Education is one of the most powerful tools in preventing gender based violence. When young people learn about equality, respect, and healthy relationships early, they are better equipped to recognize, resist, and reject violence.</p>
<h2>Comprehensive Sexuality Education (CSE)</h2>
<p>Comprehensive sexuality education goes beyond biology. It includes consent, body autonomy, gender norms, healthy and unhealthy relationships, and how to seek help. Young people who receive quality education are more likely to identify coercive behavior, report abuse, and avoid engaging in violence.</p>
<h2>Safe School Environments</h2>
<p>Schools must be safe spaces. GBV occurs in and around schools in the form of bullying, harassment, and assault. Schools that address these issues directly, train staff, and enforce zero tolerance for abuse provide protection for learners.</p>
<h2>Teacher Training</h2>
<p>Teachers play a critical role. Educators who understand GBV, model respectful behavior, and respond appropriately when abuse is disclosed can make a life changing difference. In many cases, teachers are the first trusted adults young people turn to.</p>
<h2>Curriculum Reform</h2>
<p>Curriculum also matters. When learning materials present women as equal to men, show girls as leaders, and portray boys expressing emotions in healthy ways, they reinforce positive gender norms.</p>
<div class=\"callout\"><p><strong>Key Message:</strong> Education alone cannot end GBV. However, investing in gender transformative education and keeping girls in school significantly reduces the risk of violence.</p></div>
""".strip(),
    },
    {
        "title": "Engaging Men and Boys as Allies in Preventing GBV",
        "category": "prevention",
        "read_time": 6,
        "image": "articles/prevention-3.jpeg",
        "content": """
<p class=\"intro\">For many years, the responsibility of preventing gender based violence has largely been placed on women and girls. While important, this approach overlooks a key reality. Most GBV is perpetrated by men, and prevention requires changing the beliefs and behaviors that drive it.</p>
<h2>Changing Masculinity Norms</h2>
<p>Engaging men and boys as allies is not about assigning blame. It is about responsibility and recognizing that harmful ideas about masculinity affect everyone. Programs such as Promundo's Program H and the One Man Can campaign in South Africa show that when men participate in discussions about power, relationships, and gender roles, both attitudes and behaviors improve.</p>
<h2>Bystander Intervention</h2>
<p>Bystander intervention is highly effective. When men challenge harmful behavior among peers, such as rejecting sexist jokes or stepping in during aggressive situations, it sends a strong message that violence is not acceptable.</p>
<h2>Positive Fatherhood</h2>
<p>Fatherhood programs that encourage men to be present, nurturing, and respectful help shape healthier family dynamics. Children raised in such environments are more likely to develop respectful relationships in the future.</p>
<h2>Recognizing Male Survivors</h2>
<p>It is also important to recognize that men can be survivors of GBV, especially in conflict situations. Support services must be inclusive and accessible to all survivors.</p>
<div class=\"warning-box\"><div class=\"warning-title\">Key Message</div><p>Ending GBV is not solely a women's issue. It is a shared responsibility that requires the active involvement of men and boys as part of the solution.</p></div>
""".strip(),
    },
]


class Command(BaseCommand):
    help = "Import prevention category GBV editorial articles"

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
                f"Imported prevention GBV articles. Created: {created}, Updated: {updated}"
            )
        )
