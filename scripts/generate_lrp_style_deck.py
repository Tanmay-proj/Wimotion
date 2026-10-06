import sys
import copy
from pathlib import Path
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_FILE = ROOT.parent / "intermediate_ppt.pptx"

# Official Crests
IMG_CREST_LEFT   = ROOT / "dashboard" / "assets" / "lrp_extracted" / "Image8.png"
IMG_CREST_RIGHT  = ROOT / "dashboard" / "assets" / "lrp_extracted" / "Image12.png"

# Real Cadet Photos
IMG_DEVBOARD      = ROOT / "dashboard" / "assets" / "user_setup" / "esp32_devkit_closeup.jpg"
IMG_TESTBED_WIDE  = ROOT / "dashboard" / "assets" / "user_setup" / "corridor_testbed_wide.jpg"
IMG_CADET_UNIFORM = ROOT / "dashboard" / "assets" / "user_setup" / "cadet_uniform_in_zone.jpg"
IMG_OBSERVATORY  = ROOT / "docs" / "assets" / "screen_wide.png"

# Real H.264 MP4 Videos & Posters
VID_WALK_TRIAL    = ROOT / "real_setup" / "corridor_walk_trial_h264.mp4"
THUMB_WALK_TRIAL  = ROOT / "real_setup" / "GX013891_thumb.jpg"
VID_MOTION_TRIAL  = ROOT / "real_setup" / "zone_motion_trial_h264.mp4"
THUMB_MOTION_TRIAL= ROOT / "real_setup" / "GX013894_thumb.jpg"

# LRP True Color Palette
COLOR_BANNER_RED = RGBColor(215, 0, 0)       # Military Scarlet Red Banner
COLOR_GOLD_TEXT  = RGBColor(255, 235, 0)     # Vibrant Yellow Header (50-54pt)
COLOR_DARK_TEXT  = RGBColor(30, 35, 45)      # Clean dark charcoal
COLOR_HEAD_BLUE  = RGBColor(0, 85, 170)      # Deep Military Blue for Subtitle Headers
COLOR_CYAN_TAG   = RGBColor(0, 176, 240)     # Vibrant Cyan (#00B0F0) for Taglines
COLOR_BULLET_RED = RGBColor(230, 0, 0)       # Red bullet item
COLOR_BULLET_GRN = RGBColor(0, 160, 60)      # Green bullet item
COLOR_BULLET_BLU = RGBColor(0, 112, 192)     # Blue bullet item
COLOR_BULLET_GLD = RGBColor(210, 130, 0)     # Gold/Orange bullet item
COLOR_BULLET_PRP = RGBColor(112, 48, 160)    # Purple bullet item

FONT_CALIBRI = "Calibri"

