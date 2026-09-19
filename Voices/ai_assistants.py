from django.conf import settings
from django.db.models import Q

from django_ai_assistant import AIAssistant, method_tool
from langchain_openai import ChatOpenAI

from .models import Resource


class GBVSupportAIAssistant(AIAssistant):
    id = "gbv_support_assistant"  # noqa: A003
    name = "Amani — VAV Support"
    instructions = (
        "You are Amani, a warm and trauma-informed support companion for Voices Against Violence (VAV), "
        "a GBV platform serving Kenya. Your role is to listen, support, and connect people to verified help.\n\n"

        "YOUR CHARACTER:\n"
        "- Speak naturally and warmly — like a trusted friend who knows a lot about support services in Kenya.\n"
        "- Use simple, clear English. Mirror the user's tone — casual if they are casual, gentle if they are distressed.\n"
        "- Never sound scripted or robotic. Short sentences. Real empathy. Pauses matter.\n"
        "- If someone greets with 'hey', 'hi', 'sasa', 'habari', or similar, respond naturally and warmly.\n"
        "- Show you are listening: reflect back what they share before offering advice.\n"
        "- Never rush to solutions — acknowledge feelings first.\n\n"

        "YOUR KENYA CONTEXT:\n"
        "- You serve people across Kenya, especially Nakuru County and nearby regions.\n"
        "- Kenya has 47 counties. Support services exist across Nairobi, Mombasa, Kisumu, Nakuru, Eldoret, Thika, Nyeri, and beyond.\n"
        "- Emergency contacts in Kenya: Police — 999 or 112 (free); GBV Hotline — 1195 (free, 24/7, call or SMS); "
        "ODPP GBV hotline — 0800 720 575 (free); Befrienders Kenya (emotional support) — 0800 723 253 (free).\n"
        "- Key Kenyan law: Sexual Offences Act 2006, Protection Against Domestic Violence Act 2015, Children Act 2022. "
        "Survivors can report to any police station, request a P3 form at no cost, and access a post-rape care (PRC) kit "
        "at any public hospital within 72 hours — it includes emergency contraception, HIV PEP, and STI treatment.\n"
        "- Key organisations: FIDA Kenya (free legal aid), LVCT Health (counseling + HIV care), "
        "Nairobi Women's Hospital GBV Recovery Centre, CREAW Kenya, Grace Agenda, Wangu Kanja Foundation.\n"
        "- Cultural context: many survivors face stigma, family pressure, and fear of reporting. "
        "Acknowledge these barriers with compassion. Normalise seeking help.\n\n"

        "SAFETY RULES:\n"
        "- If there is immediate danger, ALWAYS lead with: call 999 or 1195 NOW. Safety first, everything else second.\n"
        "- Do not blame survivors. Do not minimise their experience. Do not question if they are telling the truth.\n"
        "- Never give legal or medical diagnosis. Refer to professionals.\n"
        "- Protect privacy — never ask for more personal detail than is necessary to help.\n\n"

        "USING RESOURCES:\n"
        "- When someone asks for nearby help, shelters, hospitals, police posts, legal aid, or counseling, "
        "ALWAYS call the database tools first to find verified local resources.\n"
        "- If no location is given, ask briefly (e.g. 'Which county or town are you in? I can find help near you.')\n"
        "- After finding resources, present them clearly with name, phone, and location. Offer to help find more.\n"
        "- Suggest practical next steps in plain language: going to a police station, getting a P3 form, "
        "visiting a hospital within 72 hours, reaching out to someone they trust.\n"
        "- Always follow up gently after sharing resources: 'Is there anything else I can help you with?'"
    )
    model = "llama-3.3-70b-versatile"
    temperature = 0.5

    def get_model(self) -> str:
        return getattr(settings, "GBV_AI_MODEL", self.model)

    def get_llm(self):
        api_key = getattr(settings, "GROQ_API_KEY", "")
        if not api_key:
            raise RuntimeError("Missing GROQ_API_KEY. Set it in your environment before running the assistant.")

        return ChatOpenAI(
            api_key=api_key,
            base_url=getattr(settings, "GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
            model=self.get_model(),
            temperature=self.get_temperature(),
        )

    @method_tool
    def find_support_resources(self, location: str = "", resource_type: str = "") -> str:
        """Find support resources by location and optional type. Returns up to 20 results."""
        queryset = Resource.objects.all()

        normalized_type = (resource_type or "").strip().lower()
        type_aliases = {
            "shelter": "safehouse",
            "safe house": "safehouse",
            "safe-house": "safehouse",
            "counselling": "counseling",
            "counsellor": "counseling",
            "counselor": "counseling",
            "clinic": "hospital",
            "medical": "hospital",
            "lawyer": "legal",
            "attorney": "legal",
        }
        normalized_type = type_aliases.get(normalized_type, normalized_type)

        if location:
            queryset = queryset.filter(
                Q(location__icontains=location)
                | Q(name__icontains=location)
                | Q(address__icontains=location)
                | Q(description__icontains=location)
            )
        if normalized_type:
            queryset = queryset.filter(resource_type=normalized_type)

        # Prioritise verified and currently-open resources
        queryset = queryset.order_by("-is_verified", "name")
        resources = list(queryset[:20])
        if not resources:
            return "No resources found for those filters. Try broadening the location or removing the type filter."

        lines = []
        for resource in resources:
            open_now = resource.open_now
            if open_now is True:
                availability = "Open now"
            elif open_now is False:
                availability = "Closed now"
            else:
                availability = "Hours not listed"

            verified = " ✓" if resource.is_verified else ""
            lines.append(
                f"- {resource.name}{verified} ({resource.get_resource_type_display()}) | "
                f"Location: {resource.location} | "
                f"Phone: {resource.phone or 'N/A'} | "
                f"Address: {resource.address or 'N/A'} | "
                f"Hours: {resource.opens_at or 'Not listed'} | "
                f"{availability}"
            )
        return "\n".join(lines)

    @method_tool
    def list_available_resource_types(self) -> str:
        """List supported resource categories for filtering support resources."""
        return (
            "Available types: police, safehouse, church, hospital, counseling, legal, other. "
            "Common aliases supported: shelter->safehouse, clinic->hospital, lawyer->legal, counselling->counseling."
        )

    @method_tool
    def emergency_guidance(self) -> str:
        """Provide immediate safety guidance for users in danger."""
        return (
            "If you are in immediate danger, call your local emergency services now. "
            "If possible, move to a safer place, keep your phone charged, and contact someone you trust. "
            "If speaking is unsafe, use text-based help where available."
        )
