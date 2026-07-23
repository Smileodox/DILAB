import HookScene, { STEPS as HOOK_STEPS } from './HookScene'
import JourneySourceScene, { STEPS as SRC_STEPS } from './JourneySourceScene'
import JourneyMechanismScene, { STEPS as MECH_STEPS } from './JourneyMechanismScene'
import JourneyExtractionScene, { STEPS as EXT_STEPS } from './JourneyExtractionScene'
import JourneyFuturesScene, { STEPS as FUT_STEPS } from './JourneyFuturesScene'
import JourneyCouplingScene, { STEPS as CPL_STEPS } from './JourneyCouplingScene'
import JourneyFieldScene, { STEPS as FLD_STEPS } from './JourneyFieldScene'
import JourneyArchetypeScene, { STEPS as ARC_STEPS } from './JourneyArchetypeScene'
import ValidationScene, { STEPS as VAL_STEPS } from './ValidationScene'
import ImprovementLeversScene, { STEPS as LEV_STEPS } from './ImprovementLeversScene'
import LensMorphScene, { STEPS as LNS_STEPS } from './LensMorphScene'
import Slice3DScene, { STEPS as SLC_STEPS } from './Slice3DScene'
import ClosingScene, { STEPS as CLS_STEPS } from './ClosingScene'

// Deck order = talk order. `steps` = reveal steps within the scene (→ advances
// through steps first, then to the next scene).
export const SCENES = [
  { id: 'hook', title: 'Hook — the number chain', steps: HOOK_STEPS, component: HookScene },
  { id: 'journey-source', title: 'Journey 1 — it starts as text', steps: SRC_STEPS, component: JourneySourceScene },
  { id: 'journey-mechanism', title: 'Journey 2 — how a driver is found', steps: MECH_STEPS, component: JourneyMechanismScene },
  { id: 'journey-extraction', title: 'Journey 3 — text becomes a factor', steps: EXT_STEPS, component: JourneyExtractionScene },
  { id: 'journey-futures', title: 'Journey 4 — four futures', steps: FUT_STEPS, component: JourneyFuturesScene },
  { id: 'journey-coupling', title: 'Journey 5 — the sudoku rules (CIB)', steps: CPL_STEPS, component: JourneyCouplingScene },
  { id: 'journey-field', title: 'Journey 6 — 120 consistent scenarios', steps: FLD_STEPS, component: JourneyFieldScene },
  { id: 'journey-archetypes', title: 'Journey 7 — archetypes take a stance', steps: ARC_STEPS, component: JourneyArchetypeScene },
  { id: 'validation', title: 'Validation — the metal-detector test', steps: VAL_STEPS, component: ValidationScene },
  { id: 'improvement-levers', title: 'Improvement — three levers', steps: LEV_STEPS, component: ImprovementLeversScene },
  { id: 'lens-morph', title: 'Improvement — same field, four lenses', steps: LNS_STEPS, component: LensMorphScene },
  { id: 'slice-3d', title: 'Result space in 3D', steps: SLC_STEPS, component: Slice3DScene },
  { id: 'closing', title: 'Closing — one pipeline, many futures', steps: CLS_STEPS, component: ClosingScene },
]
