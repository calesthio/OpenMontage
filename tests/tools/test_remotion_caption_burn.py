from tools.video.remotion_caption_burn import RemotionCaptionBurn


def test_chinese_protected_terms_merge_character_timestamps():
    tool = RemotionCaptionBurn()
    text = "系统提交发布助手"
    segments = [
        {
            "text": f"如果你同时安装了「{text}」这个 Skill。",
            "start": 0.0,
            "end": 1.8,
            "words": [
                {"word": char, "start": index * 0.1, "end": (index + 1) * 0.1}
                for index, char in enumerate(text)
            ],
        }
    ]

    captions = tool._segments_to_word_captions(
        segments,
        protected_terms=tool._caption_protected_terms(segments, None),
    )

    assert captions == [{"word": text, "startMs": 0, "endMs": 800}]


def test_explicit_protected_terms_prevent_caption_splits():
    captions = [
        {"word": "系", "startMs": 0, "endMs": 100},
        {"word": "统", "startMs": 100, "endMs": 200},
        {"word": "问", "startMs": 200, "endMs": 300},
        {"word": "题", "startMs": 300, "endMs": 400},
        {"word": "分", "startMs": 400, "endMs": 500},
        {"word": "析", "startMs": 500, "endMs": 600},
        {"word": "助", "startMs": 600, "endMs": 700},
        {"word": "手", "startMs": 700, "endMs": 800},
    ]

    protected = RemotionCaptionBurn._protect_caption_terms(captions, ["系统问题分析助手"])

    assert protected == [{"word": "系统问题分析助手", "startMs": 0, "endMs": 800}]
