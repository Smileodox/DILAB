"""Knowledge Base pipeline step."""
from __future__ import annotations
import json
import os

import chromadb

from src.config import CHROMA_PERSIST_DIR, MAX_RAG_CHUNKS
from src.llm import embed
from src.models.kb import Source, Chunk, SourceType, ContentOrigin
from src.models.common import KBPool, stable_id
from src.sources import fetch_arxiv, fetch_webpage, extract_arxiv_id


SOURCE_REGISTRY = [
    # ── KB-Product: R&S Spectrum Monitoring Products ──
    {
        "title": "R&S ESMD Wideband Monitoring Receiver",
        "url": "https://www.rohde-schwarz.com/us/product/esmd-productstartpage_63493-9558.html",
        "type": SourceType.PRODUCT_PAGE,
        "pool": KBPool.PRODUCT,
        "section": "Product Overview",
        "fetch_selectors": [".product-detail", ".product-description", "article"],
        "fallback": """The R&S ESMD wideband monitoring receiver was especially designed for signal search, radiomonitoring, radio detection and spectrum monitoring. It performs ITU-compliant measurements and meets public safety and security requirements.

Frequency Range: 20 MHz to 26.5 GHz, with 20 MHz real-time bandwidth. Available with or without a front panel display.

RF Performance: The R&S ESMD makes an excellent trade-off between linearity and sensitivity and can reliably detect weak signals among strong unwanted ones in crowded spectra.

Filtering: Preselection filtering including filter banks and tunable bandpass filters over the entire frequency range protect against intermodulation from strong out-of-band signals.

ITU Compliance: R&S ESMD performance is in line with all relevant ITU-R recommendations. The optional R&S ESMD-IM option allows for ITU-compliant measurements of signal parameters such as bandwidth, center frequency and modulation depth.

Deployment: The receiver is ideal for both stationary and mobile/vehicular applications because it can be operated locally from the front panel or remotely controlled via LAN.

GNSS: Integrated GNSS module including GPS, Glonass, BeiDou for positioning and accurate timestamps, e.g. for TDOA.

Rack Mount: Suitable for fixed installation on standard 19-inch racks.

Applications: Networking of civil regulatory authorities radiomonitoring nodes, e.g. with R&S ARGUS 6.1 and suitable options, with automatic identification of deviations between actual and predefined spectral values. Easy detection of pulsed, frequency agile and sporadic interferers, plus audio monitoring of occupied channels to test audio transmission quality.""",
    },
    {
        "title": "R&S ESMW Ultra Wideband Monitoring Receiver",
        "url": "https://www.rohde-schwarz.com/us/products/aerospace-defense-security/desktop-and-rackmount-single-channel/rs-esmw-ultra-wideband-monitoring-receiver_63493-1241024.html",
        "type": SourceType.PRODUCT_PAGE,
        "pool": KBPool.PRODUCT,
        "section": "Product Overview",
        "fetch_selectors": [".product-detail", ".product-description", "article"],
        "fallback": """The R&S ESMW is an ultra wideband monitoring receiver designed as the next generation solution for spectrum monitoring and direction finding.

Frequency Range: 8 kHz to 40 GHz for monitoring and TDOA, extendable to 53 GHz with R&S CS-MC53 option.

Direction Finding: Angle-of-arrival (AoA) direction finding from 300 kHz to 8.5 GHz.

Real-Time Bandwidth: Up to 2 GHz instantaneous bandwidth for real-time signal capture. 500 MHz real-time bandwidth as base option, extendable to 2 GHz via software upgrade.

Dynamic Range: Outstanding dynamic range designed for challenging spectrum environments with high signal density.

Filtering Architecture: Switched suboctave filterbanks and tunable bandpass filters to mitigate harmonics and intermodulation from out-of-band signals.

Attenuation Control: Automatic attenuation adjustment up to 40 dB in 1 dB increments for optimal sensitivity-linearity tradeoff.

Scan Performance: Panorama scan speeds reaching 2.6 THz/s across the entire frequency range.

Signal Detection: Minimum signal duration of 75 nanoseconds achieves 100% probability of intercept (POI).

I/Q Data Streaming: Wideband I/Q output up to 2 GHz via 100GE interface; also supports 10GE connectivity.

Digital Downconversion: Four additional digital downconverters available within real-time bandwidth window.

Direction Finding: Supports wideband DF with up to 125 MHz real-time bandwidth. Includes angle-of-arrival error correction and TDOA functionality with internal GNSS module for precise localization.

ITU Compliance: ITU-compliant RF performance verified against ITU Handbook of Spectrum Monitoring. Bandwidth measurements align with ITU-R SM.328-11 and SM.443-4 recommendations.""",
    },
    {
        "title": "R&S UMS300 Compact Monitoring and Location System",
        "url": "https://www.rohde-schwarz.com/us/products/aerospace-defense-security/outdoor/rs-ums300-compact-monitoring-and-location-system_63493-56146.html",
        "type": SourceType.PRODUCT_PAGE,
        "pool": KBPool.PRODUCT,
        "section": "Product Overview",
        "fetch_selectors": [".product-detail", ".product-description", "article"],
        "fallback": """The R&S UMS300 universal monitoring system is the quick and reliable core of monitoring installations. It is a compact monitoring and radiolocation system.

Frequency Range: 20 MHz to 3.6 GHz with 20 MHz real-time bandwidth.

Antenna Support: Antenna coverage spans 1.3 GHz to 8.2 GHz with vertical polarization, suitable for installation on a vehicle roof, tripod or mast, with passive antenna elements.

Power: External mains adapter; input 100 to 240 VAC, output 24 VDC, max 320 W.

Housing: Compact, weatherproof housing that can be mounted directly on masts near antennas for high system sensitivity and the precise location of even weak signals and expansion of the detection range.

Deployment: Used in fixed stations, mobile stations mounted on pickup trucks for off-road operations, and transportable configurations. Can be operated standalone or networked with other stations.

Networking: Remote control systems enable centralized management of multiple monitoring stations. Systems can form regionwide or nationwide monitoring networks.

Real-World Deployment (Kenya): Rohde & Schwarz implemented remote control systems and maintenance services for three existing monitoring centers, installed a fixed V/UHF monitoring station and mobile monitoring stations mounted on pickup trucks for off-road operations. The system monitors the electromagnetic spectrum and locates suspect signal sources to ensure undisturbed reception of radio and TV broadcasts and wireless communications.""",
    },
    {
        "title": "R&S Regulatory Spectrum Monitoring Solutions Overview",
        "url": "https://www.rohde-schwarz.com/us/solutions/critical-infrastructure/spectrum-monitoring/regulatory-spectrum-monitoring/regulatory-spectrum-monitoring-overview_256290.html",
        "type": SourceType.PRODUCT_PAGE,
        "pool": KBPool.PRODUCT,
        "section": "Solution Architecture",
        "fetch_selectors": [".solution-content", ".content-area", "article", "main"],
        "fallback": """Rohde & Schwarz provides regulatory authorities with solutions for enforcing spectrum compliance and ensuring fair and workable competition along with efficient, interference-free usage of the frequency spectrum.

Objectives: Regulatory bodies deploy these systems to plan frequency spectrum usage, verify actual spectrum deployment, and rectify problematic frequency allocation.

System Types: The modular, scalable product portfolio includes fixed monitoring stations (permanent installations), mobile monitoring stations (vehicle-mounted), transportable monitoring stations (semi-portable), portable monitoring stations (handheld/lightweight), control centers (command hubs for networked operations), and UAV monitoring equipment (airborne spectrum collection systems).

Network Capabilities: Systems function either as standalone units or interconnected networks. Networked configurations provide increased operational efficiency, resource sharing across regions, geo-location capabilities for signal emitters, and regional or nationwide coverage.

Automation: All frequency bands of interest are scanned uninterruptedly 24 hours a day, seven days a week. Many regulators perform measurements as automatic background tasks. Whenever a device is not in use, predefined measurements are automatically initiated. Device settings automatically adjust to include proper channel spacing and IF bandwidth parameters per ITU compliance standards.

Data Management: Results store either locally at monitoring sites or centralize in control stations. Data from all stations can be transferred to a central database enabling multi-location analysis.

Analysis Capabilities: Occupancy statistics, noise floor determination, license constraint violations, spatial resolution comparisons between locations, trend analysis over extended periods.

Real-Time Response: Automated immediate investigation triggers when a new transmitter becomes active, starting detailed investigation to identify and locate interferers.

Evidence Documentation: Measurement setups and device configurations are documented for regulatory compliance and legal admissibility in enforcement proceedings.

Technical Features: Open interfaces compatible with existing spectrum management systems, modular design supporting customization, scalable architecture for future expansion, investment protection through upgradeability.""",
    },
    # ── KB-Product: Competitor Systems ──
    {
        "title": "Keysight N6854A Geolocation Server & N6841A RF Sensor",
        "url": "https://www.keysight.com/us/en/products/signal-monitoring/n6854a-geolocation-server.html",
        "type": SourceType.PRODUCT_PAGE,
        "pool": KBPool.PRODUCT,
        "section": "Competitor Product",
        "fetch_selectors": [".product-content", "article", "main"],
        "fallback": """The Keysight N6854A Geolocation Server combined with N6841A RF Sensors forms a network-based spectrum monitoring and emitter geolocation system competing directly with R&S regulatory monitoring solutions.

Geolocation Technology: Uses Time Difference of Arrival (TDOA) and Received Signal Strength (RSS) methods for emitter location. Typical accuracy 10-300 meters depending on sensor geometry and signal characteristics. Supports both narrowband and wideband signals for location.

N6841A RF Sensor: Frequency range 20 MHz to 6 GHz. Designed for unattended 24/7 operation in fixed installations. Compact form factor for distributed deployment on rooftops and towers. Remote-controlled via IP network for centralized management.

Surveyor 4D Integration: The N6854A integrates with Keysight's Surveyor 4D spectrum management software platform. Provides real-time spectrum visualization with 3D geographic display. Automated signal detection and classification workflows. Historical data analysis for trend identification and compliance reporting.

Network Architecture: Scalable sensor network supporting dozens to hundreds of distributed sensors. Centralized server processes data from all sensors simultaneously. Standard IP networking between sensors and server enables flexible deployment. Supports mixed fixed and mobile sensor configurations.

Key Differentiators vs R&S: Keysight emphasizes software-defined approach with flexible signal processing. Lower per-sensor cost enables denser network deployments. Strong integration with Keysight's test and measurement ecosystem. Focus on automated workflows reducing operator intervention.

Limitations: Maximum frequency 6 GHz significantly below R&S ESMW's 40+ GHz range. No built-in direction finding capability — relies purely on TDOA/RSS. Real-time bandwidth more limited than R&S wideband receivers. Less suited for signals intelligence applications requiring instantaneous wideband capture.""",
    },
    {
        "title": "Anritsu MS27201A Remote Spectrum Monitor",
        "url": "https://www.anritsu.com/en-us/test-measurement/products/ms27201a",
        "type": SourceType.PRODUCT_PAGE,
        "pool": KBPool.PRODUCT,
        "section": "Competitor Product",
        "fetch_selectors": [".product-detail", "article", "main"],
        "fallback": """The Anritsu MS27201A is a high-performance remote spectrum monitor designed for continuous 24/7 spectrum surveillance in regulatory and defense applications.

Frequency Range: 9 kHz to 43.5 GHz (standard), extendable to 54 GHz. This wide frequency range covers all major commercial and government spectrum allocations including millimeter-wave 5G bands.

RF Performance: Displayed Average Noise Level (DANL) of -164 dBm enables detection of extremely weak signals. Third-Order Intercept (TOI) of +20 dBm provides excellent linearity in high-signal-density environments. This combination of sensitivity and dynamic range is critical for urban monitoring where weak interferers coexist with strong licensed signals.

Analysis Bandwidth: 150 MHz instantaneous analysis bandwidth supports capture of wideband signals including LTE, 5G NR, and radar emissions. I/Q data streaming for offline analysis of complex waveforms.

Deployment: Rack-mountable 19-inch form factor for fixed installation in monitoring stations. Designed for unattended continuous operation with remote management via IP. Environmental specifications support outdoor installation with appropriate enclosures.

Key Differentiators: Exceptional RF sensitivity (-164 dBm DANL) among the best in class for monitoring receivers. Wide frequency coverage to 43.5/54 GHz covers emerging mmWave bands. Compact single-unit design integrates receiver, digitizer, and processing. Strong ITU compliance for regulatory measurement requirements.

Competitive Position: Directly competes with R&S ESMD and ESMW for fixed monitoring station deployments. Frequency range advantage over Keysight (43.5 GHz vs 6 GHz) but below R&S ESMW (40-53 GHz). Lacks R&S's integrated direction finding capability. Lower real-time bandwidth (150 MHz) than R&S ESMW (up to 2 GHz) limits intercept probability for frequency-hopping signals.""",
    },
    {
        "title": "CRFS RFeye Node Distributed Spectrum Monitoring",
        "url": "https://www.crfs.com/products/rfeye-node/",
        "type": SourceType.PRODUCT_PAGE,
        "pool": KBPool.PRODUCT,
        "section": "Competitor Product",
        "fetch_selectors": [".product-content", "article", "main"],
        "fallback": """CRFS RFeye Node is a family of compact, ruggedized spectrum monitoring receivers designed for distributed deployment in dense sensor networks.

Product Range: Multiple variants covering different frequency ranges and capabilities. RFeye Node 40-8: 10 MHz to 8 GHz. RFeye Node 100-8: 10 MHz to 8 GHz with 100 MHz IBW. RFeye Node 100-18: 10 MHz to 18 GHz. RFeye Node 100-40: 10 MHz to 40 GHz. RFeye Node Plus: Enhanced processing capability for edge analytics.

Architecture Philosophy: CRFS takes a fundamentally different approach from traditional monitoring receivers. Instead of a few expensive high-performance receivers (R&S, Anritsu approach), CRFS deploys many lower-cost nodes in a mesh network. This "sensor swarm" architecture provides spatial diversity and redundancy.

Edge Processing: Each node contains onboard processing capability for signal detection, classification, and feature extraction. Reduces backhaul bandwidth requirements by processing data locally. Enables real-time alerting at the sensor level without server round-trips. Machine learning inference running directly on sensor hardware.

Ruggedization: IP67-rated enclosures for outdoor deployment without additional weatherproofing. Operating temperature range -40C to +55C. Low power consumption enables solar-powered remote installations. Compact form factor allows concealed mounting on infrastructure.

Software Platform: RFeye DeepView provides centralized management of distributed sensor networks. Web-based interface for multi-user concurrent access. API-first design enables integration with third-party spectrum management systems. Automated signal detection and geolocation using networked sensors.

Competitive Differentiation: Lower per-unit cost enables 5-10x denser deployments vs R&S or Anritsu. Edge computing reduces infrastructure requirements. Mesh networking provides graceful degradation if individual nodes fail. Software-defined architecture allows capability upgrades without hardware changes.

Limitations vs R&S: Individual node RF performance (sensitivity, dynamic range) below dedicated monitoring receivers. Real-time bandwidth limited to 100 MHz vs R&S ESMW's 2 GHz. No integrated direction finding at individual node level. Network-dependent geolocation accuracy lower than DF-based approaches for single-signal scenarios.""",
    },
    {
        "title": "HawkEye 360 Satellite-Based RF Geolocation",
        "url": "https://www.he360.com/capabilities/",
        "type": SourceType.PRODUCT_PAGE,
        "pool": KBPool.PRODUCT,
        "section": "Competitor Product — Space-Based",
        "fetch_selectors": [".capability-content", "article", "main"],
        "fallback": """HawkEye 360 operates a constellation of 30+ LEO satellites for space-based radio frequency (RF) signal detection and geolocation, representing a fundamentally different approach to spectrum monitoring compared to ground-based systems from R&S, Keysight, or Anritsu.

Constellation Architecture: Satellites operate in clusters of three for TDOA/FDOA-based geolocation. Each satellite carries software-defined radio (SDR) payloads covering VHF through Ku-band. Low Earth Orbit (altitude ~500-600 km) enables global coverage including oceans, remote areas, and denied territories where ground infrastructure is impossible.

Kestrel Next-Generation Payload: Advanced SDR payload with increased sensitivity and bandwidth. Supports simultaneous monitoring of multiple frequency bands. Enhanced onboard processing for signal characterization before downlink. Designed for rapid technology refresh via software updates.

Capabilities: Detection and geolocation of radar emissions, push-to-talk radios, satellite phones, AIS transponders, emergency beacons, and GNSS interference sources. GNSS spoofing and jamming detection demonstrated operationally. Maritime domain awareness through correlation of RF emissions with vessel tracking data.

Government Contracts: $131 million FMS (Foreign Military Sales) contract to supply RF geolocation services to India's defense establishment (2024). Multiple contracts with US DoD, intelligence community, and allied nations. Growing regulatory use cases for spectrum compliance monitoring from space.

Competitive Implications for R&S: Space-based monitoring is complementary rather than directly competitive — satellites cannot match ground receiver sensitivity or real-time bandwidth. However, HawkEye 360 disrupts the value proposition for remote/maritime monitoring where ground stations are impractical. Hybrid architectures combining space and ground monitoring are emerging as the industry direction. R&S ground systems provide high-fidelity follow-up after satellite-based initial detection.

Limitations: Revisit time limits continuous monitoring (not persistent like ground stations). Geolocation accuracy (km-level) far below ground TDOA (10-300m). Cannot perform detailed signal analysis — only detection and coarse characterization. Weather and atmospheric effects impact signal propagation measurements. Orbital mechanics constrain coverage scheduling.""",
    },
    # ── KB-Trends: Technology Trends & Research ──
    {
        "title": "AI-Enabled Spectrum Management in 6G and Future Networks (Systematic Literature Review)",
        "url": "https://arxiv.org/abs/2407.10981",
        "type": SourceType.RESEARCH_PAPER,
        "pool": KBPool.TREND,
        "section": "Key Findings",
        "fallback": """Systematic literature review of 110 peer-reviewed studies (2013-2023) on AI-enabled spectrum management (AISM). Spectrum management is transitioning from static regulatory frameworks toward dynamic, intelligent systems leveraging machine learning for real-time optimization.

Primary AISM Applications:

Resource Management (39.78% of studies): Dynamic Spectrum Allocation (DSA) where secondary users access unused frequency bands via real-time availability detection. Adaptive bandwidth allocation methods achieving near-unity utilization factors compared to traditional static approaches. Federated learning combined with data augmentation enables 50-70% reduction in channel switching frequency under dynamic jamming conditions. Deep reinforcement learning approaches like MATD3 minimize latency and energy consumption while managing cache resources efficiently.

Beam Management (29.09% of studies): CNN and LSTM architectures dominate, with double-layer online learning algorithms reducing overhead in mmWave vehicular communications. Deep reinforcement learning achieved higher data rates without introducing additional overhead using RF fingerprints. MAB-based frameworks demonstrated 25-35% throughput gains versus conventional strategies in millimeter-wave systems.

Channel Management (23.67% of studies): GANs and CNN-based approaches provide robust channel estimation. Deep CNNs with transfer learning improved TV signal detection accuracy across varied environments with significantly reduced training requirements.

AI/ML Methodology Distribution: Deep Learning 47.27% (CNNs, MLPs, LSTMs), Reinforcement Learning 23.64% (DRL, policy gradient methods DDPG, A3C), Federated Learning 12.73% (decentralized training, privacy preservation), Classical ML 11.82% (SVMs, clustering, anomaly detection).

Emerging Architecture Trends: Terahertz (0.3-10 THz) exploitation for ultra-high bandwidth. Intelligent Reflecting Surfaces (IRS) with passive beamforming optimization via deep learning. Massive MIMO scaling requiring automated beam management. Space-Air-Ground Integration for multi-domain resource coordination via federated approaches.

Critical Challenges: Computational resource demands limit real-time deployment. Transparency and interpretability issues with opaque DL models in regulatory contexts. Insufficient real-world datasets causing model overfitting. Security-privacy imbalance with only 14% of studies addressing defenses. Absence of standardized testbeds and benchmarks.

Future Directions: Integration of Large Language Models for predictive policy optimization. Privacy-preserving federated learning at scale. Explainable AI frameworks for regulatory compliance. Hybrid classical-quantum approaches for NP-hard resource problems.""",
    },
    {
        "title": "Future Trends in Spectrum Monitoring: AI, Cognitive Radio, and 6G",
        "url": "https://www.mwrf.com/technologies/communications/wireless/article/55246439/",
        "type": SourceType.TECH_ARTICLE,
        "pool": KBPool.TREND,
        "section": "Technology Trends Overview",
        "fetch_selectors": [".article-body", ".article-content", "article"],
        "fallback": """Spectrum Scarcity and the 6G Imperative: Mobile devices expected to reach 80 billion by 2030. By 2030, 5G networks will reach capacity limits and will be inadequate for next-generation bandwidth-hungry, ubiquitous, intelligent services. Global traffic predicted to increase to approximately 5,000 EB/month by 2030, driven by AR/VR, Internet of Everything, AI, and robotics.

AI-Driven Spectrum Sensing and Dynamic Spectrum Access: Cognitive radio networks leveraging AI-driven spectrum sensing provide a promising solution to improve spectrum utilization. Key AI/ML models include CNNs, LSTMs, Graph Neural Networks (GNN), and multi-agent reinforcement learning (MARL) for distributed DSA networks where agents autonomously optimize power allocation.

Deep Learning for Spectrum Prediction: Spectrum prediction enhances efficiency by assisting dynamic spectrum access in cognitive radio networks. The highly nonlinear nature of spectrum data across time, frequency, and space domains requires deep learning to extract nonlinear features.

6G Standardization and AI-Native Networks by 2030: ITU aims to finalize 6G standardization by 2030, introducing AI-driven technology to create self-learning, intelligent networks integrating digital and physical worlds. 6G targets high data rates, extensive connectivity, improved cost-efficiency, efficient resource management, and enhanced security through AI.

Cognitive Radio Evolution: Integration of Machine Learning and AI to enhance spectrum sensing, access, and management. Applications expanding beyond telecommunications into public safety, disaster recovery, smart cities, and industrial IoT. Convergence with edge computing and terahertz communication.

Federated Learning and Energy Efficiency: Challenges include computational complexity, adaptability to real-time environments, and model generalization. Promising directions include energy-efficient AI architectures, federated learning for decentralized cognitive radio networks, and cooperative spectrum sensing methods.

Digital Twin Networks: Dynamic replicas of physical networks for full life cycle management. Capable of generating perceptive and cognitive intelligence from historical and online network data. Enables network self-boosting, self-evolving, and self-optimizing by verifying new functionalities before deployment.

THz Communications: Trend towards higher data rates approaching Tbit/s regime indoors, requiring large available bandwidths in sub-THz bands. Extension to much higher frequency bands with smart utilization of multiple bands.

Security and Anomaly Detection: ML and statistical techniques for detecting and adapting to novel attacks. Cybersecurity for IoT/IIoT growing concern as more wireless-enabled sensors come online.""",
    },
    {
        "title": "Quantum Sensing and Space-Based Spectrum Monitoring Trends",
        "url": "",
        "type": SourceType.TECH_ARTICLE,
        "pool": KBPool.TREND,
        "section": "Emerging Technologies",
        "fallback": """Quantum RF Sensing: Rydberg atom-based electric field sensors offer fundamentally different approach to RF detection. Rydberg atoms can detect RF signals across an extremely wide frequency range (DC to THz) with a single sensor element, eliminating need for multiple antennas. Demonstrated sensitivities approaching the quantum limit, potentially 100x more sensitive than conventional receivers. No metallic components means no electromagnetic interference with the measured field. Key challenges include miniaturization, room-temperature operation, and integration with existing systems. Timeline: laboratory demonstrations now, field-ready prototypes expected 2028-2032.

Space-Based Spectrum Monitoring: LEO satellite constellations for global spectrum monitoring coverage. Advantages include monitoring remote areas, oceans, and regions without ground infrastructure. Companies and agencies exploring cubesat-based spectrum monitoring payloads. Integration with ground networks for comprehensive 3D spectrum awareness. Challenges include latency, spatial resolution limitations, and cost of constellation deployment.

Software-Defined Radio (SDR) Evolution: Transition from hardware-defined to fully software-defined receiver architectures. Enables rapid reconfiguration for new waveforms, standards, and frequency bands. Direct RF sampling ADCs reducing analog component count. Machine learning integration for automatic modulation recognition and signal classification.

Edge Computing for Distributed Monitoring: Processing at the sensor node rather than centralizing all data. Reduces bandwidth requirements for networked monitoring stations. Enables real-time local decision making while contributing to global picture. Integration with 5G/6G edge infrastructure for shared compute resources.

Photonic Signal Processing: Microwave photonics for ultra-wideband signal processing. Photonic ADCs achieving sampling rates beyond electronic limits. Optical beamforming for antenna arrays. Potential for significant SWaP (size, weight, and power) reduction in receiver systems.""",
    },
    # ── KB-Trends: Latest Research (arXiv 2024-2025) ──
    {
        "title": "Deep Learning for Spectrum Prediction in Cognitive Radio Networks (2024)",
        "url": "https://arxiv.org/abs/2412.09849",
        "type": SourceType.RESEARCH_PAPER,
        "pool": KBPool.TREND,
        "section": "ML Spectrum Prediction",
        "fallback": """Survey of deep learning approaches for spectrum prediction in cognitive radio networks, focusing on temporal, spatial, and frequency-domain modeling for dynamic spectrum access.

Core Problem: Spectrum occupancy is highly dynamic — signals appear and disappear on millisecond timescales. Predicting future spectrum state enables proactive channel selection rather than reactive sensing, reducing latency and improving secondary user throughput.

Temporal Models: LSTM and GRU networks capture long-range temporal dependencies in spectrum occupancy patterns. Transformer-based architectures achieving state-of-the-art performance by modeling attention across time steps. Temporal CNNs with dilated convolutions as computationally efficient alternative to recurrent models.

Spatial-Spectral Models: 3D CNNs jointly model time, frequency, and spatial dimensions of spectrum data. Graph Neural Networks represent spatial relationships between monitoring stations for distributed prediction. Attention mechanisms learn which spatial locations are most informative for a given prediction.

Transfer Learning: Pre-trained models on large spectrum datasets significantly reduce training requirements for new deployment locations. Domain adaptation techniques handle distribution shift between training and deployment environments. Few-shot learning enables rapid adaptation to new frequency bands with minimal labeled data.

Real-Time Deployment Challenges: Inference latency must be below channel coherence time (typically <10ms for mobile scenarios). Model compression techniques (pruning, quantization, knowledge distillation) reduce computational requirements. Edge deployment on FPGAs and specialized AI accelerators for microsecond inference. Trade-off between prediction accuracy and computational cost remains active research area.

Implications for Monitoring: Predictive models could enable monitoring systems to anticipate interference events before they occur. Resource allocation in monitoring networks can be optimized based on predicted spectrum activity. Anomaly detection becomes more powerful when comparing actual spectrum state against predictions. Integration with digital twin models for scenario simulation and planning.""",
    },
    {
        "title": "Rydberg Atom Quantum RF Sensing: Comprehensive Review (2024)",
        "url": "https://arxiv.org/abs/2401.01655",
        "type": SourceType.RESEARCH_PAPER,
        "pool": KBPool.TREND,
        "section": "Quantum Sensing",
        "fallback": """Comprehensive review of Rydberg atom-based electric field sensors for microwave and RF measurement, covering physics, recent experimental advances, and path toward practical deployment.

Physical Principle: Rydberg atoms are atoms excited to very high principal quantum numbers (n>30) where outer electrons are loosely bound. These atoms exhibit extreme sensitivity to external electric fields due to large electric dipole moments scaling as n^2. Electromagnetically induced transparency (EIT) in atomic vapor cells provides optical readout of RF field strength.

Frequency Coverage: Single Rydberg sensor element covers DC to THz frequency range by selecting appropriate atomic transitions. No metallic antenna required — the atom itself is the sensor. Eliminates frequency-dependent antenna calibration issues that plague conventional receivers. Multiple simultaneous frequency measurements possible via different Rydberg states.

Sensitivity Achievements: Laboratory demonstrations approaching quantum-limited sensitivity of ~1 µV/cm/√Hz. Recent high-resolution Rydberg receiver experiments (arXiv:2506.11833) demonstrated sub-MHz channel resolution. Sensitivity improvements of 100-1000x over conventional dipole antennas at certain frequencies. Phase-sensitive detection enabling coherent signal processing.

Key Advantages for Monitoring: Self-calibrating — response traceable to fundamental atomic constants (SI-traceable). No electromagnetic interference from sensor itself (all-dielectric). Compact vapor cell form factor (mm to cm scale). Extremely wide instantaneous bandwidth without hardware reconfiguration. Immune to electromagnetic pulse (EMP) damage.

Current Limitations: Requires laser systems for atom preparation (size, cost, power). Operating temperature constraints — most demonstrations at room temperature in vapor cells. Dynamic range limited compared to conventional superheterodyne receivers. Signal-to-noise ratio degrades in high-signal-density environments. Miniaturization of complete sensor system (lasers + optics + vapor cell) ongoing.

Timeline to Field Deployment: Laboratory demonstrations mature (TRL 3-4 as of 2024). Field-ready prototypes expected 2028-2032. Initial applications likely in calibration and metrology rather than operational monitoring. Full replacement of conventional receivers unlikely before 2035. Hybrid architectures combining Rydberg sensors with conventional receivers for complementary capabilities most probable near-term path.""",
    },
    {
        "title": "Digital Twin Networks for 6G: Concepts and Framework (2024-2025)",
        "url": "https://arxiv.org/abs/2409.02008",
        "type": SourceType.RESEARCH_PAPER,
        "pool": KBPool.TREND,
        "section": "Digital Twins",
        "fallback": """Analysis of digital twin concepts applied to 6G network management, combining arXiv:2506.01609 (network DT for 6G) and arXiv:2409.02008 (DT meets 6G concepts), plus arXiv:2506.18293 (LLM-integrated DT).

Digital Twin Definition for Networks: A digital twin network (DTN) is a real-time, high-fidelity virtual replica of a physical network that enables simulation, prediction, optimization, and autonomous management. Unlike simple network models, DTNs continuously synchronize with the physical network state and evolve alongside it.

Architecture Layers: Physical Network Layer (actual infrastructure, spectrum, users). Digital Twin Layer (virtual replicas, ML models, simulation engines). Service/Application Layer (optimization algorithms, policy engines, autonomous control). Data Synchronization Layer (real-time telemetry, state updates, feedback loops).

Applications for Spectrum Management: Simulate spectrum allocation strategies before deployment to predict interference patterns. "What-if" analysis for new spectrum assignments without risking real-world disruption. Predict network congestion and proactively reallocate spectrum resources. Test regulatory policy changes in simulation before implementation.

LLM Integration (arXiv:2506.18293): Large Language Models as natural language interfaces to digital twin networks. Operators query network state, run simulations, and adjust parameters through conversational interaction. LLMs translate high-level objectives into specific network configuration changes. Automated report generation from digital twin analytics.

Implications for Monitoring Equipment: Monitoring systems become data feeds for digital twins rather than standalone analysis tools. Real-time spectrum measurements populate digital twin models of the electromagnetic environment. Monitoring networks can be optimized by simulating sensor placement in the digital twin. Anomaly detection enhanced by comparing real measurements against digital twin predictions.

Challenges: Computational cost of maintaining real-time synchronized digital twins. Data quality and latency requirements for accurate twin representation. Standardization of digital twin interfaces and data formats. Security of digital twin systems — a compromised twin could misdirect network management decisions.

Timeline: Basic DTN concepts being integrated into 6G standardization (2024-2026). Commercial DTN platforms expected by 2028-2030. Full autonomous network management via DTN likely post-2032.""",
    },
    {
        "title": "Federated Learning for Distributed Spectrum Sensing (2024)",
        "url": "https://arxiv.org/abs/2411.11159",
        "type": SourceType.RESEARCH_PAPER,
        "pool": KBPool.TREND,
        "section": "Federated Learning",
        "fallback": """Survey of federated learning approaches for cooperative spectrum sensing in distributed monitoring networks, synthesizing findings from arXiv:2410.23949 (DL cognitive radio frameworks), arXiv:2406.12330 (security FL spectrum sharing), and arXiv:2411.11159 (FL UAV spectrum sensing).

Core Motivation: Traditional cooperative spectrum sensing requires transmitting raw I/Q data from sensors to a central fusion center — bandwidth-intensive and privacy-compromising. Federated learning enables collaborative model training where sensors share only model updates (gradients), not raw spectrum data.

Architecture: Each monitoring node trains a local ML model on its observed spectrum data. Periodic aggregation of model parameters at a central server (FedAvg, FedProx, etc.). Global model distributed back to nodes incorporates knowledge from all locations. Differential privacy mechanisms protect individual node observations from inference attacks.

UAV-Based Spectrum Sensing (arXiv:2411.11159): Unmanned aerial vehicles as mobile spectrum sensors providing 3D coverage. FL enables cooperative sensing across UAV swarm without centralizing sensitive spectrum data. Position-aware federated models adapt to spatial variations in spectrum occupancy. Energy constraints of UAVs make communication-efficient FL essential — compressed gradients and sparse updates.

Security Considerations (arXiv:2406.12330): Byzantine-resilient aggregation protects against compromised or malicious sensor nodes injecting false spectrum observations. Adversarial attacks on FL models can cause sensors to miss unauthorized transmissions. Defense mechanisms including robust aggregation, anomaly detection on gradient updates, and secure multi-party computation. Privacy-preserving FL prevents reconstruction of sensitive spectrum intelligence from shared gradients.

Deep Learning Frameworks (arXiv:2410.23949): CNN-based signal classifiers achieving >95% accuracy on modulation recognition. Autoencoder architectures for anomaly detection in spectrum occupancy patterns. Reinforcement learning agents for autonomous spectrum access decisions. Integration with edge computing platforms (NVIDIA Jetson, Intel Movidius) for real-time inference.

Relevance to R&S Monitoring: Distributed R&S monitoring networks could benefit from FL for collaborative signal classification without centralizing raw I/Q data. Regulatory agencies operating cross-border monitoring networks face data sovereignty constraints that FL addresses. FL enables model improvement from fleet-wide operational data without exposing individual station measurements. Potential for R&S to offer FL-based analytics as a differentiating software feature for networked monitoring systems.""",
    },
    # ── KB-Trends: Regulatory & Standards ──
    {
        "title": "ITU-R Handbook on Spectrum Monitoring (2024 Edition)",
        "url": "https://www.itu.int/pub/R-HDB-23",
        "type": SourceType.REGULATION,
        "pool": KBPool.TREND,
        "section": "Regulatory Framework",
        "fetch_selectors": [".content-area", "article", "main"],
        "fallback": """The ITU Handbook on Spectrum Monitoring provides the international reference framework for radio spectrum monitoring systems and practices, directly defining compliance requirements for equipment from R&S, Keysight, Anritsu, and others.

Measurement Requirements: ITU-R defines standardized measurement procedures for occupied bandwidth (SM.328-11), frequency offset, field strength, modulation parameters, and spectrum occupancy. All monitoring receivers must implement these measurements to specified accuracy levels. Calibration traceability and measurement uncertainty documentation mandatory for regulatory enforcement.

Automated Monitoring: The 2024 edition significantly expands coverage of automated and AI-assisted monitoring. Recommendations for automated spectrum occupancy measurement, deviation detection, and trend analysis. Recognition that manual monitoring cannot scale to modern spectrum density. Framework for validating AI-based monitoring tools against traditional measurement methods.

Direction Finding Standards: ITU-R SM.2060 defines DF performance requirements including angular accuracy, sensitivity, and frequency range. Comparison of Adcock, Watson-Watt, correlative interferometer, and TDOA methods. Requirements for multipath-resistant DF in urban environments. Integration of DF data from multiple stations for emitter geolocation.

Network Architecture Guidance: Recommendations for designing monitoring networks with appropriate station density and placement. Fixed, mobile, and transportable station roles and specifications. Data exchange formats between monitoring stations and central management. Remote control protocols and cybersecurity requirements for networked monitoring.

Emerging Technology Recognition: ITU-R acknowledges SDR-based monitoring receiver evolution. Discussion of software-defined and cloud-based processing architectures. Preliminary guidance on spectrum monitoring from space-based platforms. Recognition of quantum sensing as future technology for spectrum measurement.

Impact on Equipment Manufacturers: ITU compliance is table stakes for regulatory market access — non-compliant equipment is excluded from government procurement. Standards evolution drives product roadmaps: manufacturers must anticipate and implement new requirements. Increasing automation requirements favor vendors with strong software capabilities. Interoperability standards enable multi-vendor monitoring networks, increasing competitive pressure.""",
    },
    {
        "title": "FCC Spectrum Frontiers & 6G Spectrum Policy (2024-2025)",
        "url": "https://www.fcc.gov/spectrum-frontiers",
        "type": SourceType.REGULATION,
        "pool": KBPool.TREND,
        "section": "Regulatory Trends",
        "fetch_selectors": [".field-items", ".node-content", "article", "main"],
        "fallback": """Overview of evolving US and global spectrum regulatory policy affecting the monitoring equipment market through 2035.

Spectrum Frontiers (Above 24 GHz): FCC has allocated multiple millimeter-wave bands for 5G and future use: 24 GHz, 28 GHz, 37 GHz, 39 GHz, 47 GHz bands. Additional allocations under consideration for 6G in the 71-76 GHz, 81-86 GHz, and sub-THz (100-300 GHz) ranges. Each new allocation creates monitoring requirements — regulators need equipment capable of operating at these frequencies.

Dynamic Spectrum Sharing: CBRS (Citizens Broadband Radio Service) at 3.5 GHz pioneered three-tier spectrum sharing in the US. ESC (Environmental Sensing Capability) networks demonstrate automated monitoring for spectrum sharing. Similar frameworks expanding to other bands globally. Real-time monitoring becomes integral to spectrum access — not just enforcement.

6G Spectrum Planning: ITU-R WRC-27 agenda items include new allocations above 100 GHz. AI-native 6G networks may require fundamentally different monitoring approaches. Spectrum sensing becomes embedded in network infrastructure rather than external monitoring. Regulatory frameworks evolving toward real-time, automated compliance verification.

European Regulatory Trends: ETSI EN 303 420 defines spectrum monitoring equipment requirements for EU market. CEPT ECC actively harmonizing monitoring approaches across European administrations. European Electronic Communications Code pushing toward more dynamic spectrum management. Digital Single Market initiatives drive cross-border monitoring coordination.

Implications for Monitoring Equipment Market: Growing frequency coverage requirements push receiver technology boundaries. Shift from periodic compliance checks to continuous automated monitoring. Regulators becoming technology buyers rather than just rule-setters. Government procurement cycles (5-10 years) create long-term revenue visibility but slow adoption of new technology. Cybersecurity requirements for monitoring infrastructure increasing — networked systems must resist nation-state level threats.

Market Growth Drivers: Every new spectrum allocation creates monitoring demand. Spectrum sharing regimes require real-time monitoring infrastructure. 5G/6G densification increases interference management complexity. Growing awareness of GNSS jamming and spoofing threats drives detection capability requirements. Space-based communications (LEO constellations) create monitoring challenges in previously unused bands.""",
    },
    # ── KB-Trends: Signal Classification ──
    {
        "title": "ML-based Automatic Modulation Recognition for Spectrum Monitoring (2024)",
        "url": "https://arxiv.org/abs/2502.02889",
        "type": SourceType.RESEARCH_PAPER,
        "pool": KBPool.TREND,
        "section": "Signal Classification",
        "fallback": """From DeepSense to Open RAN: survey of machine learning approaches for automatic modulation classification (AMC) in operational spectrum monitoring, bridging research and deployment.

Core Task: Automatic modulation recognition identifies the modulation scheme (AM, FM, QAM, OFDM, etc.) of detected signals without prior knowledge. Critical for monitoring systems to classify unknown emitters as licensed/unlicensed and identify interference types.

Deep Learning Architectures: CNN-based classifiers operating on raw I/Q samples achieve >95% accuracy across 11+ modulation types at SNR >5dB. ResNet and DenseNet architectures provide robust performance across varying channel conditions. Recurrent architectures (LSTM, GRU) capture temporal signal structure for burst and hopping signals. Transformer-based AMC models achieving state-of-the-art accuracy with better generalization to unseen signal parameters.

Key Datasets: RadioML 2016.10a/2018.01a: Widely used benchmarks with 11-24 modulation types under varying SNR and channel impairments. DeepSig datasets with realistic impairments including multipath, frequency offset, and sample rate mismatch. Operational datasets from real-world monitoring stations showing significant domain gap with synthetic data.

Edge Deployment: Model optimization for embedded platforms (FPGA, GPU, specialized NPUs). Quantized models (INT8) achieving near-float accuracy with 4x inference speedup. Real-time classification latency requirements: <1ms for streaming analysis, <10ms for batch processing. Power budget constraints for battery-operated and solar-powered monitoring nodes.

Open RAN Integration: O-RAN architecture provides standardized interfaces for ML-based signal processing. Near-real-time RAN Intelligent Controller (Near-RT RIC) as deployment platform for AMC models. xApps framework enables modular deployment of ML inference alongside network functions. Potential for monitoring receivers to leverage O-RAN ML infrastructure for shared analytics.

Implications for R&S: AMC capability is becoming table-stakes feature for monitoring receivers — manual modulation identification increasingly impractical. R&S monitoring software (e.g., ARGUS) integration with DL-based classifiers enables automated signal cataloging. Competitive differentiation shifts from RF hardware performance (converging across vendors) to software intelligence capabilities. Training data from deployed monitoring networks becomes strategic asset for model improvement.""",
    },
]


