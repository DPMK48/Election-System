import random
import math

def generate_synthetic_fingerprint_template(seed_id=42, num_minutiae=35, noise_jitter=0.0):
    """
    Generates a deterministic, realistic biometric minutiae template for testing.
    
    Args:
        seed_id (int): Seed for deterministic coordinate distribution.
        num_minutiae (int): Number of minutiae points (~30-50).
        noise_jitter (float): Spatial jitter to simulate probe variations on live touch (0.0 to 3.0 px).
        
    Returns:
        dict: {
            'template_id': str,
            'finger_type': str,
            'minutiae': list of dicts [{'x': float, 'y': float, 'direction': float, 'type': str}]
        }
    """
    rng = random.Random(seed_id)
    minutiae = []
    
    center_x, center_y = 250.0, 250.0
    
    for i in range(num_minutiae):
        # Generate points in elliptical whorl pattern
        radius = rng.uniform(20.0, 180.0)
        angle = rng.uniform(0, 2 * math.pi)
        
        # Elliptical aspect ratio
        base_x = center_x + radius * math.cos(angle) * 0.85
        base_y = center_y + radius * math.sin(angle) * 1.15
        
        # Add probe jitter if specified
        if noise_jitter > 0:
            base_x += random.gauss(0, noise_jitter)
            base_y += random.gauss(0, noise_jitter)
            
        direction = (angle + math.pi / 2 + rng.uniform(-0.2, 0.2)) % (2 * math.pi)
        m_type = 'ending' if rng.random() < 0.65 else 'bifurcation'
        
        minutiae.append({
            'x': round(base_x, 2),
            'y': round(base_y, 2),
            'direction': round(direction, 4),
            'type': m_type
        })
        
    return {
        'template_id': f"TEMPLATE-SEED-{seed_id}",
        'finger_type': 'RIGHT_INDEX',
        'minutiae': minutiae
    }

# Standard test templates
TEMPLATE_VOTER_1 = generate_synthetic_fingerprint_template(seed_id=101, num_minutiae=38)
TEMPLATE_VOTER_2 = generate_synthetic_fingerprint_template(seed_id=202, num_minutiae=42)
TEMPLATE_VOTER_3 = generate_synthetic_fingerprint_template(seed_id=303, num_minutiae=36)
TEMPLATE_IMPOSTOR = generate_synthetic_fingerprint_template(seed_id=999, num_minutiae=40)
