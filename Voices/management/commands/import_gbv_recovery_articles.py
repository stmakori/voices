from django.core.management.base import BaseCommand
from django.utils import timezone

from Voices.models import Article


ARTICLES = [
    {
        "title": "The Road to Recovery: Understanding Trauma After GBV",
        "category": "recovery",
        "read_time": 7,
        "image": "articles/recovery-1.jpeg",
        "content": """
<p class=\"intro\">Recovery from gender based violence is not linear. It is not a fixed destination that survivors arrive at in a set number of steps. It is a deeply personal, often non linear journey that looks different for every person, and understanding what survivors may experience along the way is essential for those supporting them.</p>
<h2>Understanding Trauma</h2>
<p>Trauma is a natural response to an overwhelmingly threatening experience. When a person experiences GBV, their brain and body respond to protect them, activating the fight or flight response, storing memories in fragmented ways, and often leaving the nervous system in a state of prolonged alertness long after the immediate danger has passed.</p>
<p>Common responses to GBV trauma include flashbacks and intrusive memories, nightmares, difficulty concentrating, hypervigilance (a constant sense of being in danger), emotional numbness or disconnection, intense feelings of shame or guilt, anxiety, and depression. Many survivors meet the criteria for Post Traumatic Stress Disorder (PTSD), though not all trauma presents in this way.</p>
<div class=\"callout\"><p><strong>Important:</strong> These responses are not signs of weakness. They are the mind and body's attempts to process an experience that should never have happened.</p></div>
<h2>Evidence Based Therapeutic Support</h2>
<p>Recovery is supported by safety, connection, and the gradual rebuilding of a sense of agency and control. Therapy, particularly trauma focused approaches such as Trauma Focused Cognitive Behavioral Therapy (TF CBT) and Eye Movement Desensitization and Reprocessing (EMDR), has strong evidence for helping survivors process traumatic memories and reduce symptoms.</p>
<h2>Recovery Beyond the Clinical</h2>
<p>But recovery is not only a clinical process. It is also social, spiritual, and practical. For many survivors, the restoration of meaningful relationships, economic stability, and a sense of purpose is as central to healing as any therapy.</p>
<div class=\"info-box\"><div class=\"info-title\">Key Message</div><p>Every survivor deserves to be met with patience, compassion, and the belief that healing is possible.</p></div>
""".strip(),
    },
    {
        "title": "Rebuilding Self Worth After Gender Based Violence",
        "category": "recovery",
        "read_time": 6,
        "image": "articles/recovery-2.jpeg",
        "content": """
<p class=\"intro\">One of the most lasting harms that gender based violence inflicts is not physical. It is the systematic destruction of a survivor's sense of self worth. Abusers often use emotional manipulation, constant criticism, isolation, and control to make survivors believe they are worthless, unlovable, and powerless. Rebuilding that foundation of self worth is a central and often overlooked part of recovery.</p>
<p>Many survivors emerge from abusive situations with a distorted self image, shaped by years of being told who they are. Reclaiming a true sense of identity, separate from what an abuser said or did, is an act of profound courage.</p>
<h2>The Role of Therapy</h2>
<p>Therapy plays a central role here. Cognitive Behavioral Therapy (CBT) helps survivors identify and challenge the negative beliefs about themselves that abuse has embedded. Over time, replacing "I deserved this" with a clear understanding of "this was not my fault" can fundamentally shift a survivor's relationship with themselves.</p>
<h2>Community and Belonging</h2>
<p>Community and belonging are equally powerful. Isolation is a tool of abuse; connection is a tool of healing. Support groups, friendships, and community involvement help survivors rebuild social bonds, practice trust, and experience being valued by others.</p>
<h2>Reclaiming Agency</h2>
<p>Reclaiming agency is transformative. When survivors make their own decisions, however small, about their daily lives, they rebuild the sense of control that abuse stripped away. This might mean choosing where to live, returning to education, pursuing a creative interest, or setting a new personal goal.</p>
<h2>Self Compassion</h2>
<p>Self compassion, treating yourself with the kindness you would offer a close friend, is a skill that can be learned and practiced. It is not self indulgence; it is a critical component of healing.</p>
<div class=\"info-box\"><div class=\"info-title\">Key Message</div><p>You are more than what was done to you. Recovery is not about returning to who you were before. It is about becoming who you are meant to be.</p></div>
""".strip(),
    },
    {
        "title": "The Role of Community in Healing From GBV",
        "category": "recovery",
        "read_time": 6,
        "image": "articles/recovery-3.jpeg",
        "content": """
<p class=\"intro\">Individual therapy and clinical support are vital parts of GBV recovery, but healing does not happen only in a therapist's office. For many survivors, the community around them is the most powerful healing force available.</p>
<p>Humans are social beings. We are shaped by our relationships, and we heal within them. When a community responds to GBV with compassion, belief, and active support, rather than shame, silence, or blame, it creates the conditions in which survivors can genuinely recover.</p>
<h2>Peer Support Groups</h2>
<p>Peer support groups are among the most effective community based healing resources. When survivors come together to share their experiences, they break the isolation that abuse thrives on. Hearing "I have been through something similar, and I survived" can provide hope that no professional can fully replicate. Peer support also builds practical knowledge as survivors share information about legal processes, service providers, and coping strategies.</p>
<h2>Family and Social Networks</h2>
<p>Family and social networks matter deeply. Survivors who have the support of family members, who believe them, stand by them, and do not pressure them to reconcile with perpetrators, recover more fully and more quickly. Conversely, rejection by family, being pressured into silence, or facing stigma can compound trauma significantly.</p>
<h2>Faith Communities</h2>
<p>Faith communities, where they are survivor centered and trained in appropriate responses, can provide spiritual sustenance, belonging, and practical support. Religious leaders who speak out about GBV and support survivors play an important role in shifting community norms.</p>
<h2>Economic Reintegration</h2>
<p>Economic reintegration, being supported to return to work, complete education, or develop new livelihoods, reconnects survivors with purpose and independence.</p>
<div class=\"callout\"><p><strong>Key Message:</strong> Recovery from GBV is not something survivors should have to do alone. When communities commit to walking alongside survivors, without judgment, without conditions, without timeline, they become agents of healing.</p></div>
""".strip(),
    },
]


class Command(BaseCommand):
    help = "Import recovery and healing GBV editorial articles"

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
                f"Imported recovery GBV articles. Created: {created}, Updated: {updated}"
            )
        )