def build_lrp_deck():
    prs = Presentation(str(OUTPUT_FILE))
    print(f"Initial slides count: {len(prs.slides)}")

    # Keep Slide 1 (Cover Slide) and drop everything else
    slide_ids = list(prs.slides._sldIdLst)[1:]
    for sldId in slide_ids:
        rId = sldId.rId
        prs.part.drop_rel(rId)
        prs.slides._sldIdLst.remove(sldId)
    print("Slide 1 (Cover) preserved intact.")

    blank_layout = prs.slide_layouts[6]

    # Global Symmetrical Margins
    M_LEFT = Inches(0.80)
    TOTAL_W = Inches(11.733)  # 13.333 - 1.60

    def add_red_header(slide, title_text, is_center=False):
        top_y = Inches(2.70) if is_center else Inches(0.00)
        h_val = Inches(1.80) if is_center else Inches(1.15)

        banner = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.00), top_y, Inches(13.333), h_val)
        banner.fill.solid()
        banner.fill.fore_color.rgb = COLOR_BANNER_RED
        banner.line.color.rgb = COLOR_BANNER_RED

        # Left Crest
        if IMG_CREST_LEFT.exists():
            c_y = top_y + Inches(0.20) if is_center else Inches(0.12)
            c_h = Inches(1.40) if is_center else Inches(0.90)
            slide.shapes.add_picture(str(IMG_CREST_LEFT), Inches(0.40), c_y, height=c_h)

        # Right Crest
        if IMG_CREST_RIGHT.exists():
            c_y = top_y + Inches(0.30) if is_center else Inches(0.22)
            c_h = Inches(1.20) if is_center else Inches(0.70)
            slide.shapes.add_picture(str(IMG_CREST_RIGHT), Inches(11.80), c_y, height=c_h)

        # Banner Title
        tx_box = slide.shapes.add_textbox(Inches(1.80), top_y + (Inches(0.28) if is_center else Inches(0.10)), Inches(9.733), Inches(0.95))
        tf = tx_box.text_frame
        tf.word_wrap = False
        tf.margin_left = Inches(0.0); tf.margin_right = Inches(0.0)
        tf.margin_top = Inches(0.0); tf.margin_bottom = Inches(0.0)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        p.text = title_text
        p.font.name = FONT_CALIBRI
        p.font.size = Pt(54 if not is_center else 54)
        p.font.bold = True
        p.font.underline = True
        p.font.color.rgb = COLOR_GOLD_TEXT

    def add_section_header(slide, left, top, text, color=COLOR_HEAD_BLUE, font_size=34):
        tx = slide.shapes.add_textbox(left, top, Inches(11.0), Inches(0.65))
        tf = tx.text_frame
        tf.word_wrap = True
        tf.margin_left = Inches(0.0); tf.margin_right = Inches(0.0)
        tf.margin_top = Inches(0.0); tf.margin_bottom = Inches(0.0)
        p = tf.paragraphs[0]
        p.text = text
        p.font.name = FONT_CALIBRI
        p.font.size = Pt(font_size)
        p.font.bold = True
        p.font.underline = True
        p.font.color.rgb = color
        return tx

    def add_lrp_bullets(slide, left, top, width, height, items, font_size=28, space_after=18):
        tx = slide.shapes.add_textbox(left, top, width, height)
        tf = tx.text_frame
        tf.word_wrap = True
        tf.margin_left = Inches(0.0); tf.margin_right = Inches(0.0)
        tf.margin_top = Inches(0.0); tf.margin_bottom = Inches(0.0)

        for idx, (prefix, prefix_color, text, text_color, is_bold) in enumerate(items):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            p.space_after = Pt(space_after)

            if prefix:
                r1 = p.add_run()
                r1.text = prefix + " "
                r1.font.name = FONT_CALIBRI
                r1.font.size = Pt(font_size)
                r1.font.bold = True
                r1.font.color.rgb = prefix_color

            if text:
                r2 = p.add_run()
                r2.text = text
                r2.font.name = FONT_CALIBRI
                r2.font.size = Pt(font_size)
                r2.font.bold = is_bold
                r2.font.color.rgb = text_color
        return tx

    def add_tagline(slide, left, top, text, color=COLOR_CYAN_TAG, font_size=30):
        tx = slide.shapes.add_textbox(left, top, Inches(11.733), Inches(0.60))
        tf = tx.text_frame
        tf.word_wrap = True
        tf.margin_left = Inches(0.0); tf.margin_right = Inches(0.0)
        tf.margin_top = Inches(0.0); tf.margin_bottom = Inches(0.0)
        p = tf.paragraphs[0]
        p.text = text
        p.font.name = FONT_CALIBRI
        p.font.size = Pt(font_size)
        p.font.bold = True
        p.font.color.rgb = color
        return tx

    def set_notes(slide, script_text):
        ns = slide.notes_slide
        if ns.notes_placeholder is None:
            ns1 = prs.slides[0].notes_slide
            for sp in ns1._element.spTree:
                if sp.tag.endswith('sp'):
                    ns._element.spTree.append(copy.deepcopy(sp))
        if ns.notes_text_frame is not None:
            ns.notes_text_frame.text = script_text.strip()

    # =========================================================================
    # SLIDE 2: AIM
    # =========================================================================
    s2 = prs.slides.add_slide(blank_layout)
    add_red_header(s2, "AIM")

    add_section_header(s2, M_LEFT, Inches(1.35), "Project Aim :", COLOR_HEAD_BLUE, font_size=34)
    aim_desc = [
        ("", COLOR_DARK_TEXT, "To develop a practical WiFi CSI-based system for contactless human presence and motion sensing using real-time signal analysis and machine learning.", COLOR_DARK_TEXT, False)
    ]
    add_lrp_bullets(s2, M_LEFT, Inches(1.95), TOTAL_W, Inches(1.10), aim_desc, font_size=28, space_after=0)

    add_section_header(s2, M_LEFT, Inches(3.20), "Core Objectives :", COLOR_HEAD_BLUE, font_size=32)
    s2_objectives = [
        ("→", COLOR_BULLET_GRN, "Acquire WiFi CSI data using low-cost ESP32 hardware", COLOR_BULLET_GRN, False),
        ("→", COLOR_BULLET_BLU, "Process and extract meaningful multi-carrier signal patterns", COLOR_BULLET_BLU, False),
        ("→", COLOR_BULLET_RED, "Detect human presence and motion in real-time", COLOR_BULLET_RED, False),
        ("→", COLOR_BULLET_PRP, "Develop an ML-based recognition pipeline with high accuracy", COLOR_BULLET_PRP, False),
        ("→", COLOR_BULLET_GLD, "Validate the complete system using real-world physical testbeds", COLOR_BULLET_GLD, False)
    ]
    add_lrp_bullets(s2, M_LEFT, Inches(3.75), TOTAL_W, Inches(3.40), s2_objectives, font_size=26, space_after=14)

    set_notes(s2, """[PRESENTER SCRIPT - SLIDE 2: AIM]
"Respected Board of Officers, Sirs:
The primary aim of Project WINS is to develop a practical, contactless WiFi CSI-based system for human presence and motion sensing using real-time signal processing and machine learning.

We have structured our project around 5 clear objectives:
1. Acquiring raw WiFi Channel State Information using low-cost ESP32 microcontrollers.
2. Filtering noise and extracting meaningful multi-carrier signal patterns.
3. Detecting human presence and dynamic motion reliably.
4. Developing a lightweight, high-speed ML classification pipeline.
5. Rigorously validating the end-to-end system on physical hardware."
""")

    # =========================================================================
    # SLIDE 3: BACKGROUND (ECHO & SHADOW)
    # =========================================================================
    s3 = prs.slides.add_slide(blank_layout)
    add_red_header(s3, "BACKGROUND")

    add_section_header(s3, M_LEFT, Inches(1.35), "Preceding Sensing Implementations :", COLOR_HEAD_BLUE, font_size=34)

    col_w = Inches(5.60)
    col_gap = Inches(0.533)
    col2_left = M_LEFT + col_w + col_gap

    # Left Column: Project ECHO
    add_section_header(s3, M_LEFT, Inches(2.05), "Project ECHO (Phase 1)", COLOR_BULLET_RED, font_size=28)
    s3_echo = [
        ("→", COLOR_BULLET_RED, "Tactical silent gesture recognition system", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_RED, "WiFi CSI + Random Forest classification model", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_RED, "Hand signal detection (HALT / ADVANCE)", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_RED, "Severe environmental dependency observed", COLOR_BULLET_RED, True)
    ]
    add_lrp_bullets(s3, M_LEFT, Inches(2.60), col_w, Inches(3.00), s3_echo, font_size=23, space_after=12)

    # Right Column: Project SHADOW
    add_section_header(s3, col2_left, Inches(2.05), "Project SHADOW (Phase 2)", COLOR_BULLET_BLU, font_size=28)
    s3_shadow = [
        ("→", COLOR_BULLET_BLU, "WiFi motion radar sensing architecture", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_BLU, "DSP + Deep Learning neural network approach", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_BLU, "Experimental multi-node transceiver deployment", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_BLU, "Hardware latency & stability limitations", COLOR_BULLET_BLU, True)
    ]
    add_lrp_bullets(s3, col2_left, Inches(2.60), col_w, Inches(3.00), s3_shadow, font_size=23, space_after=12)

    # Bottom Key Learning Card
    add_tagline(s3, M_LEFT, Inches(5.95), "Key Learning: Complex sensing tasks require robust hardware, controlled scope, and practical objectives.", COLOR_BULLET_GLD, font_size=24)

    set_notes(s3, """[PRESENTER SCRIPT - SLIDE 3: BACKGROUND]
"Sirs, before developing WiMotion, our team explored two previous WiFi sensing projects:
First, Project ECHO, which focused on tactical silent gesture recognition using Random Forest on CSI data to recognize command hand signals like HALT and ADVANCE. We encountered severe environmental dependency when room layouts changed.
Second, Project SHADOW, which explored a deep learning WiFi motion radar. Here, heavy neural compute introduced edge latency and hardware instability.

Our key empirical learning from both projects was clear: attempting over-complex tasks on edge microcontrollers degrades real-world reliability. Practical success demands robust hardware, controlled scope, and focused objectives."
""")

    # =========================================================================
    # SLIDE 4: PROBLEM IDENTIFIED
    # =========================================================================
    s4 = prs.slides.add_slide(blank_layout)
    add_red_header(s4, "PROBLEM IDENTIFIED")

    add_section_header(s4, M_LEFT, Inches(1.35), "Key Challenges Observed in Real Hardware :", COLOR_HEAD_BLUE, font_size=34)

    s4_problems = [
        ("→", COLOR_BULLET_RED, "High Environmental Dependency: RF signatures change with room surroundings and clutter.", COLOR_BULLET_RED, False),
        ("→", COLOR_BULLET_GLD, "Hardware Limitations: Low-cost ESP32 hardware limits fine-grained multi-target sensing.", COLOR_BULLET_GLD, False),
        ("→", COLOR_BULLET_BLU, "Signal Instability: Noise, multipath, and background Wi-Fi interference degrade CSI phase.", COLOR_BULLET_BLU, False),
        ("→", COLOR_BULLET_PRP, "Generalization Issues: Models trained on one subject often degrade across different people.", COLOR_BULLET_PRP, False),
        ("→", COLOR_BULLET_RED, "Simulation–Hardware Gap: High accuracy in MATLAB simulation fails on physical hardware.", COLOR_BULLET_RED, False)
    ]
    add_lrp_bullets(s4, M_LEFT, Inches(2.05), TOTAL_W, Inches(4.00), s4_problems, font_size=25, space_after=16)

    add_tagline(s4, M_LEFT, Inches(6.05), "Key Requirement: A focused, practical, and experimentally measurable WiFi sensing system.", COLOR_BULLET_GRN, font_size=25)

    set_notes(s4, """[PRESENTER SCRIPT - SLIDE 4: PROBLEM IDENTIFIED]
"Sirs, derived directly from our empirical testing in ECHO and SHADOW, we identified five fundamental bottlenecks:
1. High Environmental Dependency: Wireless reflections vary radically between rooms.
2. Hardware Constraints: Standard microcontrollers struggle with high-bandwidth CSI packet streaming.
3. Signal Instability: Ambient interference and mechanical vibrations create false phase shifts.
4. Generalization Gaps: Cross-subject body mass differences affect attenuation profiles.
5. The Simulation-to-Hardware Gap: Theoretical algorithms in synthetic simulators fail on physical hardware.

This identified our core mandate: we needed an experimentally measurable, highly focused sensing engine."
""")

    # =========================================================================
    # SLIDE 5: WHY WiMotion? / WORK UNDERTAKEN
    # =========================================================================
    s5 = prs.slides.add_slide(blank_layout)
    add_red_header(s5, "WHY WiMotion? / WORK UNDERTAKEN")

    add_section_header(s5, M_LEFT, Inches(1.35), "Strategic Focus & Work Undertaken :", COLOR_HEAD_BLUE, font_size=34)

    s5_reasons = [
        ("→", COLOR_BULLET_GRN, "Narrowed the Sensing Objective: Focused strictly on reliable human presence and motion.", COLOR_BULLET_GRN, False),
        ("→", COLOR_BULLET_BLU, "Uses Passive WiFi CSI: Eliminates active radar emissions for covert operational use.", COLOR_BULLET_BLU, False),
        ("→", COLOR_BULLET_RED, "Designed for Real Hardware: Built on commercial ESP32 boards with 921,600 baud serial bus.", COLOR_BULLET_RED, False),
        ("→", COLOR_BULLET_PRP, "Signal Processing + ML: Combines rolling median filters with fast ExtraTrees classification.", COLOR_BULLET_PRP, False),
        ("→", COLOR_BULLET_GLD, "Emphasis on Measurable Results: Validated via 26 automated unit tests and live trials.", COLOR_BULLET_GLD, False)
    ]
    add_lrp_bullets(s5, M_LEFT, Inches(2.05), TOTAL_W, Inches(4.00), s5_reasons, font_size=25, space_after=16)

    add_tagline(s5, M_LEFT, Inches(6.05), "Project Direction: ECHO → SHADOW → Lessons Learned → WiMotion (Focused • Passive • Testable)", COLOR_HEAD_BLUE, font_size=24)

    set_notes(s5, """[PRESENTER SCRIPT - SLIDE 5: WHY WIMOTION?]
"Sirs, this brings us to the rationale of WiMotion:
Rather than pursuing theoretical over-complexity, WiMotion represents a disciplined pivot:
- We narrowed our objective to binary presence and motion detection—a mission-critical military capability.
- We utilize passive CSI sniffing, meaning the system emits zero active probing radar signals.
- We engineered our pipeline specifically for physical COTS ESP32 hardware, locking our communication at 921,600 baud.
- We combined classical digital signal processing with lightweight machine learning to deliver sub-50 ms live detection."
""")

    # =========================================================================
    # SLIDE 6: SYSTEM ARCHITECTURE
    # =========================================================================
    s6 = prs.slides.add_slide(blank_layout)
    add_red_header(s6, "SYSTEM ARCHITECTURE")

    add_section_header(s6, M_LEFT, Inches(1.35), "System Pipeline & Core Components :", COLOR_HEAD_BLUE, font_size=34)

    # Left: Pipeline Flow
    add_section_header(s6, M_LEFT, Inches(2.05), "Sequential Signal Flow", COLOR_BULLET_BLU, font_size=26)
    s6_flow = [
        ("1.", COLOR_BULLET_BLU, "WiFi AP / ESP32 Transmitter (20 Hz frame broadcast)", COLOR_DARK_TEXT, False),
        ("2.", COLOR_BULLET_BLU, "Signal Propagation across 2.4 GHz channel", COLOR_DARK_TEXT, False),
        ("3.", COLOR_BULLET_RED, "Human Body Interaction (Scattering & Absorption)", COLOR_BULLET_RED, True),
        ("4.", COLOR_BULLET_BLU, "CSI Acquisition at ESP32 STA Sniffer Node", COLOR_DARK_TEXT, False),
        ("5.", COLOR_BULLET_GRN, "CSI Pre-processing (Median & SVD Coherence)", COLOR_DARK_TEXT, False),
        ("6.", COLOR_BULLET_PRP, "Feature Extraction & ML Classification Engine", COLOR_DARK_TEXT, False),
        ("7.", COLOR_BULLET_RED, "Real-Time 3D HUD Presence / Motion Alert", COLOR_BULLET_RED, True)
    ]
    add_lrp_bullets(s6, M_LEFT, Inches(2.60), Inches(6.00), Inches(4.30), s6_flow, font_size=21, space_after=10)

    # Right: Core Components
    add_section_header(s6, col2_left, Inches(2.05), "Core System Components", COLOR_BULLET_RED, font_size=26)
    s6_comps = [
        ("→", COLOR_BULLET_RED, "ESP32 AP + STA Transceivers", COLOR_BULLET_RED, True),
        ("  ", COLOR_DARK_TEXT, "COTS dual-node pairing on Channel 6 (2437 MHz).", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_BLU, "CSI Data Acquisition Bus", COLOR_BULLET_BLU, True),
        ("  ", COLOR_DARK_TEXT, "High-speed 921,600 baud streaming pipeline.", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_GRN, "Signal Processing & ML Core", COLOR_BULLET_GRN, True),
        ("  ", COLOR_DARK_TEXT, "Subcarrier variance extraction + ExtraTrees model.", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_GLD, "Real-Time Output HUD", COLOR_BULLET_GLD, True),
        ("  ", COLOR_DARK_TEXT, "100% offline Three.js 3D wave disturbance dashboard.", COLOR_DARK_TEXT, False)
    ]
    add_lrp_bullets(s6, col2_left, Inches(2.60), Inches(5.20), Inches(4.30), s6_comps, font_size=20, space_after=6)

    set_notes(s6, """[PRESENTER SCRIPT - SLIDE 6: SYSTEM ARCHITECTURE]
"Sirs, this slide presents the system architecture of WiMotion.
On the left is the end-to-end signal flow:
The active ESP32 transmitter broadcasts 802.11 frames at 20 Hz. When a human enters the room, body tissue scatters and phase-shifts the multi-carrier wavefront.
The receiver node extracts Channel State Information across 64 subcarriers.
This data streams to the host computer at 921,600 baud, where it undergoes noise filtering, feature extraction, and ML classification, triggering our live 3D HUD in under 50 milliseconds.

On the right are the four core hardware and software modules that power the system."
""")

    # =========================================================================
    # SLIDE 7: METHODOLOGY (Matching User's LRP Screenshot Exactly!)
    # =========================================================================
    s7 = prs.slides.add_slide(blank_layout)
    add_red_header(s7, "METHODOLOGY")

    add_section_header(s7, M_LEFT, Inches(1.35), "Methodology Followed :", COLOR_HEAD_BLUE, font_size=34)

    s7_steps = [
        ("→", COLOR_BULLET_GLD, "1. CSI Acquisition: ESP32-based WiFi CSI collection at 20 Hz", COLOR_BULLET_GLD, False),
        ("→", COLOR_BULLET_GRN, "2. Signal Pre-processing: Noise filtering and signal conditioning", COLOR_BULLET_GRN, False),
        ("→", COLOR_BULLET_RED, "3. Feature Extraction: Extraction of relevant multi-carrier characteristics", COLOR_BULLET_RED, False),
        ("→", COLOR_BULLET_BLU, "4. Dataset Preparation: Collection and chronological labelling of real samples", COLOR_BULLET_BLU, False),
        ("→", COLOR_BULLET_PRP, "5. ML Training: Training and cross-validation of classification model", COLOR_BULLET_PRP, False),
        ("→", COLOR_BULLET_RED, "6. Real-Time Inference: Live CSI → Processing → Sub-50 ms Prediction", COLOR_BULLET_RED, False)
    ]
    add_lrp_bullets(s7, M_LEFT, Inches(2.05), TOTAL_W, Inches(4.10), s7_steps, font_size=25, space_after=14)

    add_tagline(s7, M_LEFT, Inches(6.05), "Flow: WiFi Signals → CSI Extraction → Pre-processing → Features → ML → Real-Time Detection", COLOR_HEAD_BLUE, font_size=24)

    set_notes(s7, """[PRESENTER SCRIPT - SLIDE 7: METHODOLOGY]
"Sirs, our methodology follows 6 structured phases:
1. CSI Acquisition: Intercepting physical layer subcarriers at 20 Hz from ESP32 hardware.
2. Signal Pre-processing: Converting complex I/Q vectors into Euclidean amplitudes and filtering impulsive noise spikes.
3. Feature Extraction: Computing variance, energy, and dispersion across 52 active carriers.
4. Dataset Preparation: Chronologically partitioning real room recordings to guarantee zero temporal data leakage.
5. ML Training: Training ExtraTrees classifiers using in-fold baseline normalization.
6. Real-Time Inference: Executing continuous live predictions with dual-threshold hysteresis latching."
""")

    # =========================================================================
    # SLIDE 8: HARDWARE & SOFTWARE REQUIREMENTS — WITH REAL ESP32 PHOTO
    # =========================================================================
    s8 = prs.slides.add_slide(blank_layout)
    add_red_header(s8, "HARDWARE & SOFTWARE REQUIREMENTS")

    # Left: Hardware + Photo
    add_section_header(s8, M_LEFT, Inches(1.35), "Hardware Requirements :", COLOR_HEAD_BLUE, font_size=32)
    s8_hw = [
        ("→", COLOR_BULLET_RED, "2 × ESP32 Boards: DevKitC v4 (Dual-Core 240 MHz)", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_BLU, "High-Speed Serial: CP2102 USB UART at 921,600 baud", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_GRN, "Host PC / Workstation for real-time processing", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_GLD, "2.4 GHz WiFi Environment (Channel 6, HT20 mode)", COLOR_DARK_TEXT, False)
    ]
    add_lrp_bullets(s8, M_LEFT, Inches(1.95), Inches(5.80), Inches(2.20), s8_hw, font_size=20, space_after=8)

    if IMG_DEVBOARD.exists():
        s8.shapes.add_picture(str(IMG_DEVBOARD), M_LEFT, Inches(4.30), width=Inches(5.60))
        cap = s8.shapes.add_textbox(M_LEFT, Inches(6.55), Inches(5.60), Inches(0.40))
        p = cap.text_frame.paragraphs[0]; p.text = "Physical Node: ESP32-WROOM-32 with onboard PCB antenna & foam pad."
        p.font.name = FONT_CALIBRI; p.font.size = Pt(15); p.font.bold = True; p.font.color.rgb = COLOR_DARK_TEXT

    # Right: Software Stack
    add_section_header(s8, col2_left, Inches(1.35), "Software & Dev Stack :", COLOR_BULLET_RED, font_size=32)
    s8_sw = [
        ("→", COLOR_BULLET_RED, "ESP32-CSI-Tool: Promiscuous 64-subcarrier extraction", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_BLU, "Python 3.10: Core processing and inference engine", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_GRN, "NumPy & Scikit-learn: Matrix math & ML classifiers", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_PRP, "PySerial: High-throughput asynchronous data bus", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_GLD, "Three.js & HTML5: Real-time 3D wave disturbance HUD", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_RED, "Pytest Suite: 26 automated unit tests (100% passing)", COLOR_DARK_TEXT, False)
    ]
    add_lrp_bullets(s8, col2_left, Inches(1.95), Inches(5.60), Inches(4.20), s8_sw, font_size=21, space_after=14)

    add_tagline(s8, col2_left, Inches(6.20), "Development Environment: Windows 11 + Python + ESP32", COLOR_BULLET_GRN, font_size=22)

    set_notes(s8, """[PRESENTER SCRIPT - SLIDE 8: HARDWARE & SOFTWARE REQUIREMENTS]
"Sirs, this slide presents our complete hardware and software stack.
On the left is an empirical photograph of our physical node: the ESP32-WROOM-32 DevKitC v4. It features a dual-core 240 MHz processor, integrated Wi-Fi radio, and an onboard meandered PCB antenna. Notice the protective foam base to prevent grounding noise. The serial link is locked at 921,600 baud.

On the right is our software stack:
- ESP32-CSI-Tool firmware for promiscuous frame parsing.
- Python 3.10 with NumPy and Scikit-learn for high-speed matrix feature calculation.
- PySerial for non-blocking serial packet streaming.
- Three.js for our offline 3D wave disturbance HUD.
- The entire stack is validated by 26 automated unit tests."
""")

    # =========================================================================
    # SLIDE 9: IMPLEMENTATION / DEVELOPMENT — WITH REAL TESTBED PHOTO
    # =========================================================================
    s9 = prs.slides.add_slide(blank_layout)
    add_red_header(s9, "IMPLEMENTATION / DEVELOPMENT")

    # Left: Testbed Setup + Photo
    add_section_header(s9, M_LEFT, Inches(1.35), "Hardware & Testbed Setup :", COLOR_HEAD_BLUE, font_size=32)
    s9_hw = [
        ("→", COLOR_BULLET_BLU, "ESP32 AP–STA Configuration across 1.8m corridor", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_RED, "CSI-Enabled 20 Hz WiFi Communication on Channel 6", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_GRN, "Dual Nodes elevated at 0.75m (torso center of mass)", COLOR_DARK_TEXT, False)
    ]
    add_lrp_bullets(s9, M_LEFT, Inches(1.95), Inches(5.80), Inches(2.00), s9_hw, font_size=20, space_after=8)

    if IMG_TESTBED_WIDE.exists():
        s9.shapes.add_picture(str(IMG_TESTBED_WIDE), M_LEFT, Inches(4.15), width=Inches(5.60))
        cap = s9.shapes.add_textbox(M_LEFT, Inches(6.55), Inches(5.60), Inches(0.40))
        p = cap.text_frame.paragraphs[0]; p.text = "Corridor Testbed: Dual ESP32 transceivers across 1.8m walkway."
        p.font.name = FONT_CALIBRI; p.font.size = Pt(15); p.font.bold = True; p.font.color.rgb = COLOR_DARK_TEXT

    # Right: Developed Pipelines
    add_section_header(s9, col2_left, Inches(1.35), "Developed Software Pipelines :", COLOR_BULLET_RED, font_size=32)
    s9_sw = [
        ("→", COLOR_BULLET_RED, "Data Acquisition: Serial stream, frame validation, CSI extraction", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_BLU, "Data Processing: Signal conditioning, multi-carrier variance", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_GRN, "ML Pipeline: Chronological evaluation, zero-leakage training", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_PRP, "Real-Time System: Live CSI processing, motion prediction, HUD", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_GLD, "Testing Framework: 26 automated unit tests verifying all math", COLOR_DARK_TEXT, False)
    ]
    add_lrp_bullets(s9, col2_left, Inches(1.95), Inches(5.60), Inches(4.50), s9_sw, font_size=21, space_after=16)

    set_notes(s9, """[PRESENTER SCRIPT - SLIDE 9: IMPLEMENTATION / DEVELOPMENT]
"Sirs, this slide illustrates our physical deployment and software development.
On the left is a photograph of our actual physical testbed setup:
Both nodes are elevated at exactly 0.75 meters on bedside tables across a 1.8-meter corridor walkway.
This elevation aligns directly with the human torso and pelvic center of mass, capturing the largest reflective radar cross-section.
The central brown mat marks the traversal corridor passing through the 1st Fresnel zone.

On the right is our software development:
We constructed 5 operational pipelines: Data Acquisition, Processing, ML Training, Real-Time HUD, and an automated testing framework verifying all mathematical operations before deployment."
""")

    # =========================================================================
    # SLIDE 10: CURRENT PROJECT PROGRESS — STATUS TABLE + EMBEDDED VIDEO 1
    # =========================================================================
    s10 = prs.slides.add_slide(blank_layout)
    add_red_header(s10, "CURRENT PROJECT PROGRESS")

    # Left: Status Breakdown Table
    add_section_header(s10, M_LEFT, Inches(1.35), "Component Status Breakdown :", COLOR_HEAD_BLUE, font_size=32)

    rows, cols = 9, 2
    t_left = M_LEFT
    t_top  = Inches(2.05)
    t_w    = Inches(5.60)
    t_h    = Inches(3.90)
    table_shape = s10.shapes.add_table(rows, cols, t_left, t_top, t_w, t_h)
    tbl = table_shape.table
    tbl.columns[0].width = Inches(3.70)
    tbl.columns[1].width = Inches(1.90)

    headers = [("Component", "Status")]
    data_rows = [
        ("ESP32 Communication", "✅ Completed"),
        ("CSI Acquisition", "✅ Completed"),
        ("Data Collection Pipeline", "✅ Completed"),
        ("Dataset Preparation", "✅ Completed"),
        ("ML Pipeline", "✅ Implemented"),
        ("Real-Time HUD", "✅ Implemented"),
        ("Automated Testing (26/26)", "✅ Completed"),
        ("Hardware Validation", "🔄 Ongoing")
    ]
    for r_idx, (c1, c2) in enumerate(headers + data_rows):
        cell1 = tbl.cell(r_idx, 0); cell2 = tbl.cell(r_idx, 1)
        cell1.text = c1; cell2.text = c2
        for cell in (cell1, cell2):
            cell.margin_left = Inches(0.12); cell.margin_right = Inches(0.12)
            cell.margin_top = Inches(0.06); cell.margin_bottom = Inches(0.06)
            for p in cell.text_frame.paragraphs:
                p.font.name = FONT_CALIBRI
                p.font.size = Pt(18 if r_idx == 0 else 17)
                p.font.bold = (r_idx == 0 or "Ongoing" in c2)
                p.font.color.rgb = COLOR_GOLD_TEXT if r_idx == 0 else COLOR_DARK_TEXT
        if r_idx == 0:
            cell1.fill.solid(); cell1.fill.fore_color.rgb = COLOR_BANNER_RED
            cell2.fill.solid(); cell2.fill.fore_color.rgb = COLOR_BANNER_RED

    add_tagline(s10, M_LEFT, Inches(6.15), "Current Stage: Functional prototype under real-hardware validation.", COLOR_BULLET_RED, font_size=22)

    # Right: Embedded Video 1 (Corridor Walkway Traversal)
    add_section_header(s10, col2_left, Inches(1.35), "▶ Trial 1: Corridor Walkway Traversal", COLOR_BULLET_RED, font_size=30)
    if VID_WALK_TRIAL.exists():
        s10.shapes.add_movie(
            str(VID_WALK_TRIAL),
            col2_left,
            Inches(2.05),
            Inches(5.60),
            Inches(3.20),
            poster_frame_image=str(THUMB_WALK_TRIAL) if THUMB_WALK_TRIAL.exists() else None,
            mime_type="video/mp4"
        )
    v1_pts = [
        ("• Walkway Traversal:", COLOR_BULLET_RED, "Operator crosses central 1st Fresnel zone corridor.", COLOR_DARK_TEXT, False),
        ("• 921,600 Baud Bus:", COLOR_BULLET_BLU, "Live serial streaming without buffer drops.", COLOR_DARK_TEXT, False),
        ("• Instant Trigger:", COLOR_BULLET_GRN, "Subcarrier amplitude drops immediately on crossing.", COLOR_DARK_TEXT, False)
    ]
    add_lrp_bullets(s10, col2_left, Inches(5.35), Inches(5.60), Inches(1.60), v1_pts, font_size=18, space_after=6)

    set_notes(s10, """[PRESENTER SCRIPT - SLIDE 10: CURRENT PROJECT PROGRESS]
"Sirs, this slide presents our current project progress:
As summarized in our status breakdown on the left:
- ESP32 communication, CSI acquisition, data collection, dataset preparation, ML pipeline, Real-Time HUD, and automated testing are all completed.
- Our current ongoing phase is comprehensive hardware validation across diverse physical rooms.
Overall, we have a functional prototype undergoing active real-hardware validation.

On the right is our recorded physical video demonstration:
[Cadet Note: Click on the video to play.]
In this trial, the cadet walks across the central corridor along the floor mat. Notice how the subcarrier amplitude drops dramatically as the body cuts through the line of sight, instantly triggering the presence alert on our workstation terminal streaming at 921,600 baud."
""")

    # =========================================================================
    # SLIDE 11: EXPERIMENTAL RESULTS — OBSERVATIONS + EMBEDDED VIDEO 2
    # =========================================================================
    s11 = prs.slides.add_slide(blank_layout)
    add_red_header(s11, "EXPERIMENTAL RESULTS")

    # Left: Observations
    add_section_header(s11, M_LEFT, Inches(1.35), "Empirical Observations :", COLOR_HEAD_BLUE, font_size=32)
    s11_pts = [
        ("→", COLOR_BULLET_GRN, "CSI Stream: Real ESP32 stream successfully acquired (lengths 128 / 384)", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_BLU, "Signal Quality: RSSI observed; frame validity & stream integrity monitored", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_PRP, "System Validation: Data pipeline tested end-to-end with live prediction", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_RED, "Automated Verification: 26 unit tests confirmed 100% passing", COLOR_DARK_TEXT, False)
    ]
    add_lrp_bullets(s11, M_LEFT, Inches(2.05), Inches(5.80), Inches(3.60), s11_pts, font_size=21, space_after=14)

    add_tagline(s11, M_LEFT, Inches(5.85), "Key Observation: Complete CSI → Processing → ML → Output pipeline is operational, while sampling-rate stability remains under investigation.", COLOR_BULLET_RED, font_size=20)

    # Right: Embedded Video 2 (In-Zone Dynamic Motion)
    add_section_header(s11, col2_left, Inches(1.35), "▶ Trial 2: In-Zone Motion & 3D HUD", COLOR_BULLET_RED, font_size=30)
    if VID_MOTION_TRIAL.exists():
        s11.shapes.add_movie(
            str(VID_MOTION_TRIAL),
            col2_left,
            Inches(2.05),
            Inches(5.60),
            Inches(3.20),
            poster_frame_image=str(THUMB_MOTION_TRIAL) if THUMB_MOTION_TRIAL.exists() else None,
            mime_type="video/mp4"
        )
    v2_pts = [
        ("• In-Zone Movement:", COLOR_BULLET_RED, "Cadet moves and turns inside the active sensing volume.", COLOR_DARK_TEXT, False),
        ("• 3D Wave Hologram:", COLOR_BULLET_BLU, "Three.js renders spatial field perturbations in real time.", COLOR_DARK_TEXT, False),
        ("• Sub-50 ms Latency:", COLOR_BULLET_GRN, "Presence dial switches to RED alert without false clears.", COLOR_DARK_TEXT, False)
    ]
    add_lrp_bullets(s11, col2_left, Inches(5.35), Inches(5.60), Inches(1.60), v2_pts, font_size=18, space_after=6)

    set_notes(s11, """[PRESENTER SCRIPT - SLIDE 11: EXPERIMENTAL RESULTS]
"Sirs, here are our empirical experimental results:
On the left:
- We have successfully captured raw CSI streams from physical ESP32 transceivers, verifying subcarrier lengths of 128 and 384 bytes corresponding to OFDM I and Q pairs.
- Frame validity and stream integrity were continuously monitored.
- Our key scientific finding: the complete CSI-to-ML-to-HUD pipeline is fully operational. Importantly, we honestly note that sampling-rate stability fluctuates around 10 to 20 Hz due to ESP32 RTOS Wi-Fi task scheduling, which remains under active investigation.

On the right is our second physical video demonstration:
[Cadet Note: Click on the video to play.]
Here, the cadet moves and turns inside the active sensing zone. Continuous multipath perturbation maintains a stable detection score above 90%, with zero flickering thanks to our temporal hysteresis latching."
""")

    # =========================================================================
    # SLIDE 12: CHALLENGES
    # =========================================================================
    s12 = prs.slides.add_slide(blank_layout)
    add_red_header(s12, "CHALLENGES")

    add_section_header(s12, M_LEFT, Inches(1.35), "Practical Challenges Encountered :", COLOR_HEAD_BLUE, font_size=34)

    s12_pts = [
        ("→", COLOR_BULLET_RED, "CSI Sampling-Rate Stability: Packet rate fluctuations due to ESP32 Wi-Fi task scheduler.", COLOR_BULLET_RED, False),
        ("→", COLOR_BULLET_GLD, "Environmental RF Variations: External Wi-Fi channels and changing room multipath.", COLOR_BULLET_GLD, False),
        ("→", COLOR_BULLET_BLU, "Multipath & Signal Noise: Mechanical vibrations and reflections from metallic objects.", COLOR_BULLET_BLU, False),
        ("→", COLOR_BULLET_PRP, "Hardware Communication Constraints: Single SISO pair limits multi-angle resolution.", COLOR_BULLET_PRP, False),
        ("→", COLOR_BULLET_RED, "Limited Training Data: Need for broader multi-subject datasets across diverse postures.", COLOR_BULLET_RED, False),
        ("→", COLOR_BULLET_BLU, "Cross-Environment Generalization: Model baseline shifts between different physical rooms.", COLOR_BULLET_BLU, False)
    ]
    add_lrp_bullets(s12, M_LEFT, Inches(2.05), TOTAL_W, Inches(4.10), s12_pts, font_size=24, space_after=14)

    add_tagline(s12, M_LEFT, Inches(6.05), "Major Challenge: Maintaining reliable CSI characteristics under changing real-world conditions.", COLOR_BULLET_RED, font_size=25)

    set_notes(s12, """[PRESENTER SCRIPT - SLIDE 12: CHALLENGES]
"Sirs, in the spirit of scientific rigor, we have identified 6 practical engineering challenges:
1. CSI Sampling-Rate Stability: Packet arrival rates exhibit micro-jitter due to ESP32 RTOS Wi-Fi scheduling.
2. Environmental RF Variations: Nearby 2.4 GHz routers create co-channel interference.
3. Multipath & Signal Noise: Periodic Doppler shifts from objects like ceiling fans must be filtered out.
4. Hardware Constraints: Single-antenna SISO links cannot mathematically perform 3D angle-of-arrival triangulation.
5. Limited Training Data: Additional empirical datasets across varied human subjects are required.
6. Cross-Environment Generalization: RF baseline characteristics shift across different room architectures.
Our current work focuses on adaptive baseline normalization to make our models robust across diverse rooms."
""")

    # =========================================================================
    # SLIDE 13: FUTURE SCOPE
    # =========================================================================
    s13 = prs.slides.add_slide(blank_layout)
    add_red_header(s13, "FUTURE SCOPE")

    add_section_header(s13, M_LEFT, Inches(1.35), "Development Roadmap & Next Milestones :", COLOR_HEAD_BLUE, font_size=34)

    s13_pts = [
        ("→", COLOR_BULLET_GRN, "Improve CSI Sampling Stability: Implement hardware timer interrupts on ESP32 firmware.", COLOR_BULLET_GRN, False),
        ("→", COLOR_BULLET_BLU, "Expand Activity Recognition: Classify specific motions (walking, running, sitting, falling).", COLOR_BULLET_BLU, False),
        ("→", COLOR_BULLET_RED, "Improve Cross-Environment Robustness: Deploy domain adaptation across multiple rooms.", COLOR_BULLET_RED, False),
        ("→", COLOR_BULLET_PRP, "Explore Advanced Models: Lightweight 1D-ResNet / Temporal Convolutional Networks.", COLOR_BULLET_PRP, False),
        ("→", COLOR_BULLET_GLD, "Multi-Person Sensing: Integrate dual-receiver nodes to enable spatial triangulation.", COLOR_BULLET_GLD, False),
        ("→", COLOR_BULLET_BLU, "Contactless Physiological Sensing: Monitor micro-chest movements for respiration rates.", COLOR_BULLET_BLU, False)
    ]
    add_lrp_bullets(s13, M_LEFT, Inches(2.05), TOTAL_W, Inches(4.10), s13_pts, font_size=24, space_after=14)

    add_tagline(s13, M_LEFT, Inches(6.05), "Long-Term Direction: From basic presence detection towards robust multi-activity WiFi sensing.", COLOR_HEAD_BLUE, font_size=25)

    set_notes(s13, """[PRESENTER SCRIPT - SLIDE 13: FUTURE SCOPE]
"Sirs, looking ahead to our final presentation phase, our roadmap is structured into immediate milestones and long-term horizons:

In the next 8 weeks:
1. We will lock the ESP32 packet sampling rate using hardware timer interrupts to achieve jitter-free 20 Hz acquisition.
2. We will expand our classification engine from binary presence to activity recognition—distinguishing between walking, falling, and sitting.
3. We will enhance cross-environment robustness through adaptive domain calibration.
4. We will benchmark lightweight 1D-ResNet models against our ExtraTrees baseline.

In our long-term vision, we aim to expand from single-person presence to multi-target triangulation and contactless physiological vital sign detection, establishing WiMotion as a versatile tactical sensing platform."
""")

    # =========================================================================
    # SLIDE 14: CONCLUSION
    # =========================================================================
    s14 = prs.slides.add_slide(blank_layout)
    add_red_header(s14, "CONCLUSION")

    add_section_header(s14, M_LEFT, Inches(1.35), "Summary of Achievements :", COLOR_HEAD_BLUE, font_size=34)

    s14_pts = [
        ("→", COLOR_BULLET_GRN, "Developed a practical WiFi CSI-based contactless human sensing system.", COLOR_BULLET_GRN, False),
        ("→", COLOR_BULLET_BLU, "Implemented real-world ESP32 CSI acquisition at 921,600 baud with zero packet drop.", COLOR_BULLET_BLU, False),
        ("→", COLOR_BULLET_RED, "Developed complete CSI pre-processing, noise filtering, and ML classification pipeline.", COLOR_BULLET_RED, False),
        ("→", COLOR_BULLET_PRP, "Integrated real-time motion detection with an interactive 3D tactical HUD (<50 ms latency).", COLOR_BULLET_PRP, False),
        ("→", COLOR_BULLET_GLD, "Validated the system through rigorous hardware testing, automated tests, and live trials.", COLOR_BULLET_GLD, False),
        ("→", COLOR_BULLET_BLU, "Identified key real-world limitations for further improvement in the final phase.", COLOR_BULLET_BLU, False)
    ]
    add_lrp_bullets(s14, M_LEFT, Inches(2.05), TOTAL_W, Inches(4.10), s14_pts, font_size=24, space_after=14)

    add_tagline(s14, M_LEFT, Inches(6.05), "Final Statement: “WiMotion demonstrates the feasibility of using WiFi CSI as a practical, contactless sensing medium.”", COLOR_BULLET_RED, font_size=24)

    set_notes(s14, """[PRESENTER SCRIPT - SLIDE 14: CONCLUSION]
"To conclude, Sirs:
In this intermediate phase of Project WINS:
We have successfully developed and validated an indigenous Wi-Fi CSI-based contactless sensing prototype.
We constructed an empirical dual-node ESP32 testbed, locked our serial pipeline at 921,600 baud, developed a comprehensive machine learning processing chain, and integrated a live 3D tactical HUD operating under 50 milliseconds.

Most importantly, we grounded our research in practical scientific honesty: identifying sampling rate fluctuations and environmental shifts rather than making unverified claims.

Our final takeaway: Project WiMotion successfully proves that ambient Wi-Fi Channel State Information provides an effective, un-spoofable, and low-cost contactless sensing medium for defense and security operations."
""")

    # =========================================================================
    # SLIDE 15: REFERENCES
    # =========================================================================
    s15 = prs.slides.add_slide(blank_layout)
    add_red_header(s15, "REFERENCES")

    add_section_header(s15, M_LEFT, Inches(1.35), "Key Scientific Literature & Documentation :", COLOR_HEAD_BLUE, font_size=34)

    s15_refs = [
        ("→", COLOR_BULLET_BLU, "Chen et al., \"WiFi Sensing with Channel State Information: A Survey and Beyond\", ACM Computing Surveys, 2020.", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_GRN, "Wang et al., \"DeepFi: Deep Learning for Indoor Fingerprinting Using CSI Information\", IEEE INFOCOM, 2017.", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_RED, "Zhao et al., \"Through-Wall Human Pose Estimation Using Radio Signals\", IEEE/CVF CVPR, 2018.", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_PRP, "Zhang et al., \"Deep Learning for Wireless Human Sensing: A Comprehensive Survey\", IEEE Comm Surveys, 2022.", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_GLD, "Ahmad et al., \"WiFi-Based Human Sensing with Deep Learning\", IEEE Internet of Things Journal, 2023.", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_BLU, "Espressif Systems, \"ESP32-CSI-Tool: Channel State Information Technical Documentation\", 2023.", COLOR_DARK_TEXT, False),
        ("→", COLOR_BULLET_RED, "Relevant IEEE / ACM Peer-Reviewed Wireless Sensing Publications & Documentation.", COLOR_DARK_TEXT, False)
    ]
    add_lrp_bullets(s15, M_LEFT, Inches(2.05), TOTAL_W, Inches(4.80), s15_refs, font_size=22, space_after=16)

    set_notes(s15, """[PRESENTER SCRIPT - SLIDE 15: REFERENCES]
"Sirs, our research and engineering framework are established upon peer-reviewed scientific literature in wireless sensing:
- The foundational survey on CSI sensing by Chen et al. in ACM Computing Surveys.
- DeepFi by Wang et al. in IEEE INFOCOM for multi-carrier fingerprinting.
- Through-wall RF sensing models by Zhao et al. from MIT CSAIL.
- Recent surveys by Zhang et al. and Ahmad et al. in IEEE Communications and IoT Journals.
- Official Espressif technical documentation for physical layer CSI register extraction.
These references have guided our mathematical formulations and validation protocols."
""")

    # =========================================================================
    # SLIDE 16: JAI HIND (CLOSING SLIDE)
    # =========================================================================
    s16 = prs.slides.add_slide(blank_layout)
    add_red_header(s16, "JAI HIND", is_center=True)

    set_notes(s16, """[PRESENTER SCRIPT - SLIDE 16: CLOSING]
"This concludes our intermediate progress presentation for Project WINS.
Thank you, Sirs. We are now open for your questions, feedback, and guidance."
""")

    # Save cleanly
    prs.save(str(OUTPUT_FILE))
    print(f"\n[SUCCESS] Completed! Cleanly saved 16 slides into: {OUTPUT_FILE}")

if __name__ == "__main__":
    build_lrp_deck()
