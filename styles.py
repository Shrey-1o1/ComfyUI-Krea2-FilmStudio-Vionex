"""Curated VIONEX cinematic prompt styles."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


CINEMATIC_STYLES: dict[str, dict[str, str]] = {
    "silver_thriller": {
        "label": "Silver-blue thriller",
        "summary": "Sony VENICE 2 · restrained contemporary suspense",
        "camera": "Sony VENICE 2, 50mm spherical cinema lens, shoulder-height tracking shot, medium composition, gentle forward dolly movement, shallow depth of field, subtle handheld micro-movement, realistic motion blur, soft natural lens breathing.",
        "lighting": "Soft overcast daylight, diffused sky illumination, cool ambient fill, gentle reflections from wet pavement and glass surfaces, realistic bounce light, faint atmospheric haze.",
        "grade": "Clean cinematic contrast, cool silver-blue mids, neutral skin tones, slightly lifted blacks, controlled highlights, muted saturation, fine film grain, polished contemporary feature-film finish.",
        "mood": "Tense, grounded, mysterious, sophisticated, quietly dramatic, immersive sense of realism.",
        "style": "Photorealistic live-action thriller film still, physically accurate anatomy and motion, realistic wardrobe textures, detailed environmental surfaces, natural atmospheric depth, restrained cinematic composition, premium theatrical realism, 2.39:1 widescreen, no text, no watermark, no artificial CGI look.",
    },
    "golden_action": {
        "label": "Golden action rush",
        "summary": "ARRI Alexa Mini LF · aggressive anamorphic action",
        "camera": "ARRI Alexa Mini LF, 24mm anamorphic cinema lens, extremely low ground-level tracking shot, wide composition, aggressive forward movement, deep spatial perspective, subtle camera vibration, realistic directional motion blur, pronounced anamorphic edge distortion.",
        "lighting": "Harsh late-afternoon sunlight cutting across the frame, strong backlight, long dramatic shadows, bright rim lighting, dusty volumetric atmosphere, natural flare streaks, reflected warm light from surrounding surfaces.",
        "grade": "High-contrast blockbuster grade, blazing golden highlights, rich burnt-orange mids, deep teal shadows, strong but controlled saturation, crushed blacks, subtle halation, textured film grain.",
        "mood": "Explosive, urgent, fearless, adrenaline-heavy, dangerous, larger-than-life.",
        "style": "Photorealistic live-action action-film still, intense physical realism, detailed debris and environmental interaction, realistic clothing movement, dynamic perspective, large-scale cinematic spectacle, practical-effects aesthetic, 2.39:1 widescreen, no text, no watermark, no cartoon styling.",
    },
    "midnight_noir": {
        "label": "Midnight neo-noir",
        "summary": "RED V-RAPTOR XL · intimate nocturnal city portrait",
        "camera": "RED V-RAPTOR XL, 85mm cinema prime, long-lens close-to-medium tracking shot, slightly elevated angle, compressed background perspective, very shallow depth of field, stabilized movement with subtle organic drift, delicate motion blur, natural optical compression.",
        "lighting": "Blue-hour ambient light mixed with warm practical city lights, soft neon reflections, gentle edge lighting, realistic window illumination, subtle atmospheric glow, controlled specular highlights.",
        "grade": "Deep midnight blues, warm tungsten-orange accents, rich blacks, luminous skin tones, selective saturation, soft highlight roll-off, mild bloom, elegant cinematic grain.",
        "mood": "Intimate, stylish, nocturnal, confident, emotionally charged, metropolitan.",
        "style": "Photorealistic live-action neo-noir film still, realistic skin and fabric detail, sophisticated urban production design, natural light interaction, cinematic bokeh, premium dramatic photography, 2.39:1 widescreen, no text, no watermark, no synthetic plastic textures.",
    },
    "morning_adventure": {
        "label": "Morning adventure",
        "summary": "Panavision DXL2 · sweeping optimistic crane move",
        "camera": "Panavision Millennium DXL2, 40mm anamorphic lens, high-angle crane shot transitioning into a descending tracking perspective, wide composition, medium depth of field, smooth sweeping movement, subtle inertial camera lag, realistic lens distortion and motion blur.",
        "lighting": "Bright early-morning sunlight, soft warm directional light, cool shadow fill, crisp atmospheric clarity, reflective highlights on architecture and vehicles, gentle natural haze.",
        "grade": "Luminous warm highlights, soft cyan shadows, crisp whites, natural greens and reds, medium contrast, clean highlight retention, restrained film grain, expansive premium adventure-film finish.",
        "mood": "Optimistic, adventurous, energetic, expansive, uplifting, full of possibility.",
        "style": "Photorealistic live-action adventure film still, believable physics and anatomy, richly detailed locations, natural environmental scale, realistic textures and materials, broad cinematic depth, elegant IMAX-style composition, 2.39:1 widescreen, no text, no watermark, no exaggerated fantasy proportions.",
    },
    "aerial_spectacle": {
        "label": "Aerial large-format spectacle",
        "summary": "ARRI Alexa 65 · top-down high-speed aerial chase",
        "camera": "ARRI Alexa 65, 18mm ultra-wide cinema lens, top-down aerial chase shot, extremely wide composition, deep depth of field, high-speed synchronized tracking, smooth aerial stabilization with slight natural drift, realistic peripheral distortion and motion blur.",
        "lighting": "Intense midday sunlight, hard direct illumination, sharply defined shadows, bright reflected light from concrete and glass, realistic skylight bounce, slight heat haze in the distance.",
        "grade": "Crisp high-dynamic-range contrast, bright neutral highlights, slightly cool shadows, natural saturated primaries, rich blacks without crushing detail, subtle grain, ultra-clean large-format cinema finish.",
        "mood": "Overwhelming, kinetic, spectacular, vertiginous, powerful, highly energetic.",
        "style": "Photorealistic live-action large-format spectacle, physically accurate scale and perspective, ultra-detailed city geometry, realistic environmental motion, authentic materials, immense spatial depth, IMAX-scale realism, 2.39:1 widescreen, no text, no watermark, no video-game aesthetic.",
    },
    "sunset_hero": {
        "label": "Sunset hero profile",
        "summary": "Sony VENICE 2 · emotional parallel tracking shot",
        "camera": "Sony VENICE 2, 75mm anamorphic cinema lens, profile side-tracking shot, medium-close composition, camera moving perfectly parallel with the subject, shallow depth of field, smooth stabilized motion with subtle handheld texture, horizontal motion blur, organic anamorphic breathing.",
        "lighting": "Sunset backlight with strong golden rim, soft frontal fill from surrounding surfaces, deep cool shadows, glowing atmospheric haze, gentle flare artifacts, realistic reflective bounce.",
        "grade": "Warm copper highlights, rich navy shadows, natural skin tones, slightly desaturated backgrounds, deep contrast, subtle halation, refined grain structure, premium emotional blockbuster finish.",
        "mood": "Determined, heroic, emotional, graceful, powerful, iconic.",
        "style": "Photorealistic live-action character-driven film still, realistic facial detail and anatomy, physically believable fabric movement, elegant background separation, cinematic lighting falloff, dramatic feature-film polish, 2.39:1 widescreen, no text, no watermark, no excessive stylization.",
    },
    "storm_chase": {
        "label": "Storm chase realism",
        "summary": "ARRI Alexa 35 · gritty rear three-quarter pursuit",
        "camera": "ARRI Alexa 35, 28mm spherical cinema lens, rear three-quarter chase shot, low shoulder-height perspective, medium-wide composition, moderate depth of field, fast Steadicam-style movement, energetic camera sway, realistic acceleration blur, subtle lens imperfections.",
        "lighting": "Stormy late-afternoon environment, diffused gray sky, shafts of sunlight breaking through clouds, strong reflective highlights from wet streets, cool ambient fill, subtle mist and atmospheric scattering.",
        "grade": "Steel-blue shadows, pale warm highlights, slightly desaturated palette, strong local contrast, rich wet-surface reflections, lifted atmospheric blacks, fine grain, grounded cinematic realism.",
        "mood": "Urgent, gritty, relentless, dramatic, unpredictable, high-stakes.",
        "style": "Photorealistic live-action chase-film still, realistic environmental physics, wet-surface detail, believable human motion, natural wardrobe response to wind and speed, tactile production design, 2.39:1 widescreen, no text, no watermark, no glossy CGI appearance.",
    },
    "monumental_scifi": {
        "label": "Monumental sci-fi",
        "summary": "Blackmagic URSA Cine 17K 65 · slow low-angle hero frame",
        "camera": "Blackmagic URSA Cine 17K 65, 32mm large-format cinema lens, static low-angle hero composition with a very slow push-in, medium-wide framing, medium depth of field, almost imperceptible handheld breathing, minimal motion blur, natural perspective falloff.",
        "lighting": "Dramatic nighttime lighting from large practical sources, strong white-blue key light, warm orange practical accents, deep shadow pockets, subtle atmospheric smoke, realistic bounce and reflective spill.",
        "grade": "Deep blacks, cool cobalt shadows, bright neutral highlights, warm amber practicals, controlled saturation, smooth highlight roll-off, pronounced but elegant film grain, premium sci-fi theatrical finish.",
        "mood": "Imposing, mysterious, confident, monumental, futuristic, awe-inspiring.",
        "style": "Photorealistic live-action science-fiction film still, physically plausible lighting and materials, realistic human proportions, intricate architectural detail, practical-set realism, cinematic atmosphere, large-format depth and scale, 2.39:1 widescreen, no text, no watermark, no artificial neon overload.",
    },
    "rainy_drama": {
        "label": "Rainy prestige drama",
        "summary": "Panavision DXL2 · restrained telephoto observation",
        "camera": "Panavision Millennium DXL2, 100mm spherical cinema lens, distant observational telephoto shot, eye-level composition, subject framed against compressed layers of architecture, extremely shallow depth of field, slow lateral camera drift, refined motion blur, natural optical softness.",
        "lighting": "Soft rainy daylight, diffused window light, wet-surface reflections, cool ambient skylight, subtle warm interior practicals in the distance, realistic mist, low-contrast natural illumination.",
        "grade": "Desaturated cool-gray palette, restrained blue-green shadows, warm skin and practical accents, soft contrast, gentle highlight bloom, lifted blacks, delicate grain, sophisticated dramatic-film finish.",
        "mood": "Reflective, lonely, suspenseful, atmospheric, emotionally restrained, cinematic.",
        "style": "Photorealistic live-action prestige drama still, realistic weather interaction, fine skin detail, authentic fabric textures, subdued environmental design, delicate depth separation, naturalistic cinematography, 2.39:1 widescreen, no text, no watermark, no exaggerated visual effects.",
    },
    "epic_orbit": {
        "label": "Epic amber-teal orbit",
        "summary": "ARRI Alexa 65 · sweeping anamorphic orbit",
        "camera": "ARRI Alexa 65, 21mm anamorphic cinema lens, sweeping orbit shot from a low three-quarter angle, wide cinematic composition, medium-to-deep depth of field, fast circular camera movement, smooth stabilized inertia, dramatic parallax, realistic motion blur and anamorphic curvature.",
        "lighting": "Fiery sunset mixed with cool atmospheric skylight, dramatic side-and-back lighting, strong silhouette separation, warm reflections across metal and glass, subtle volumetric rays, atmospheric dust glowing in the distance.",
        "grade": "Bold amber-and-teal cinematic palette, intense warm highlights, deep cyan-blue shadows, rich blacks, natural skin tones, restrained saturation, soft halation, textured film grain, epic theatrical blockbuster finish.",
        "mood": "Triumphant, exhilarating, epic, fearless, cinematic, enormous sense of scale and momentum.",
        "style": "Photorealistic live-action epic film still, physically accurate anatomy and movement, realistic environmental interaction, detailed architecture and materials, expansive atmospheric perspective, premium VFX integration with practical realism, IMAX-scale spectacle, 2.39:1 widescreen, no text, no watermark, no exaggerated cartoon proportions.",
    },
}


def style_suffix(style_id: str) -> str:
    """Return a stable prompt suffix for the selected style, or an empty string."""

    item = CINEMATIC_STYLES.get(style_id)
    if not item:
        return ""
    return "\n".join(
        f"{label}: {item[key]}"
        for label, key in (
            ("Camera", "camera"),
            ("Lighting", "lighting"),
            ("Color grade", "grade"),
            ("Mood", "mood"),
            ("Style", "style"),
        )
    )


def style_payload() -> list[dict[str, Any]]:
    """Return JSON-safe style descriptions for the frontend."""

    return [{"value": key, **deepcopy(value)} for key, value in CINEMATIC_STYLES.items()]