def add_source(
    collection,
    sources: dict,
    chunks: dict,
    title: str,
    url: str,
    source_type: SourceType,
    pool: KBPool,
    content: str,
    section: str = "",
    content_origin: ContentOrigin = ContentOrigin.CURATED,
) -> list[Chunk]:
    """Register source, chunk content, embed, store in ChromaDB."""
    src = Source(
        id=stable_id(url or title, title),
        title=title,
        url=url,
        type=source_type,
        pool=pool,
        content_origin=content_origin,
    )
    sources[src.id] = src

    # Split on double-newlines and merge small paragraphs
    raw_chunks = [p.strip() for p in content.split("\n\n") if p.strip()]
    merged: list[str] = []
    buf = ""
    for rc in raw_chunks:
        if len(buf) + len(rc) < 1200:
            buf = f"{buf}\n\n{rc}" if buf else rc
        else:
            if buf:
                merged.append(buf)
            buf = rc
    if buf:
        merged.append(buf)

    new_chunks: list[Chunk] = []
    for text in merged:
        chunk = Chunk(
            id=stable_id(src.id, text[:200]),
            source_id=src.id,
            content=text,
            section=section,
            pool=pool,
        )
        chunks[chunk.id] = chunk
        new_chunks.append(chunk)

    embeddings = embed([c.content for c in new_chunks])

    collection.add(
        ids=[c.id for c in new_chunks],
        embeddings=embeddings,
        documents=[c.content for c in new_chunks],
        metadatas=[
            {
                "source_id": c.source_id,
                "source_title": src.title,
                "pool": c.pool.value,
                "section": c.section,
            }
            for c in new_chunks
        ],
    )

    origin_tag = "FETCHED" if content_origin == ContentOrigin.FETCHED else "CURATED"
    print(f"  [{origin_tag}] {len(new_chunks)} chunks ({len(content)} chars) — '{title}' [{pool.value}]")
    return new_chunks


