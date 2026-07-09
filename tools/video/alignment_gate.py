#!/usr/bin/env python3
"""
Alignment Gate Module: 

This right here, implements a deterministic semantic audio-visual quality gate to ensure narration 
beats are perfectly mapped and aligned with visual timeline intent layouts before 
rendering."""

import os
import json
from typing import List, Dict, Any


def check_timing_staleness(old_meta: Dict[str, Any], new_meta: Dict[str, Any], drift_tolerance: float = 0.5) -> bool:
    """
    Requirement 1: Invalidate previously approved scene timings if the underlying 
    TTS properties or narration text changes.
    
    Args:
        old_meta: Metadata from the previously compiled/approved layout.
        new_meta: Incoming metadata from current production stage.
        drift_tolerance: Allowed variance in seconds before forcing invalidation.
    """
    monitored_keys = ["tts_provider", "voice", "speaking_rate", "narration_text"]
    
    # Check for direct categorical parameter changes
    for key in monitored_keys:
        if old_meta.get(key) != new_meta.get(key):
            return True
            
    # Check for duration drift beyond a tight tolerance layout constraint
    old_duration = float(old_meta.get("narration_duration", 0.0))
    new_duration = float(new_meta.get("narration_duration", 0.0))
    
    if abs(old_duration - new_duration) > drift_tolerance:
        return True
        
    return False


def verify_audio_visual_alignment(
    narration_beats: List[Dict[str, Any]], 
    visual_scenes: List[Dict[str, Any]], 
    transition_tolerance: float = 0.2
) -> Dict[str, Any]:
    """
    Requirement 2 & 5: Manifest-based deterministic checker verifying 
    visual scene coverage over final transcript time bounds.
    
    Args:
        narration_beats: List of speech intervals containing timestamps and structural intents.
        visual_scenes: Active layout structure timelines containing scene slices.
        transition_tolerance: Maximum allowable lag/bleed time for topic changes.
    """
    report = {
        "status": "PASS",
        "mismatches": [],
        "mapping_table": [],
        "sampled_timestamps": []
    }
    
    for beat in narration_beats:
        b_id = beat.get("beat_id")
        start = float(beat.get("transcript_start", 0.0))
        end = float(beat.get("transcript_end", 0.0))
        intent = beat.get("required_visual_intent")
        expected_scene_id = beat.get("expected_scene_id")
        
        # Enforce contract coverage check across the visual array
        is_covered = False
        for scene in visual_scenes:
            if scene.get("scene_id") == expected_scene_id:
                # Scene must wrap the timing window within allowed transit boundary tolerances
                s_start = float(scene.get("start", 0.0))
                s_end = float(scene.get("end", 0.0))
                
                if s_start <= (start + transition_tolerance) and s_end >= (end - transition_tolerance):
                    is_covered = True
                    break
                    
        if not is_covered:
            report["status"] = "FAIL"
            report["mismatches"].append({
                "timestamp": start,
                "beat_id": b_id,
                "error": f"Narration segment '{intent}' (ID: {b_id}) is missing matching visual scene allocation or timing drifted outside tolerance."
            })
            
        report["mapping_table"].append({
            "beat_id": b_id,
            "time_range": f"{start}s - {end}s",
            "required_intent": intent,
            "expected_scene_id": expected_scene_id,
            "aligned": is_covered
        })
        
        # Requirement 3: Extract evaluation reference points for frame capture samples
        report["sampled_timestamps"].extend([
            start,                   # Beat Start
            round((start + end) / 2, 2), # Beat Middle
            end                      # Beat End
        ])
        
    # Add scene transition borders to safety tracking array
    for scene in visual_scenes:
        report["sampled_timestamps"].append(float(scene.get("start", 0.0)))
        report["sampled_timestamps"].append(float(scene.get("end", 0.0)))
        
    # Clean up, deduplicate, and sort tracking timestamp list
    report["sampled_timestamps"] = sorted(list(set([t for t in report["sampled_timestamps"] if t >= 0.0])))
    return report


def run_synthetic_test() -> None:
    """
    Requirement 4: Enforce system compliance by validating that explicitly 
    shifted timeline frames fail the execution quality gate.
    """
    mock_beats = [{
        "beat_id": "beat_101",
        "transcript_start": 4.5,
        "transcript_end": 9.0,
        "required_visual_intent": "Render statistical dynamic b-roll asset charts",
        "expected_scene_id": "scene_chart_delta"
    }]
    
    # Synthetic failure injection: Scene starts at 6.0s instead of covering 4.5s
    shifted_scenes = [{
        "scene_id": "scene_chart_delta",
        "start": 6.0,
        "end": 12.0
    }]
    
    test_report = verify_audio_visual_alignment(mock_beats, shifted_scenes)
    
    assert test_report["status"] == "FAIL", "Quality Gate Error: Deterministic rule check failed to block invalid timing mismatch."
    print(">>> [SUCCESS] Synthetic alignment gate test completed. Timing shift correctly caught.")


if __name__ == "__main__":
    # Self-test confirmation harness execution check
    run_synthetic_test()

