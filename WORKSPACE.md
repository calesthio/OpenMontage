# Workspace — Semih's OpenMontage Action Hub

> **Bu dosya senin için, OSS değil.** OpenMontage upstream pull yaparsan untracked görünür — push etmediğin sürece sorun yok.
> **Upstream CLAUDE.md → AGENT_GUIDE.md** zorunlu sıra (Rule Zero) hâlâ geçerli; bu dosya o akışın **üstüne** eklenir, yerine geçmez.

---

## Hızlı Karar Ağacı (yeni Claude session açtığında)

```
Sen ne yapmak istiyorsun?
│
├─ "<MARKA> için OpenMontage kurulumu yapacağız"  (TRIGGER PHRASE)
│   "<marka> için yeni client setup"
│   "Yeni proje aç <marka>"
│   "/onboard <marka>"
│   → internal/CLIENT_ONBOARDING.md protokolü çalıştır (6-step)
│   → internal/scripts/new-client.sh "<marka>" otomatik scaffolder
│
├─ "Bir client için video üreteceğim" (workspace zaten var)
│   → internal/SERVICE_PLAYBOOK.md  (intake → delivery, 7 aşama)
│
├─ "Sıfırdan kendi videom için brief vereceğim"
│   → Mode 1: claude → "use hybrid pipeline, [brief]"  (chat ile)
│
├─ "Hızlı zero-key demo ile sistem testi"
│   → make demo  ($0, ~1 dk)
│
├─ "Reference video klonlamak istiyorum"
│   → ~/.claude/skills/video-clone-system.md skill'i tetikle
│   → ~/.claude/scripts/video-clone-analyze.py <video.mp4>
│
├─ "Visual preview / Remotion ile düzenle"
│   → Mode 3: cd remotion-composer && npx remotion studio
│
└─ "Bilgi/komut hatırlamadım, lookup lazım"
    → internal/QUICKSTART.md   (cheat sheet)
    → internal/KNOWLEDGE_INDEX.md  (her şeyin map'i)
```

## ⚡ Trigger Phrase: Client Onboarding

Kullanıcı bu cümlelerden birini söyleyince Claude **otomatik** `internal/CLIENT_ONBOARDING.md` protokolünü çalıştırır:

| Trigger | Aksiyon |
|---|---|
| "XYZ için OpenMontage kurulumu yapacağız" | new-client.sh + intake.md aç |
| "<marka> için yeni client setup" | Aynı |
| "Yeni iş geldi, <marka> için hazırlık" | Aynı |
| "Client onboard et: <marka>" | Aynı |
| "/onboard <marka>" | Aynı |

Detaylı protokol: `internal/CLIENT_ONBOARDING.md` (6 adım: scaffold → intake → preflight → reference → meta → pipeline-suggest).

---

## İlk Aktivasyon (her session)

```bash
cd ~/projects/OpenMontage && source .venv/bin/activate
make preflight   # tool envanteri sağlık check
```

`preflight` çıktısında 9/9 composition tool görmen lazım. Görmüyorsan `make setup` koş.

---

## Knowledge Stack (cross-link map)

```
Bu dosya (WORKSPACE.md)
   └─ internal/                         ← TÜM kullanıcı dökümanları burada (gitignored)
       ├─ README.md                      ← klasör haritası
       ├─ CHANGELOG.md                   ← setup geçmişi (her session'ın özeti)
       ├─ KNOWLEDGE_INDEX.md             ← her dosyaya lookup
       ├─ QUICKSTART.md                  ← komut cheat sheet
       ├─ SERVICE_PLAYBOOK.md            ← client iş akışı (intake → delivery)
       ├─ CLIENT_ONBOARDING.md           ← "X için kurulum" trigger protokolü
       ├─ ROADMAP.md                     ← sonraki adımlar
       ├─ scripts/new-client.sh          ← workspace scaffolder
       ├─ templates/client-intake.md     ← intake form template
       └─ research/                      ← araştırma notları + patch'ler
           ├─ INDEX.md
           ├─ openmontage-prompt-postprocess-fix.md
           ├─ openmontage-video-prompt-button.md
           ├─ sample-artifacts-{brief,script}.json
           └─ archive/                   ← eski büyük roadmap'ler

Upstream OSS (DOKUNMA):
   ├─ AGENT_GUIDE.md                    ← Rule Zero
   ├─ pipeline_defs/{hybrid,cinematic,animated-explainer}.yaml
   ├─ skills/creative/video-gen-prompting.md  ← universal 5-aspect
   ├─ skills/creative/prompting/*.md    ← per-provider grammar
   └─ lib/shot_prompt_builder.py:82-144 ← deterministik builder

Senin custom OpenMontage uzantıların (gitignored değil ama upstream'le çakışmaz):
   ├─ tools/audio/qwen3_tts.py
   ├─ tools/graphics/kie_nano_banana.py
   ├─ tools/graphics/kie_gpt_image.py
   ├─ tools/video/kie_seedance.py
   ├─ tools/video/kie_kling.py
   └─ lib/kie_client.py

Memory (her Claude session'da auto-load):
   ├─ ~/.claude/projects/-Users-abalioglu/memory/skill_openmontage.md
   ├─ ~/.claude/projects/-Users-abalioglu/memory/skill_openmontage_advanced.md
   ├─ ~/.claude/projects/-Users-abalioglu/memory/skill_openmontage_client_onboarding.md
   └─ ~/.claude/projects/-Users-abalioglu/memory/project_openmontage_service_offering.md
```

---

## Servis Modeli — Kısaca

**Pivot (2026-05-07):** AdSwap SaaS pause edildi. Yeni yön: **e-ticaret markalarına video prodüksiyon servisi** (agency model, not SaaS).

- Hedef pazar: Shopify/WooCommerce dropship + DTC beauty/cosmetics
- Pricing fikri: UGC starter $300, brand cinematic $800, full campaign $1500
- Edge: OpenMontage 9-katman + Seedance multi-shot identity + character consistency protocol — kullanıcı sadece brief verir, biz prompt + render + compose orchestrasyonunu yaparız
- Detay: `internal/SERVICE_PLAYBOOK.md`

---

## Bugünün Durumu

- ✅ OpenMontage kurulu, .venv izole, .env API key'leri kontrolü gerekiyor (FAL/OpenAI/ElevenLabs/Google)
- ✅ 3 demo render (sağlık testi geçti — `projects/demos/renders/`)
- ✅ Prompt engineering insights belgelendi (memory + Documents)
- ✅ Surgical post-process patch yazıldı (Desktop + Documents) — diğer Claude session'a paslanmaya hazır
- ⏳ Sample portfolio üretimi (3-5 sektör)
- ⏳ Pricing landing page (agentized.io altına)
- ⏳ İlk client outreach
