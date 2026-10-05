---
name: xiaohongshu-publish
description: |
  Publish videos to Xiaohongshu (小红书 / XHS / RED) via Android phone automation.
  Uses uiautomator2 + ADB to control a phone running the XHS app.
  Covers: connection setup, UI flow for video posting, Chinese text input,
  popup handling, sound source page, and content declaration page.
allowed-tools: xhs_publisher
metadata:
  openclaw:
    requires:
      env:
        - ADB_PATH
      python:
        - uiautomator2
        - Pillow
    primaryEnv: ADB_PATH
---

# Xiaohongshu (小红书) Video Publishing

Publish video notes to Xiaohongshu by controlling an Android phone via ADB + uiautomator2.

## Prerequisites

1. **Android phone** with USB debugging enabled and connected via USB or same-network WiFi
2. **Python packages**: `pip install uiautomator2 Pillow`
3. **ADB binary**: Either in PATH or set `ADB_PATH` in `.env`
4. **XHS app** installed on the phone (com.xingin.xhs)

## Connection

The `xhs_publisher` tool connects in this order:
1. USB direct (`u2.connect()`)
2. WiFi fallback (`172.20.10.2:5555`, then `10ACAT0J44005MZ:5555`)

## Video Posting UI Flow

The XHS video posting flow has more steps than image posting:

```
+ button → 从相册选择 → Video tab → select first video
→ Next(1) → video editor
→ Next → video editing page (sound source)
→ Next → text editor (title + content)
→ Next → publish preview
→ 发布笔记 → confirm → done
```

### Key differences from image posting:
- Videos auto-select the first item in the grid after switching to the Video tab
- There is an extra "sound source" page after the video editing page — must tap Next to skip
- Content declaration page (AI-generated label) may appear — tap "确认并发布"

## Chinese Text Input

The publisher uses a 4-strategy fallback chain:

| Priority | Method | Reliability |
|----------|--------|-------------|
| 1 | `u2.set_text()` on focused EditText | High — direct field set |
| 2 | `u2.send_keys()` via IME | Medium — needs IME enabled |
| 3 | Clipboard paste (`cmd clipboard set` + KEYCODE_PASTE) | High on Android 13+ |
| 4 | ADB Keyboard broadcast (`ADB_INPUT_TEXT`) | Fallback — works with Chrome ADBKeyboard |

After each input, hierarchy dump verification confirms text was accepted.

## Popup Handling

Dump hierarchy once per round and check all keywords in order:
1. **Draft resume**: "去编辑" → click to resume editing, then navigate through image→text editor
2. **Discard**: "存草稿", "不保存", "放弃", "丢弃"
3. **Dismiss**: "关闭", "取消", "跳过", "暂不", "知道了", "以后再说"

## Limitations

- Requires a physical Android phone connected to the machine
- Screen resolution assumed 1080x2400 (auto-scaled to other resolutions)
- Button positions are calibrated for XHS app version ~8.x layout
- Posting frequency limits apply per XHS platform rules (typically 3-5/day)
- Video must be MP4, 9:16 portrait orientation recommended (1080x1920)

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "No device connected" | USB debugging off or unauthorized | Check phone, accept RSA fingerprint prompt |
| Chinese text shows garbage | IME not switched to uiautomator2 keyboard | Enable ADBKeyboard IME on phone |
| "Cannot find button X" | XHS app version changed layout | Recalibrate coordinates |
| Video appears in wrong tab | Media scanner didn't finish | Increase sleep after push |
| Post button not found | Content declaration page intercepting | Add "确认并发布" to tap targets |
