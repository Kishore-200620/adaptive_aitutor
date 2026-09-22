import hashlib
import logging
import traceback
from pathlib import Path
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List

@dataclass
class VisualIntent:
    primary_intent: str = 'generic'
    components: List[str] = field(default_factory=list)
    composition_intent: str = ''
    visual_style: str = 'educational_diagram'
    is_photorealistic: bool = False
    raw_directive: str = ''
    routing_reason: str = ''

logger = logging.getLogger("eduva.orchestrator")

class EducationalFallbackRenderer:
    def __init__(self):
        self.images_dir = Path("static/images")
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def _generate_cache_key(self, concept: str, directive: str) -> str:
        # Provide fallback if directive is empty
        d = (directive or "generic").strip()
        c = (concept or "concept").strip()
        cache_data = f"local_diagram:{c}:{d}"
        return hashlib.md5(cache_data.encode("utf-8")).hexdigest()

    def analyze_intent(self, directive: str, concept: str = '') -> VisualIntent:
        d = (directive or '').strip().lower()
        c = (concept or '').strip().lower()
        text = d if d else c
        
        intent = VisualIntent(raw_directive=d or c)
        
        # 1. Gather evidence
        photo_words = ['photo', 'photograph', 'photorealistic', 'realistic', 'real-world appearance', 'physical appearance', 'actual physical object']
        has_photo = any(w in text for w in photo_words)
        has_comparison = 'compare' in text or 'comparison' in text
        
        # SYMBOL evidence
        has_circuit_symbol = 'circuit symbol' in text
        
        # SYSTEM / COMPOSITION evidence
        composition_phrases = [
            'series circuit', 'parallel circuit', 'schematic', 'wiring', 'connected', 'connection',
            'current path', 'complete circuit', 'circuit containing', 'circuit with',
            'draw the circuit', 'circuit diagram', 'electronic circuit', 'electrical circuit',
            'circuit connected'
        ]
        has_strong_composition = any(p in text for p in composition_phrases)
        
        if not has_strong_composition and 'circuit' in text and not has_circuit_symbol:
            if 'draw a circuit' in text or 'illustrate the circuit' in text or 'show the complete circuit' in text:
                has_strong_composition = True
            
        # COMPONENT evidence
        components_found = []
        concept_components = []
        for comp in ['resistor', 'diode', 'transistor', 'capacitor', 'led', 'battery', 'switch']:
            if comp in text:
                components_found.append(comp)
            if comp in c:
                concept_components.append(comp)
                
        if len(components_found) >= 2 and 'circuit' in text and not has_circuit_symbol:
            has_strong_composition = True
                
        # WAVEFORM evidence
        is_analog_digital = any(w in text for w in ['analog', 'digital']) and ('wave' in text or 'signal' in text)
        
        # 2. Resolve Intent Priority
        if has_photo and not has_comparison:
            intent.is_photorealistic = True
            intent.visual_style = 'photorealistic'
            
        intent.components = components_found or concept_components
        
        # Now route
        if has_comparison and not has_strong_composition:
            intent.primary_intent = components_found[0] if components_found else (concept_components[0] if concept_components else 'generic')
            intent.routing_reason = 'component comparison request'
        elif intent.is_photorealistic:
            intent.primary_intent = 'generated_image'
            intent.routing_reason = 'explicit photorealistic physical-object request'
            if components_found:
                intent.composition_intent = components_found[0]
            elif concept_components:
                intent.composition_intent = concept_components[0]
        elif is_analog_digital:
            intent.primary_intent = 'analog_digital'
            intent.routing_reason = 'explicit analog/digital waveform request'
        elif has_strong_composition:
            if 'series' in text and 'parallel' in text:
                intent.primary_intent = 'series_parallel'
            else:
                intent.primary_intent = 'circuit'
            intent.composition_intent = 'circuit'
            intent.routing_reason = 'system-level composition request outranks component mention'
        elif components_found:
            intent.primary_intent = components_found[0]
            if has_circuit_symbol:
                intent.routing_reason = 'component-symbol request; "circuit symbol" describes representation, not a circuit composition'
            else:
                intent.routing_reason = 'explicit component request'
        elif concept_components:
            intent.primary_intent = concept_components[0]
            intent.routing_reason = 'authoritative requested subject fallback; directive is descriptive'
        else:
            if 'circuit' in text or 'battery' in text or 'switch' in text:
                intent.primary_intent = 'circuit'
                intent.routing_reason = 'generic circuit mention'
            elif 'conductor' in text or 'insulator' in text:
                intent.primary_intent = 'conductor'
                intent.routing_reason = 'conductor/insulator request'
            elif ('voltage' in text or 'current' in text) and 'ohm' in text:
                intent.primary_intent = 'voltage_current'
                intent.routing_reason = 'voltage/current relationship request'
            elif 'waveform' in text or 'sine wave' in text or 'square wave' in text:
                intent.primary_intent = 'waveform'
                intent.routing_reason = 'waveform diagram request'
            elif 'graph' in text or 'chart' in text:
                intent.primary_intent = 'graph_chart'
                intent.routing_reason = 'graph/chart request'
            else:
                intent.primary_intent = 'generic'
                intent.routing_reason = 'no specific deterministic renderer matched'
                
        return intent

    def has_deterministic_renderer(self, directive: str, concept: str = "") -> bool:
        intent = self.analyze_intent(directive, concept)
        return intent.primary_intent != "generic" and intent.primary_intent != "generated_image"

    def render(self, visual_directive: str, concept: str) -> str:
        try:
            intent = self.analyze_intent(visual_directive, concept)
            diagram_type = intent.primary_intent
            cache_key = self._generate_cache_key(concept, visual_directive)
            filename = f"{cache_key}.svg"
            filepath = self.images_dir / filename
            file_url = f"/static/images/{filename}"

            if filepath.exists():
                if self._validate_svg(filepath):
                    return file_url
                else:
                    filepath.unlink(missing_ok=True)

            logger.info(f"[EDUVA][Visuals] Fallback type: {diagram_type}")
            
            if diagram_type == "analog_digital":
                svg_content = self._render_analog_digital()
            elif diagram_type == "circuit":
                svg_content = self._render_circuit()
            elif diagram_type == "resistor":
                svg_content = self._render_resistor()
            elif diagram_type == "conductor":
                svg_content = self._render_conductor()
            elif diagram_type == "voltage_current":
                svg_content = self._render_voltage_current()
            elif diagram_type == "waveform":
                svg_content = self._render_waveform()
            elif diagram_type == "transistor":
                svg_content = self._render_transistor()
            elif diagram_type == "diode":
                svg_content = self._render_diode()
            elif diagram_type == "capacitor":
                svg_content = self._render_capacitor()
            elif diagram_type == "series_parallel":
                svg_content = self._render_series_parallel()
            elif diagram_type == "graph_chart":
                svg_content = self._render_graph_chart()
            else:
                svg_content = self._render_generic(concept, visual_directive)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(svg_content)

            if self._validate_svg(filepath):
                logger.info("[EDUVA][Visuals] SVG validation passed")
                return file_url
            else:
                logger.error("[EDUVA][Visuals] Generated SVG failed validation.")
                filepath.unlink(missing_ok=True)
                return self.get_emergency_fallback()

        except Exception as e:
            logger.error(f"[EDUVA][Visuals] Unexpected error in EducationalFallbackRenderer: {e}")
            logger.debug(traceback.format_exc())
            return self.get_emergency_fallback()

    def get_emergency_fallback(self) -> str:
        logger.info("[EDUVA][Visuals] Using emergency fallback")
        filename = "emergency_fallback.svg"
        filepath = self.images_dir / filename
        file_url = f"/static/images/{filename}"
        
        svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 300" width="100%" height="100%" style="background-color: #f8fafc; border-radius: 8px;">
          <style>
            .title { font-family: sans-serif; font-size: 20px; font-weight: bold; fill: #475569; text-anchor: middle; }
            .subtitle { font-family: sans-serif; font-size: 14px; fill: #64748b; text-anchor: middle; }
            .box { fill: #e2e8f0; stroke: #94a3b8; stroke-width: 2; rx: 8; }
          </style>
          <rect x="50" y="50" width="500" height="200" class="box" />
          <text x="300" y="140" class="title">Educational Visual Request</text>
          <text x="300" y="170" class="subtitle">Requested concept could not be visually generated.</text>
        </svg>"""
        
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(svg_content)
            return file_url
        except Exception:
            # Absolute worst case, return a data URI so it NEVER returns None or blank
            return "data:image/svg+xml;utf8," + svg_content.replace('"', "'")

    def _validate_svg(self, filepath: Path) -> bool:
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            if not root.tag.endswith('svg'):
                return False
            return True
        except Exception as e:
            logger.error(f"[EDUVA][Visuals] SVG validation error: {e}")
            return False

    def _render_generic(self, concept: str, directive: str) -> str:
        # Fallback for unknown concepts, creates a whiteboard with the concept name
        c = (concept or "Educational Concept").replace("<", "&lt;").replace(">", "&gt;")[:30]
        return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400" width="100%" height="100%" style="background-color: white;">
  <style>
    .title {{ font-family: sans-serif; font-size: 28px; font-weight: bold; fill: #1e293b; text-anchor: middle; }}
    .subtitle {{ font-family: sans-serif; font-size: 16px; fill: #64748b; text-anchor: middle; }}
    .node {{ fill: #3b82f6; }}
    .edge {{ stroke: #cbd5e1; stroke-width: 3; fill: none; }}
  </style>
  <rect x="20" y="20" width="760" height="360" rx="10" stroke="#94a3b8" stroke-width="4" fill="#f8fafc" />
  <text x="400" y="80" class="title">{c}</text>
  <text x="400" y="110" class="subtitle">Concept Diagram</text>
  
  <!-- Generic Diagram -->
  <circle cx="400" cy="220" r="40" class="node" />
  <circle cx="250" cy="280" r="30" class="node" style="fill: #10b981;" />
  <circle cx="550" cy="280" r="30" class="node" style="fill: #ef4444;" />
  
  <path d="M 400 260 L 250 250" class="edge" />
  <path d="M 400 260 L 550 250" class="edge" />
</svg>"""

    def _render_analog_digital(self) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400" width="100%" height="100%" style="background-color: white;">
  <style>
    .axis { stroke: #94a3b8; stroke-width: 2; }
    .analog { stroke: #3b82f6; stroke-width: 4; fill: none; }
    .digital { stroke: #ef4444; stroke-width: 4; fill: none; stroke-linejoin: bevel; }
    .label { font-family: sans-serif; font-size: 18px; font-weight: bold; fill: #1e293b; }
    .sublabel { font-family: sans-serif; font-size: 14px; fill: #64748b; }
  </style>
  
  <!-- Analog Section -->
  <text x="50" y="40" class="label">Analog (continuous)</text>
  <text x="50" y="60" class="sublabel">Continuous waveform</text>
  <line x1="50" y1="120" x2="750" y2="120" class="axis" />
  <path d="M 50 120 C 150 -20, 250 260, 350 120 C 450 -20, 550 260, 650 120 C 700 50, 750 120, 750 120" class="analog" />

  <!-- Digital Section -->
  <text x="50" y="240" class="label">Digital (discrete)</text>
  <text x="50" y="260" class="sublabel">Discrete states (0 and 1)</text>
  <line x1="50" y1="320" x2="750" y2="320" class="axis" />
  <path d="M 50 320 L 150 320 L 150 240 L 250 240 L 250 320 L 350 320 L 350 240 L 450 240 L 450 320 L 550 320 L 550 240 L 650 240 L 650 320 L 750 320" class="digital" />
</svg>"""

    def _render_circuit(self) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400" width="100%" height="100%" style="background-color: white;">
  <style>
    .wire { stroke: #1e293b; stroke-width: 3; fill: none; }
    .component { stroke: #1e293b; stroke-width: 3; fill: white; }
    .label { font-family: sans-serif; font-size: 16px; font-weight: bold; fill: #334155; }
    .current { stroke: #ef4444; stroke-width: 2; fill: #ef4444; }
  </style>
  
  <text x="200" y="40" class="label" style="font-size: 20px;">Simple Series Circuit</text>

  <!-- Wires -->
  <path d="M 150 150 L 150 100 L 450 100 L 450 170" class="wire" />
  <path d="M 450 230 L 450 300 L 150 300 L 150 250" class="wire" />
  
  <!-- Battery -->
  <line x1="120" y1="150" x2="180" y2="150" class="component" style="stroke-width: 4;" />
  <line x1="135" y1="170" x2="165" y2="170" class="component" style="stroke-width: 6;" />
  <line x1="120" y1="190" x2="180" y2="190" class="component" style="stroke-width: 4;" />
  <line x1="135" y1="210" x2="165" y2="210" class="component" style="stroke-width: 6;" />
  <text x="60" y="185" class="label">Battery</text>
  <text x="140" y="130" class="label">+</text>
  <text x="140" y="240" class="label">-</text>
  <path d="M 150 210 L 150 250" class="wire" />

  <!-- Switch (Top wire) -->
  <line x1="280" y1="100" x2="320" y2="70" class="component" />
  <circle cx="280" cy="100" r="4" class="component" />
  <circle cx="330" cy="100" r="4" class="component" />
  <text x="280" y="60" class="label">Switch</text>

  <!-- Resistor -->
  <path d="M 450 170 L 430 180 L 470 190 L 430 200 L 470 210 L 430 220 L 450 230" class="wire" />
  <text x="490" y="205" class="label">Resistor</text>

  <!-- LED -->
  <circle cx="300" cy="300" r="25" class="component" />
  <path d="M 285 300 L 315 300 L 300 280 Z" class="component" style="fill: #1e293b;" />
  <line x1="285" y1="280" x2="315" y2="280" class="component" />
  <line x1="300" y1="260" x2="320" y2="240" class="current" marker-end="url(#arrow)" />
  <line x1="315" y1="270" x2="335" y2="250" class="current" marker-end="url(#arrow)" />
  <text x="280" y="350" class="label">LED</text>

  <!-- Defs for arrows -->
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#ef4444" />
    </marker>
    <marker id="current-arrow" viewBox="0 0 10 10" refX="5" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#1e293b" />
    </marker>
  </defs>

  <!-- Current Flow arrows -->
  <path d="M 180 100 L 220 100" class="wire" marker-end="url(#current-arrow)" stroke-dasharray="5,5" />
  <text x="180" y="85" class="label" style="font-size: 14px; fill: #64748b;">Current (I)</text>
</svg>"""

    def _render_resistor(self) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 300" width="100%" height="100%" style="background-color: white;">
  <style>
    .wire { stroke: #64748b; stroke-width: 8; fill: none; }
    .body { fill: #fde68a; stroke: #b45309; stroke-width: 2; }
    .band-red { fill: #ef4444; }
    .band-brown { fill: #92400e; }
    .band-gold { fill: #fbbf24; }
    .label { font-family: sans-serif; font-size: 18px; font-weight: bold; fill: #1e293b; text-anchor: middle; }
    .sublabel { font-family: sans-serif; font-size: 14px; fill: #64748b; text-anchor: middle; }
    .pointer { stroke: #cbd5e1; stroke-width: 2; fill: none; stroke-dasharray: 4,4; }
  </style>

  <text x="400" y="40" class="label" style="font-size: 24px;">Resistor</text>

  <!-- Wires -->
  <line x1="100" y1="150" x2="250" y2="150" class="wire" />
  <line x1="550" y1="150" x2="700" y2="150" class="wire" />

  <!-- Resistor Body -->
  <rect x="250" y="110" width="300" height="80" rx="20" class="body" />
  
  <!-- Bands -->
  <rect x="280" y="110" width="20" height="80" class="band-red" />
  <rect x="330" y="110" width="20" height="80" class="band-red" />
  <rect x="380" y="110" width="20" height="80" class="band-brown" />
  <rect x="490" y="110" width="20" height="80" class="band-gold" />
</svg>"""

    def _render_conductor(self) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400" width="100%" height="100%" style="background-color: white;">
  <style>
    .core { fill: #d97706; }
    .insulation { fill: #3b82f6; stroke: #1e3a8a; stroke-width: 2; }
    .label { font-family: sans-serif; font-size: 18px; font-weight: bold; fill: #1e293b; }
    .electron { fill: #ef4444; }
  </style>
  <text x="400" y="40" class="label" style="text-anchor: middle; font-size: 24px;">Conductor vs Insulator</text>
  
  <!-- Copper Core (Conductor) -->
  <rect x="100" y="150" width="600" height="40" class="core" />
  <text x="400" y="130" class="label" style="text-anchor: middle;">Conductor (Copper Core)</text>
  <text x="400" y="220" class="label" style="text-anchor: middle; font-size: 14px; fill: #64748b;">Electrons move freely</text>
  
  <!-- Electrons moving -->
  <circle cx="150" cy="170" r="6" class="electron" />
  <line x1="160" y1="170" x2="180" y2="170" stroke="#ef4444" stroke-width="2" marker-end="url(#arrow)" />
  
  <circle cx="350" cy="170" r="6" class="electron" />
  <line x1="360" y1="170" x2="380" y2="170" stroke="#ef4444" stroke-width="2" marker-end="url(#arrow)" />

  <circle cx="550" cy="170" r="6" class="electron" />
  <line x1="560" y1="170" x2="580" y2="170" stroke="#ef4444" stroke-width="2" marker-end="url(#arrow)" />

  <!-- Insulation -->
  <rect x="200" y="140" width="400" height="60" class="insulation" opacity="0.4" />
  <rect x="200" y="100" width="400" height="10" class="insulation" />
  <rect x="200" y="230" width="400" height="10" class="insulation" />
  <text x="400" y="260" class="label" style="text-anchor: middle;">Insulator (Plastic Sheath)</text>
</svg>"""

    def _render_voltage_current(self) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 300" width="100%" height="100%" style="background-color: white;">
  <style>
    .label { font-family: sans-serif; font-size: 20px; font-weight: bold; fill: #1e293b; text-anchor: middle; }
    .desc { font-family: sans-serif; font-size: 14px; fill: #64748b; text-anchor: middle; }
    .box { fill: #f8fafc; stroke: #94a3b8; stroke-width: 2; rx: 8; }
  </style>
  <rect x="50" y="50" width="150" height="150" class="box" />
  <text x="125" y="110" class="label" style="fill: #3b82f6; font-size: 28px;">V</text>
  <text x="125" y="140" class="label">Voltage</text>
  <text x="125" y="160" class="desc">Push (Pressure)</text>

  <rect x="225" y="50" width="150" height="150" class="box" />
  <text x="300" y="110" class="label" style="fill: #ef4444; font-size: 28px;">I</text>
  <text x="300" y="140" class="label">Current</text>
  <text x="300" y="160" class="desc">Flow (Electrons)</text>

  <rect x="400" y="50" width="150" height="150" class="box" />
  <text x="475" y="110" class="label" style="fill: #f59e0b; font-size: 28px;">R</text>
  <text x="475" y="140" class="label">Resistance</text>
  <text x="475" y="160" class="desc">Squeeze (Friction)</text>
  
  <text x="300" y="250" class="label" style="font-size: 24px;">V = I × R (Ohm's Law)</text>
</svg>"""

    def _render_waveform(self) -> str:
        return self._render_analog_digital()

    def _render_transistor(self) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400" width="100%" height="100%" style="background-color: white;">
  <style>
    .line { stroke: #1e293b; stroke-width: 4; fill: none; }
    .label { font-family: sans-serif; font-size: 18px; font-weight: bold; fill: #1e293b; text-anchor: middle; }
  </style>
  <text x="200" y="40" class="label">NPN Transistor</text>
  <circle cx="200" cy="200" r="80" class="line" />
  <line x1="160" y1="140" x2="160" y2="260" class="line" />
  
  <!-- Base -->
  <line x1="50" y1="200" x2="160" y2="200" class="line" />
  <text x="50" y="190" class="label" style="text-anchor: end;">Base (B)</text>
  
  <!-- Collector -->
  <line x1="160" y1="160" x2="220" y2="120" class="line" />
  <line x1="220" y1="120" x2="220" y2="50" class="line" />
  <text x="220" y="40" class="label">Collector (C)</text>
  
  <!-- Emitter -->
  <line x1="160" y1="240" x2="220" y2="280" class="line" />
  <line x1="220" y1="280" x2="220" y2="350" class="line" />
  <path d="M 200 280 L 220 280 L 210 260 Z" style="fill: #1e293b;" />
  <text x="220" y="370" class="label">Emitter (E)</text>
</svg>"""

    def _render_diode(self) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="100%" height="100%" style="background-color: white;">
  <style>
    .line { stroke: #1e293b; stroke-width: 4; fill: none; }
    .fill { fill: #1e293b; }
    .label { font-family: sans-serif; font-size: 18px; font-weight: bold; fill: #1e293b; text-anchor: middle; }
  </style>
  <text x="200" y="40" class="label">Diode Symbol</text>
  
  <line x1="50" y1="150" x2="150" y2="150" class="line" />
  <line x1="250" y1="150" x2="350" y2="150" class="line" />
  
  <path d="M 150 100 L 150 200 L 250 150 Z" class="fill" />
  <line x1="250" y1="100" x2="250" y2="200" class="line" />
  
  <text x="120" y="240" class="label">Anode (+)</text>
  <text x="280" y="240" class="label">Cathode (-)</text>
</svg>"""

    def _render_capacitor(self) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300" width="100%" height="100%" style="background-color: white;">
  <style>
    .line { stroke: #1e293b; stroke-width: 4; fill: none; }
    .label { font-family: sans-serif; font-size: 18px; font-weight: bold; fill: #1e293b; text-anchor: middle; }
  </style>
  <text x="200" y="40" class="label">Capacitor Symbol</text>
  
  <line x1="50" y1="150" x2="180" y2="150" class="line" />
  <line x1="220" y1="150" x2="350" y2="150" class="line" />
  
  <line x1="180" y1="100" x2="180" y2="200" class="line" />
  <line x1="220" y1="100" x2="220" y2="200" class="line" />
</svg>"""

    def _render_series_parallel(self) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 400" width="100%" height="100%" style="background-color: white;">
  <style>
    .wire { stroke: #1e293b; stroke-width: 3; fill: none; }
    .label { font-family: sans-serif; font-size: 18px; font-weight: bold; fill: #1e293b; text-anchor: middle; }
  </style>
  
  <!-- Series -->
  <text x="200" y="40" class="label">Series Circuit</text>
  <rect x="100" y="100" width="200" height="150" class="wire" />
  <circle cx="150" cy="100" r="15" fill="#fde047" stroke="#1e293b" stroke-width="2" />
  <circle cx="250" cy="100" r="15" fill="#fde047" stroke="#1e293b" stroke-width="2" />
  
  <!-- Parallel -->
  <text x="600" y="40" class="label">Parallel Circuit</text>
  <rect x="500" y="100" width="200" height="150" class="wire" />
  <line x1="550" y1="100" x2="550" y2="250" class="wire" />
  <line x1="650" y1="100" x2="650" y2="250" class="wire" />
  <circle cx="550" cy="175" r="15" fill="#fde047" stroke="#1e293b" stroke-width="2" />
  <circle cx="650" cy="175" r="15" fill="#fde047" stroke="#1e293b" stroke-width="2" />
</svg>"""

    def _render_graph_chart(self) -> str:
        return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 400" width="100%" height="100%" style="background-color: white;">
  <style>
    .axis { stroke: #94a3b8; stroke-width: 3; }
    .line { stroke: #3b82f6; stroke-width: 4; fill: none; }
    .point { fill: #ef4444; }
    .label { font-family: sans-serif; font-size: 16px; fill: #1e293b; }
  </style>
  <text x="300" y="40" class="label" style="font-weight: bold; font-size: 20px; text-anchor: middle;">Data Chart</text>
  
  <line x1="50" y1="50" x2="50" y2="350" class="axis" />
  <line x1="50" y1="350" x2="550" y2="350" class="axis" />
  
  <path d="M 50 350 L 150 250 L 250 280 L 350 150 L 450 100 L 550 80" class="line" />
  <circle cx="150" cy="250" r="5" class="point" />
  <circle cx="250" cy="280" r="5" class="point" />
  <circle cx="350" cy="150" r="5" class="point" />
  <circle cx="450" cy="100" r="5" class="point" />
</svg>"""
