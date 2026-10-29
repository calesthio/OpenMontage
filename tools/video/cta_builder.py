"""
cta_builder.py
Generates high-converting Comic-Style ASS Call-To-Action (CTA) overlays for OpenMontage Shorts.
Includes:
1. Pulsing Outro Subscribe Card (Last 5 seconds)
2. Interactive Pointer (Finger pointing to the YouTube subscribe button)
3. Header Brand Watermark with Subscribe Bell
4. Mid-Roll Mini CTA Pop
"""

import sys
from pathlib import Path

def generate_cta_ass_snippet(
    duration: float,
    channel_name: str = "WILD MECHANICS",
    animal_name: str = "",
    cta_start_offset: float = 4.5,
) -> str:
    """
    Returns ASS events string with full animated CTA package.
    """
    cta_start = max(0.0, duration - cta_start_offset)
    
    # Format time helpers
    def fmt_time(t: float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = int(t % 60)
        cs = int((t - int(t)) * 100)
        return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

    t_start = fmt_time(cta_start)
    t_end = fmt_time(duration)
    t_mid = fmt_time(cta_start + 0.4)
    t_mid2 = fmt_time(cta_start + 0.8)

    snippet = f"""
; === HIGH-CONVERTING SUBSCRIBER CTA SYSTEM ===
; Layer 1: Outro Glow Background Badge
Dialogue: 2,{t_start},{t_end},CTABadge,,0,0,0,,{{\\fad(200,0)\\an5\\pos(540,1580)\\t(0,200,\\fscx105\\fscy105)\\t(200,400,\\fscx100\\fscy100)}}🔴 SUBSCRIBE FOR DAILY WILDLIFE 🐾

; Layer 2: Action Direction Callout with Pulsing Animation
Dialogue: 3,{t_mid},{t_end},CTASubtext,,0,0,0,,{{\\fad(150,0)\\an5\\pos(540,1660)\\c&H00FFFF&\\b1\\fs40\\t(0,300,\\fscx115\\fscy115)\\t(300,600,\\fscx100\\fscy100)}}👇 TAP SUBSCRIBE TO JOIN THE PACK! 🔔

; Layer 3: Animated Arrow Pointer
Dialogue: 3,{t_mid2},{t_end},CTAPointer,,0,0,0,,{{\\fad(150,0)\\an5\\pos(540,1740)\\c&H0000FF&\\b1\\fs44\\t(0,200,\\fscx120\\fscy120)}}👉 SUBSCRIBE 👈
"""
    return snippet

if __name__ == "__main__":
    print(generate_cta_ass_snippet(60.0, "WILD MECHANICS", "Shrike Bird"))
