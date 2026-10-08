# WiMotion: The Tactical "Why This Project?" Playbook
**Audience:** Board of Officers / Evaluators at MCTE (Lt Col, Col, Brigadier)  
**Project:** WiMotion (WiFi Interferometric Neural Sensing)  
**Cadets:** OC Tanmay Mugale & OC Rishabh Singh Rathore  

---

## 1. The 20-Second Opening Killer Hook (Word-for-Word)

> *"Respected Board of Officers, Sirs:*  
> *In Close-Quarter Battle (CQB) and Counter-Terrorism room intervention, visual sensors have fatal blindspots: optical cameras are blinded by darkness and smoke, thermal cameras cannot see through solid doors, and tactical radars emit high-power RF signatures that alert the adversary.*  
> 
> *WiMotion solves this tactical gap by repurposing omnipresent, ambient 802.11 WiFi signals into a completely covert, non-line-of-sight human presence sensor. Without deploying active radar pulses or carrying expensive payloads, two sub-₹500 COTS nodes extract microsecond Channel State Information (CSI) to detect human occupancy behind visual obstructions in real time.*  
> 
> *Our prototype is validated on physical hardware, running a verified 20 Hz inference pipeline backed by 26 passing automated test suites."*

---

## 2. The Tactical Sensor Comparison Matrix (The Panel Disarmer)

When a panel member asks: *"Camera aur thermal ke zamane mein WiFi se sensing kyu karein?"*, show or recite this exact 4-tier matrix:

| Feature / Modality | Optical Camera (RGB) | Thermal Imaging (FLIR) | Military Through-Wall Radar | **WiMotion (WiFi CSI Sensing)** |
| :--- | :---: | :---: | :---: | :---: |
| **Through-Wall / Door Penetration** | ❌ **0%** (Blocked) | ❌ **0%** (Surface only) | ✅ **High** (Microwave pulses) | ✅ **Moderate** (Drywall, wood, glass) |
| **Operation in Smoke / Dust / Darkness** | ❌ **Fails completely** | ✅ **Works** (Heat signature) | ✅ **Works** | ✅ **Unaffected by visual obscurity** |
| **Covertness / Electronic Signature** | ⚠️ Needs IR LEDs at night | ✅ Passive receiver | ❌ **HIGH EMISSION** (Alerts enemy SIGINT/RWR) | ✅ **ZERO RF EMISSION** (Passive sniff or ambient WiFi) |
| **Physical Concealment / Camouflage** | ❌ Requires clear lens LOS | ❌ Requires exposed lens | ⚠️ Bulky antenna box | ✅ **Can be completely hidden** behind objects |
| **System Cost (Per Node)** | ₹3,000 – ₹15,000 | ₹1.5 Lakh – ₹10 Lakhs | ₹25 Lakhs – ₹1 Crore | **< ₹1,000 (Commodity ESP32)** |
| **SWaP-C (Size, Weight, Power)** | High processing draw | Bulky cooling / battery | Heavy backpack unit | **< 100g, 5V USB power (18h+ runtime)** |
| **Operational Role** | Primary Visual Recon | Thermal Heat Profiling | Heavy Breaching Radar | **Complementary Covert Tripwire / Occupancy** |

---

## 3. The 3 Golden Tactical Scenarios (Where WiMotion Truly Wins)

Explain WiMotion using these three practical, non-exaggerated scenarios:

### Scenario A: Urban CQB & Room Intervention (Covert Pre-Entry Recon)
- **Problem:** Before a dynamic room entry, troops do not know if the room is occupied or empty. Peeking around the door exposes the point-man to direct fatal fire.
- **WiMotion Role:** A forward scout places/throws an ultra-lightweight node near the entryway. The ambient WiFi router inside or across the corridor provides the RF illumination. 
- **Outcome:** The team receives a real-time binary indicator: `SENSING ZONE CLEAR` vs `HUMAN PRESENT` without exposing a human life or sticking a camera under the door.

