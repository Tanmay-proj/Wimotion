import shutil
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN

PPT_PATH = Path(r"E:\WIFI_INTERFEROMETRIC_NEURAL_SENSING\intermediate_ppt.pptx")
BACKUP_PATH = Path(r"E:\WIFI_INTERFEROMETRIC_NEURAL_SENSING\intermediate_ppt_before_common_changes.pptx")

# 1. Create a safe backup before any edits
shutil.copy2(PPT_PATH, BACKUP_PATH)
print(f"[OK] Backup created at: {BACKUP_PATH}")

prs = Presentation(str(PPT_PATH))
print(f"Total Slides: {len(prs.slides)}")

COLOR_GOLD_TEXT  = RGBColor(255, 235, 0)
COLOR_MUTED_TEXT = RGBColor(90, 100, 115)

for idx, slide in enumerate(prs.slides, 1):
    shapes_to_remove = []
    
    for sh in slide.shapes:
        top_in = sh.top / 914400 if sh.top is not None else 0
        
        # Check for any bottom footer shapes or lines (top > 6.7 inches)
        if top_in > 6.8:
            txt = sh.text_frame.text if sh.has_text_frame else ''
            if 'INTERMEDIATE PROGRESS' in txt or 'OC TANMAY' in txt or sh.height / 914400 < 0.1:
                shapes_to_remove.append(sh)
                continue
        
        # Heading adjustments (top < 1.3 inches, inside the red banner)
        if top_in < 1.3 and sh.has_text_frame:
            txt = sh.text_frame.text.strip().replace('\n', ' ')
            if txt and len(txt) < 55 and idx > 1: # Don't alter slide 1 banner since user perfected it
                tf = sh.text_frame
                tf.word_wrap = False
                tf.margin_left = Inches(0.0)
                tf.margin_right = Inches(0.0)
                tf.margin_top = Inches(0.0)
                tf.margin_bottom = Inches(0.0)
                for p in tf.paragraphs:
                    p.alignment = PP_ALIGN.CENTER
                    p.font.name = "Calibri"
                    p.font.size = Pt(54)
                    p.font.bold = True
                    p.font.underline = True
                    p.font.color.rgb = COLOR_GOLD_TEXT
                    for r in p.runs:
                        r.font.name = "Calibri"
                        r.font.size = Pt(54)
                        r.font.bold = True
                        r.font.underline = True
                        r.font.color.rgb = COLOR_GOLD_TEXT
                print(f"Slide {idx:02d}: Heading set to 54pt -> '{txt}'")
        
        # Small captions under pictures (currently 15pt -> bump to 18pt for high readability)
        if top_in >= 5.8 and sh.has_text_frame:
            tf = sh.text_frame
            for p in tf.paragraphs:
                current_sz = p.font.size.pt if (p.font and p.font.size) else (p.runs[0].font.size.pt if p.runs and p.runs[0].font.size else 0)
                if current_sz <= 16:
                    p.font.size = Pt(18)
                    for r in p.runs:
                        r.font.size = Pt(18)
                    clean_caption = p.text[:35].encode('ascii', 'ignore').decode('ascii')
                    print(f"Slide {idx:02d}: Caption bumped from {current_sz}pt to 18pt -> '{clean_caption}...'")

        # Metric subtitle labels on Slide 14 (Test results)
        if idx == 14 and top_in >= 2.0 and top_in <= 3.2 and sh.has_text_frame:
            tf = sh.text_frame
            for p in tf.paragraphs:
                p.font.size = Pt(18)
                p.font.bold = True
                for r in p.runs:
                    r.font.size = Pt(18)
                    r.font.bold = True
            print(f"Slide 14: Metric label bumped to 18pt bold -> '{sh.text_frame.text[:35]}'")

    # Remove any unwanted bottom shapes
    for sh in shapes_to_remove:
        sp = sh._element
        sp.getparent().remove(sp)
        print(f"Slide {idx:02d}: Removed footer artifact shape.")

prs.save(str(PPT_PATH))
print(f"[SUCCESS] All common changes saved cleanly into: {PPT_PATH}")
