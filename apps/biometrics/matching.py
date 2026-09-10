import math
import numpy as np

# Standard similarity threshold for SourceAFIS minutiae verification
DEFAULT_MATCH_THRESHOLD = 40.0

def angle_difference(a1, a2):
    """Calculate absolute difference between two angles in radians [0, pi]."""
    diff = abs(a1 - a2) % (2 * math.pi)
    return min(diff, 2 * math.pi - diff)

def match_minutiae_templates(probe_template, reference_template, max_distance=25.0, max_angle_diff=0.52):
    """
    SourceAFIS-compatible Minutiae Feature Matcher.
    
    Compares two minutiae templates using spatial translation alignment,
    Euclidean distance thresholds, angular delta tolerances, and topological scoring.
    
    Args:
        probe_template (dict): Probe template containing 'minutiae' list: [{'x': float, 'y': float, 'direction': float, 'type': str}]
        reference_template (dict): Reference enrolled template.
        max_distance (float): Spatial distance tolerance in pixels (default 25.0 px).
        max_angle_diff (float): Angular tolerance in radians (~30 degrees / 0.52 rad).
        
    Returns:
        dict: {
            'is_match': bool,
            'similarity_score': float, # 0.0 to 100.0+
            'matched_minutiae_count': int,
            'probe_count': int,
            'reference_count': int,
            'confidence': str ('HIGH', 'MEDIUM', 'LOW', 'REJECTED')
        }
    """
    probe_minutiae = probe_template.get('minutiae', [])
    ref_minutiae = reference_template.get('minutiae', [])

    n_probe = len(probe_minutiae)
    n_ref = len(ref_minutiae)

    if n_probe == 0 or n_ref == 0:
        return {
            'is_match': False,
            'similarity_score': 0.0,
            'matched_minutiae_count': 0,
            'probe_count': n_probe,
            'reference_count': n_ref,
            'confidence': 'REJECTED'
        }

    best_matched_pairs = 0
    best_score = 0.0

    # Test potential alignments using anchor minutiae pairs
    # In SourceAFIS, pairs of minutiae define translation and rotation offsets
    candidate_anchors = min(15, n_probe)
    ref_anchors = min(15, n_ref)

    for p_idx in range(candidate_anchors):
        p_anchor = probe_minutiae[p_idx]
        for r_idx in range(ref_anchors):
            r_anchor = ref_minutiae[r_idx]

            # Translation delta
            dx = r_anchor['x'] - p_anchor['x']
            dy = r_anchor['y'] - p_anchor['y']
            d_theta = r_anchor.get('direction', 0) - p_anchor.get('direction', 0)

            # Match counter under this alignment
            matched_pairs = 0
            matched_weights = 0.0
            used_ref_indices = set()

            for pm in probe_minutiae:
                # Transform probe minutia to reference coordinate space
                # Apply rotation around anchor and translation
                px_shifted = pm['x'] - p_anchor['x']
                py_shifted = pm['y'] - p_anchor['y']

                cos_t = math.cos(d_theta)
                sin_t = math.sin(d_theta)

                px_rot = px_shifted * cos_t - py_shifted * sin_t + r_anchor['x']
                py_rot = px_shifted * sin_t + py_shifted * cos_t + r_anchor['y']
                p_dir_rot = (pm.get('direction', 0) + d_theta) % (2 * math.pi)

                # Find closest compatible reference minutia
                best_dist = max_distance
                best_ref_idx = -1

                for rm_idx, rm in enumerate(ref_minutiae):
                    if rm_idx in used_ref_indices:
                        continue

                    dist = math.hypot(px_rot - rm['x'], py_rot - rm['y'])
                    if dist < best_dist:
                        ang_diff = angle_difference(p_dir_rot, rm.get('direction', 0))
                        if ang_diff <= max_angle_diff:
                            best_dist = dist
                            best_ref_idx = rm_idx

                if best_ref_idx != -1:
                    used_ref_indices.add(best_ref_idx)
                    matched_pairs += 1
                    # Closeness weight bonus
                    dist_weight = 1.0 - (best_dist / max_distance) * 0.5
                    type_weight = 1.2 if pm.get('type') == ref_minutiae[best_ref_idx].get('type') else 0.8
                    matched_weights += (dist_weight * type_weight)

            # Calculate similarity score normalized by harmonic mean of minutiae counts
            harmonic_mean = (2.0 * n_probe * n_ref) / (n_probe + n_ref)
            score = (matched_weights / harmonic_mean) * 100.0

            if score > best_score:
                best_score = score
                best_matched_pairs = matched_pairs

    is_match = best_score >= DEFAULT_MATCH_THRESHOLD

    if not is_match:
        confidence = 'REJECTED'
    elif best_score >= 70.0:
        confidence = 'HIGH'
    else:
        confidence = 'MEDIUM'


    return {
        'is_match': is_match,
        'similarity_score': round(best_score, 2),
        'matched_minutiae_count': best_matched_pairs,
        'probe_count': n_probe,
        'reference_count': n_ref,
        'confidence': confidence
    }

def evaluate_far_frr(genuine_scores, impostor_scores, thresholds=[20.0, 30.0, 40.0, 50.0, 60.0, 70.0]):
    """
    Evaluates False Acceptance Rate (FAR) and False Rejection Rate (FRR)
    across multiple similarity thresholds for academic defense & benchmarks.
    """
    results = []
    total_genuine = len(genuine_scores) if genuine_scores else 1
    total_impostor = len(impostor_scores) if impostor_scores else 1

    for t in thresholds:
        # False Rejection: Genuine attempts that scored BELOW threshold
        fr_count = sum(1 for s in genuine_scores if s < t)
        frr = (fr_count / total_genuine) * 100.0

        # False Acceptance: Impostor attempts that scored AT OR ABOVE threshold
        fa_count = sum(1 for s in impostor_scores if s >= t)
        far = (fa_count / total_impostor) * 100.0

        results.append({
            'threshold': t,
            'FAR_percent': round(far, 4),
            'FRR_percent': round(frr, 4),
            'genuine_tested': total_genuine,
            'impostor_tested': total_impostor
        })

    return results