### Scenario B: Covert Electronic Reconnaissance (Zero Counter-Surveillance Signature)
- **Problem:** Military radars (like UWB through-wall radars) blast active pulses that light up on hostile electronic surveillance receivers, giving away troop positions.
- **WiMotion Role:** WiMotion uses standard 802.11 OFDM packets on Channel 6. To any adversary monitoring the spectrum, it looks like ordinary, innocent home/office WiFi router traffic. It emits **zero anomalous radar signatures**.

### Scenario C: Blindspot & Smoke-Filled Casualty Search
- **Problem:** In post-blast or smoke-compromised indoor environments, optical thermal reflection off particulates degrades camera feeds.
- **WiMotion Role:** 2.4 GHz radio waves ($\lambda \approx 12.5\text{ cm}$) have a wavelength vastly larger than smoke/dust particles, penetrating the aerosol cloud without scattering attenuation.

---

## 4. The 5 Tough Panel Questions & Model Answers

### Q1: "Is this meant to replace thermal cameras and optical sensors?"
> **Cadet Answer:**  
> *"No, Sir. WiMotion is designed strictly as a **complementary sensing layer**. Thermal and optical sensors provide high-resolution visual confirmation when Line-of-Sight exists. WiMotion steps in when Line-of-Sight is denied—behind doors, in heavy smoke, or when operational security prohibits emitting active radar pulses. It is a tactical tripwire, not a camera replacement."*

### Q2: "Why ESP32 instead of commercial SDR (Software Defined Radio)?"
> **Cadet Answer:**  
> *"Sir, military SDRs like USRP or HackRF cost upwards of ₹1.5 to ₹4 Lakhs, consume significant power, and require laptop-grade processing on-site.  
> Our primary engineering objective was to evaluate whether low-cost, expendable Commercial Off-The-Shelf (COTS) hardware could extract actionable Channel State Information at the tactical edge. At under ₹500 per node, these sensors are disposable tactical assets."*

### Q3: "What is your real accuracy? Can you deploy this tomorrow across any building?"
> **Cadet Answer:**  
> *"Sir, we want to be completely honest about our engineering boundaries. On our session-grouped validation dataset, our model achieves approximately **70.6% accuracy (71.9% F1-score)**.  
> In our controlled live hardware trials, the system successfully transitioned between empty room, dynamic crossing, and stationary occupancy without false clears.  
> However, WiFi CSI is inherently subject to multipath variations across different room layouts. Cross-environment generalization remains an ongoing research challenge across the entire scientific community, which is why we position this as an evaluated functional prototype rather than a universal turn-key surveillance product."*

### Q4: "How does it detect a person if they are standing completely still?"
> **Cadet Answer:**  
> *"Sir, when a person walks, dynamic multipath dispersion elevates the presence probability to ~89%. When a subject stands stationary, macroscopic movement ceases.  
> However, the human body consists of ~70% water, which creates measurable electromagnetic shadowing. In our physical trial, we observed an average ~6.3 dB attenuation in link power alongside slight quiescent channel perturbation, allowing our temporal decision filter to maintain the presence state across a 25-second stationary duration with zero false clearance alarms."*

### Q5: "What did you actually build versus what was already open source?"
> **Cadet Answer:**  
> *"Sir, we engineered the entire end-to-end operational pipeline:  
> 1. Firmware configuration to stream 64 OFDM subcarrier CSI frames over a high-speed 921,600 baud serial interface.  
> 2. The signal processing layer, including sliding-window median filters, subcarrier amplitude extraction, and an active Signal Quality Gate that blocks invalid inference if stream rates drop below 4 Hz.  
> 3. Feature engineering and machine learning model training evaluated under rigorous group-k-fold cross-validation.  
> 4. The real-time WebSocket and 3D Observatory dashboard.  
> 5. A 26-test automated verification suite that validates end-to-end software and data integrity."*
