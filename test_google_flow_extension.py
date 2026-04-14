#!/usr/bin/env python3
"""Google Flow Video Tool Extension Smoke Tests

Runs 5 test scenarios to verify:
1. Backward compatibility (default values)
2. Model parameter (veo_lite)
3. Aspect ratio (4:3)
4. Frames parameter
5. Ingredients parameter
"""

import sys
import time
from pathlib import Path
from tools.video.google_flow_video import GoogleFlowVideo

def run_test(test_num: int, name: str, inputs: dict) -> bool:
    """Run a single smoke test and report results."""
    print(f"\n{'='*60}")
    print(f"Test {test_num}: {name}")
    print(f"{'='*60}")
    print(f"Input: {inputs}")

    tool = GoogleFlowVideo()

    # Check tool status
    status = tool.get_status()
    print(f"Tool status: {status.value}")

    if status.value == "unavailable":
        print(f"⚠️  SKIP: Tool unavailable (check credentials/Playwright)")
        return False

    print("Starting generation (will wait 3-5 minutes)...")
    start = time.time()

    try:
        result = tool.execute_safe(inputs)
    except Exception as e:
        print(f"❌ FAILED: Exception during execution: {e}")
        return False

    elapsed = round(time.time() - start, 2)

    if result.success:
        print(f"✅ PASSED in {elapsed}s")
        print(f"Output: {result.data.get('output_path')}")
        output_path = Path(result.data.get("output_path", ""))
        if output_path.exists():
            size_mb = output_path.stat().st_size / (1024 * 1024)
            print(f"File size: {size_mb:.2f} MB")
        if "model" in result.data:
            print(f"Model used: {result.data['model']}")
        if "ingredients" in result.data and result.data['ingredients']:
            print(f"Ingredients: {result.data['ingredients']}")
        return True
    else:
        print(f"❌ FAILED: {result.error}")
        return False


def main() -> None:
    """Run all 5 smoke tests."""
    output_dir = Path("projects/smoke-test-google-flow-extension")
    output_dir.mkdir(parents=True, exist_ok=True)

    tests = [
        (
            1,
            "Backward Compatibility (defaults)",
            {
                "prompt": "A red car driving fast through a city at sunset",
                "output_path": str(output_dir / "test1_backward_compat.mp4"),
            },
        ),
        (
            2,
            "Model Parameter (veo_lite)",
            {
                "prompt": "A red car driving fast through a city at sunset",
                "model": "veo_lite",
                "output_path": str(output_dir / "test2_veo_lite.mp4"),
            },
        ),
        (
            3,
            "Aspect Ratio (4:3)",
            {
                "prompt": "A red car driving fast through a city at sunset",
                "aspect_ratio": "4:3",
                "output_path": str(output_dir / "test3_aspect_4_3.mp4"),
            },
        ),
        (
            4,
            "Frames Parameter",
            {
                "prompt": "A red car driving fast through a city at sunset",
                "frames": 180,
                "output_path": str(output_dir / "test4_frames.mp4"),
            },
        ),
        (
            5,
            "Ingredients Parameter",
            {
                "prompt": "A red car driving fast through a city at sunset",
                "ingredients": ["cinematic", "slow motion", "golden hour"],
                "output_path": str(output_dir / "test5_ingredients.mp4"),
            },
        ),
    ]

    print("\n" + "="*60)
    print("Google Flow Video Tool Extension Smoke Tests")
    print("="*60)

    results = []
    for test_num, name, inputs in tests:
        passed = run_test(test_num, name, inputs)
        results.append((test_num, name, passed))

    # Summary
    print(f"\n{'='*60}")
    print("Test Summary")
    print(f"{'='*60}")
    for test_num, name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - Test {test_num}: {name}")

    passed_count = sum(1 for _, _, p in results if p)
    print(f"\nTotal: {passed_count}/{len(tests)} tests passed")

    if passed_count == len(tests):
        print("🎉 All tests passed!")
        sys.exit(0)
    else:
        print("⚠️  Some tests failed. Check output above for details.")
        sys.exit(1)


if __name__ == "__main__":
    main()