def run(output_path: str = "data/outputs/kb_state.json") -> dict:
    """Run the full KB pipeline: fetch sources, chunk, embed, store."""
    client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)

    # Clear and recreate collection for clean rebuild
    try:
        client.delete_collection("knowledge_base")
    except ValueError:
        pass
    collection = client.get_or_create_collection(
        name="knowledge_base",
        metadata={"hnsw:space": "cosine"},
    )

    sources: dict[str, Source] = {}
    chunks: dict[str, Chunk] = {}

    # Fetch and ingest all sources
    fetch_stats = {"fetched": 0, "curated": 0}

    for entry in SOURCE_REGISTRY:
        url = entry["url"]
        content = ""
        origin = ContentOrigin.CURATED

        if url:
            arxiv_id = extract_arxiv_id(url)
            if arxiv_id:
                content = fetch_arxiv(arxiv_id)
            else:
                content = fetch_webpage(url, selectors=entry.get("fetch_selectors"))

        if len(content) > 200:
            origin = ContentOrigin.FETCHED
            fetch_stats["fetched"] += 1
        else:
            content = entry["fallback"]
            fetch_stats["curated"] += 1

        add_source(
            collection,
            sources,
            chunks,
            title=entry["title"],
            url=url,
            source_type=entry["type"],
            pool=entry["pool"],
            content=content,
            section=entry.get("section", ""),
            content_origin=origin,
        )

    print(f"\n{'=' * 60}")
    print(f"FETCHED: {fetch_stats['fetched']}/{len(SOURCE_REGISTRY)}")
    print(f"CURATED: {fetch_stats['curated']}/{len(SOURCE_REGISTRY)}")
    print(f"Total chunks: {len(chunks)}, ChromaDB: {collection.count()}")

    # Save state
    state = {
        "sources": {k: v.model_dump(mode="json") for k, v in sources.items()},
        "chunks": {k: v.model_dump(mode="json") for k, v in chunks.items()},
    }
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(state, f, indent=2, default=str)

    return state
