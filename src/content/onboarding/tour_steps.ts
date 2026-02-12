export interface TourStep {
  id: string;
  targetElement: string;
  title: string;
  body: string;
  nextLabel?: string;
  action?: {
    type: 'load_demo_compound' | 'navigate';
    smiles?: string;
    view?: string;
  };
}

export const TOUR_STEPS: TourStep[] = [
  {
    id: 'welcome',
    targetElement: '#main-content',
    title: 'Welcome to Edeon',
    body: 'Edeon is a desktop platform for agrochemical lead optimization with validated Tier-1 prediction models, calibrated uncertainty, and closed-loop molecular design. This 60-second tour will show you the main workflows.',
    nextLabel: 'Show me',
  },
  {
    id: 'honeycomb',
    targetElement: '#honeycomb-panel',
    title: 'The Honeycomb',
    body: 'Each cell shows a Tier-1 prediction with calibrated 95% confidence intervals. Green = in applicability domain, yellow = borderline, red = out of domain. Where measured data exists, you\'ll see a 🧪 experimental overlay.',
    nextLabel: 'Continue',
  },
  {
    id: 'fate_gauge',
    targetElement: '#fate-gauge',
    title: 'Environmental Fate',
    body: 'Koc, DT50, and GUS leaching index with Monte Carlo uncertainty propagation. The DT50 model uses a heteroscedastic architecture that captures both aleatoric (study-to-study) and epistemic (model) uncertainty separately.',
    nextLabel: 'Continue',
  },
  {
    id: 'docking',
    targetElement: '#docking-workbench-nav',
    title: 'Docking Workbench',
    body: 'Real AutoDock Vina docking with automatic receptor preparation, pocket detection, and ProLIF interaction analysis. Not a 3D visualizer pretending to be docking — actual docking.',
    action: { type: 'navigate', view: 'docking' },
    nextLabel: 'See generation',
  },
  {
    id: 'generation',
    targetElement: '#generation-workbench-nav',
    title: 'Generation Workbench',
    body: 'CReM-dock pipeline for closed-loop molecular design. Generated mutants are scored against the full Tier-1 ecotox + fate + mammalian stack. This combination doesn\'t exist in any other agrochemistry tool.',
    nextLabel: 'Finish',
  },
  {
    id: 'knowledge',
    targetElement: '#knowledge-hub-nav',
    title: 'Knowledge Hub',
    body: 'Federated search across PPDB, ECOTOX, OpenFoodTox, and ChEMBL, plus a Claude-powered Q&A assistant with citation-grounded answers. Press Cmd+K anytime to access the command palette.',
    nextLabel: 'Get started',
  },
];
