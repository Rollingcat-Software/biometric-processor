"""Find images that pass quality checks."""
import requests
from pathlib import Path

base_dir = Path(r'C:\Users\ahabg\OneDrive\Belgeler\GitHub\FIVUCSAS\practice-and-test\DeepFacePractice1\images')
person_dirs = sorted([d for d in base_dir.iterdir() if d.is_dir()])

print('Finding images that pass quality checks...\n')

good_images = {}

for person_dir in person_dirs:
    images = sorted(list(person_dir.glob('*.jpg')) + list(person_dir.glob('*.png')))
    print(f'Testing {person_dir.name}: ({len(images)} images)')
    
    for img in images:
        with open(img, 'rb') as f:
            files = {'file': (img.name, f, 'image/jpeg')}
            data = {'user_id': f'test_{person_dir.name}'}
            try:
                response = requests.post(
                    'http://localhost:8001/api/v1/enroll', 
                    files=files, 
                    data=data, 
                    timeout=30
                )
                result = response.json()
                
                if response.status_code == 200:
                    quality = result.get('quality_score', 0)
                    print(f'  ✅ {img.name}: SUCCESS (quality: {quality:.1f})')
                    good_images[person_dir.name] = str(img)
                    break
                else:
                    error_msg = result.get('message', 'Unknown').split('.')[0][:50]
                    print(f'  ❌ {img.name}: {error_msg}...')
            except Exception as e:
                print(f'  ❌ {img.name}: Error - {str(e)[:40]}')
    
    if person_dir.name not in good_images:
        print(f'  ⚠️  No good images found for {person_dir.name}')
    print()

print('\n' + '='*60)
print('SUMMARY')
print('='*60)
print(f'Found {len(good_images)} usable images out of {len(person_dirs)} persons\n')

if good_images:
    print('Good images:')
    for person, img_path in good_images.items():
        print(f'  {person}: {Path(img_path).name}')
else:
    print('⚠️  No images passed quality checks!')
    print('\nTips:')
    print('  - Images should have clear, front-facing faces')
    print('  - Good lighting')
    print('  - Not too blurry')
    print('  - Face size at least 80x80 pixels')
